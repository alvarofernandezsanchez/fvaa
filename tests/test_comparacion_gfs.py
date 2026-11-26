"""Pruebas de las cuatro configuraciones, la muestra común, la latencia y los intervalos GFS."""

import json
from pathlib import Path

import pandas as pd

from fvaa.pronosticos import alinear_gfs
from scripts.ampliar_gfs import convertir_3h

RAIZ = Path(__file__).resolve().parents[1]
CELDAS = json.loads((RAIZ / "notebooks/FVAA_fase1.ipynb").read_text(encoding="utf-8"))["cells"]
CODIGO = "\n".join("".join(c["source"]) for c in CELDAS if c["cell_type"] == "code")


def gfs_sintetico():
    t = pd.Timestamp("2020-01-02", tz="UTC")
    filas = []
    for emision in pd.date_range(t - pd.Timedelta(hours=18), t, freq="6h"):
        for plazo in range(3, 37, 3):
            filas.append({
                "emision_utc": emision,
                "inicio_validez_utc": emision + pd.Timedelta(hours=plazo - 3),
                "fin_validez_utc": emision + pd.Timedelta(hours=plazo),
                "plazo_horas": plazo,
                # El valor identifica la emision para detectar si se usa una futura.
                "dswrf_media_w_m2": float(emision.hour + 1),
            })
    return pd.DataFrame(filas)


def test_cuatro_configuraciones_en_el_notebook():
    # 3A no incluye CAMS (meteo); 3B si; ambas comparten nivel 1 y los pronosticos.
    assert 'niveles["3A Pronóstico sin CAMS"] = nivel1 + pronosticos' in CODIGO
    assert 'niveles["3B CAMS + pronóstico"] = nivel1 + meteo + pronosticos' in CODIGO
    assert '"Sin meteorología": nivel1' in CODIGO and '"Con irradiación": nivel1 + meteo' in CODIGO
    # La muestra común sale de la unión de columnas de los cuatro niveles.
    assert "comunes = list(set().union(*niveles.values()))" in CODIGO
    assert "train, val, test = dividir(y, h, comunes)" in CODIGO
    # Sin cobertura de 24 h no se evalua con horizontes parciales.
    assert "horas_gfs" not in CODIGO
    assert "if h == 24 and not cobertura_24h:" in CODIGO


def test_latencia_no_usa_ejecuciones_posteriores():
    datos = gfs_sintetico()
    t = pd.date_range("2020-01-02 00:00", periods=1, freq="h", tz="UTC")
    for latencia in [3, 6]:
        pron = alinear_gfs(t, datos, latencia).iloc[0]
        usable = datos[datos.emision_utc + pd.Timedelta(hours=latencia) <= t[0]]
        for h in range(24):
            objetivo = t[0] + pd.Timedelta(hours=h)
            candidatos = usable[(usable.inicio_validez_utc <= objetivo) & (objetivo < usable.fin_validez_utc)]
            esperado = candidatos.sort_values("emision_utc").dswrf_media_w_m2.iloc[-1]
            assert pron[f"pronostico_h{h}"] == esperado
    # Con latencia 6 h la ejecucion de las 00 UTC del mismo dia (valor 1) no esta disponible a las 00.
    assert 1.0 not in alinear_gfs(t, datos, 6).iloc[0].to_numpy()
    assert (alinear_gfs(t, datos, 0).iloc[0] == 1.0).any()


def test_intervalos_3h_y_6h_sin_solape_y_negativos_documentados():
    t = pd.Timestamp("2020-01-01", tz="UTC")
    # Medias nativas: 3 h (24-27) = 100, 6 h (24-30) = 150 -> 27-30 = 200; 3 h (30-33) = 300, 6 h (30-36) = 100 -> 33-36 = -100.
    nativos = pd.DataFrame([(t, 24, 27, 100.), (t, 24, 30, 150.), (t, 30, 33, 300.), (t, 30, 36, 100.)],
                           columns=["emision_utc", "inicio", "fin", "valor"])
    r = convertir_3h(nativos).sort_values("inicio_validez_utc")
    assert r.dswrf_media_w_m2.tolist() == [100., 200., 300., -100.]
    assert r.inicio_validez_utc.iloc[1:].tolist() == r.fin_validez_utc.iloc[:-1].tolist()  # contiguos, sin solape
    assert not r.inicio_validez_utc.duplicated().any()
    # El negativo se conserva en los datos y solo se trunca a 0 al alinear.
    r["lat"], r["lon"], r["duracion_intervalo_h"] = 32.75, 343.0, 3
    pron = alinear_gfs(pd.DatetimeIndex([t + pd.Timedelta(hours=33)]), r, latencia_h=0)
    assert pron["pronostico_h0"].iloc[0] == 0
