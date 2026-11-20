"""Pruebas funcionales sin datos reales ni búsquedas costosas."""
import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator

from fvaa.cuantiles import (diagnosticar_cruces, evaluar_cuantiles, ordenar_cuantiles)
from fvaa.modelos import predecir, mae_no_negativo
from fvaa.pipeline import ejecutar, leer_json, main
from fvaa.produccion import cargar_produccion

ROOT = Path(__file__).resolve().parents[1]


class PrediccionesFijas(BaseEstimator):
    def predict(self,X): return np.array([-0.1,0.2,0.3])


def test_minimo_cero_preserva_originales_y_fechas():
    X = pd.DataFrame(index=pd.date_range("2020-01-01",periods=3,freq="h",tz="UTC"))
    raw, corregida = predecir(PrediccionesFijas(),X,True)
    assert raw.tolist() == [-.1,.2,.3]
    assert corregida.tolist() == [0,.2,.3]
    assert raw.index.equals(corregida.index)
    assert mae_no_negativo([0,.2,.3],raw) == 0


def test_cruces_ordenacion_cobertura_y_pinball():
    idx = pd.date_range("2020-01-01",periods=3,freq="h",tz="UTC")
    q = pd.DataFrame({"q10":[.3,0,0],"q50":[.1,.2,.1],"q90":[.2,.4,.3]},index=idx)
    original = q.copy(deep=True)
    assert diagnosticar_cruces(q).cruce.tolist() == [True,False,False]
    ordenados = ordenar_cuantiles(q)
    pd.testing.assert_frame_equal(q,original)
    assert ordenados.iloc[0].tolist() == [.1,.2,.3]
    y = pd.Series([.2,.5,0],index=idx)
    grupos,marginal = evaluar_cuantiles(y,ordenados,y)
    assert grupos.loc["total","cobertura_pct"] == pytest.approx(200/3)
    assert grupos.loc["total","anchura_media_kwh"] == pytest.approx(.3)
    assert marginal.loc["q10","porcentaje_real_menor_igual"] >= marginal.loc["q10","porcentaje_real_menor"]
    with pytest.raises(ValueError,match="índices"):
        evaluar_cuantiles(y.iloc[::-1],ordenados,y)


def test_carga_utc_y_rechazo_de_duplicados(tmp_path):
    p=tmp_path/"raw.csv"
    pd.DataFrame({"timestamp":["2020-01-01 00:00:00","2020-01-01 00:00:01"],
                  "active_power_P1":[0,5]}).to_csv(p,index=False)
    assert str(cargar_produccion(p).timestamp.dt.tz) == "UTC"
    pd.DataFrame({"timestamp":["2020-01-01","2020-01-01"],
                  "active_power_P1":[0,5]}).to_csv(p,index=False)
    with pytest.raises(ValueError,match="duplicados"): cargar_produccion(p)


def configuracion_sintetica(tmp_path):
    c=leer_json(ROOT/"configs/pr20_2020.json")
    c.update(entrada="raw.csv",salidas="resultados",inicio="2020-01-01",
             fin_exclusivo="2020-01-05",inicio_validacion="2020-01-03",inicio_test="2020-01-04",
             n_jobs_busquedas=1)
    c["figuras"]={"produccion":["2020-01-01","2020-01-02"],
                   "validacion":["2020-01-03","2020-01-03"],"test":["2020-01-04","2020-01-04"]}
    # Solo esta configuración de prueba reduce el coste; la de PR20 se conserva íntegra.
    for spec in c["modelos"].values():
        if spec["tipo"] != "lineal":spec["parametros"]["n_estimators"]=2
        if "n_jobs" in spec["parametros"]:spec["parametros"]["n_jobs"]=1
    for nombre,spec in c["busquedas"].items():
        spec["parametros"]["n_estimators"]=2
        spec["grid"]={"max_depth":[2],"min_samples_leaf":[1]}
    c["cuantiles"]["parametros"]["n_estimators"]=2
    c["profundidades_rf"]=[2]
    idx=pd.date_range("2020-01-01",periods=96*3600,freq="s",tz="UTC")
    power=np.maximum(0,np.sin((idx.hour.to_numpy()-6)*np.pi/12))*500
    raw=pd.DataFrame({"timestamp":idx,"active_power_P1":power})
    # Una hora incompleta para comprobar propagación de ausencias a retardos.
    raw.loc[(raw.timestamp.dt.day==1)&(raw.timestamp.dt.hour==5),"active_power_P1"]=np.nan
    raw.to_csv(tmp_path/"raw.csv",index=False)
    return c


def test_integracion_etapas_no_leen_test_en_desarrollo(tmp_path,monkeypatch):
    c=configuracion_sintetica(tmp_path)
    preparada=ejecutar(c,tmp_path,"preparacion")
    calidad=leer_json(preparada/"calidad.json")
    assert calidad["filas_excluidas"] > 24
    # Si desarrollo abre test por cualquier motivo, el test falla.
    import fvaa.pipeline as pipeline
    leer_original=pipeline.leer_particion
    def sin_test(preparada,nombre,c):
        assert nombre != "test", "Desarrollo accedió al test"
        return leer_original(preparada,nombre,c)
    with monkeypatch.context() as m:
        m.setattr(pipeline,"leer_particion",sin_test)
        desarrollo=ejecutar(c,tmp_path,"desarrollo",preparada)
    assert not (desarrollo/"metricas_test.csv").exists()
    assert leer_json(desarrollo/"seleccion.json")["variantes_finales"] == c["variantes_finales"]
    crear_original=pipeline.crear_modelo
    ajustes_finales=[]
    def modelo_vigilado(tipo,parametros):
        modelo=crear_original(tipo,parametros)
        fit_original=modelo.fit
        def fit(X,y):
            assert X.index.max() < pd.Timestamp(c["inicio_test"],tz="UTC")
            assert X.index.max() >= pd.Timestamp(c["inicio_validacion"],tz="UTC")
            ajustes_finales.append(tipo)
            return fit_original(X,y)
        modelo.fit=fit
        return modelo
    # Vigilar fit sin serializar funciones locales añadidas por la propia prueba.
    dump_original=pipeline.joblib.dump
    def dump_vigilado(modelo,ruta):
        if "fit" in modelo.__dict__:del modelo.__dict__["fit"]
        return dump_original(modelo,ruta)
    with monkeypatch.context() as m:
        m.setattr(pipeline,"crear_modelo",modelo_vigilado)
        m.setattr(pipeline.joblib,"dump",dump_vigilado)
        final=ejecutar(c,tmp_path,"final",preparada,desarrollo)
    assert ajustes_finales==["lineal","rf","gb"]
    assert len({preparada,desarrollo,final})==3
    assert leer_json(final/"estado.json")["estado"] == "completo"
    assert (final/"rf_final.joblib").is_file()
    assert (final/"intervalo_test.png").is_file()
    metricas=pd.read_csv(final/"metricas_test.csv",index_col=0)
    assert set(metricas.index)=={"persistencia","persistencia_diaria","lineal","rf","gb"}
    assert np.isfinite(metricas.to_numpy()).all()
    cv=pd.read_csv(desarrollo/"rf_grid1_cv.csv")
    assert "MAE_split0_test_score" in cv
    assert "split2_train_score" in cv
    pred=pd.read_csv(final/"predicciones_test.csv",index_col=0)
    assert (pd.to_datetime(pred.index,utc=True)>=pd.Timestamp(c["inicio_test"],tz="UTC")).all()
    # La procedencia/configuración de desarrollo no puede sustituirse silenciosamente.
    alterada=copy.deepcopy(c);alterada["modelos"]["lineal"]["parametros"]={"fit_intercept":False}
    with pytest.raises(ValueError,match="configuración"):
        ejecutar(alterada,tmp_path,"final",preparada,desarrollo)


def test_final_requiere_desarrollo_y_no_hay_completo_implicito(tmp_path,capsys):
    c=leer_json(ROOT/"configs/pr20_2020.json")
    with pytest.raises(ValueError,match="prepared-run"):
        ejecutar(c,tmp_path,"final")
    with pytest.raises(SystemExit) as info:main(["--help"])
    assert info.value.code==0
    assert "por defecto solo preparación" in capsys.readouterr().out
