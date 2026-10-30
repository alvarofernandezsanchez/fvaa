"""Orquestación por etapas del experimento PR20–2020.

No carga modelos joblib: reconstruye configuraciones declaradas y reentrena.
"""
import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import logging
from pathlib import Path
import platform
import subprocess
import uuid

import joblib
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

from .busquedas import buscar_temporal
from .cuantiles import (diagnosticar_cruces, diagnosticar_q10, entrenar_cuantiles,
                         evaluar_cuantiles, ordenar_cuantiles, predecir_cuantiles)
from .evaluacion import evaluar_predicciones
from .features import crear_variables_historicas
from .figuras import dibujar_intervalo, dibujar_predicciones
from .modelos import ENTRADAS, OBJETIVO, crear_modelo, predecir, referencias
from .particiones import separar_temporalmente
from .produccion import agregar_produccion_horaria, cargar_produccion

LOG = logging.getLogger(__name__)
LIMITACIONES = """Energía estimada: la potencia media observada se supone representativa de toda la hora.
Cobertura mínima del 99 %; las ausencias no se sustituyen por cero.
Objetivo horario pendiente de coordinación con el contrato común de 15 minutos.
Solo producción histórica y calendario; sin irradiación ni pronósticos meteorológicos.
El test de 2020 ya fue observado en el notebook: no es un periodo independiente para futuras mejoras.
Los cuantiles pueden cruzarse y estar mal calibrados. Su ordenación no garantiza cobertura nominal.
Las métricas exportadas corresponden únicamente a esta ejecución; no se copian las del notebook.
"""


def guardar_json(ruta, valor):
    ruta.write_text(json.dumps(valor, ensure_ascii=False, indent=2, default=str,
                               allow_nan=False) + "\n", encoding="utf-8")


def leer_json(ruta):
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def fecha_utc(valor):
    return pd.to_datetime(valor, utc=True)


def validar_config(c):
    requeridos = {"experimento", "entrada", "salidas", "inicio", "fin_exclusivo",
        "inicio_validacion", "inicio_test", "cobertura_minima", "entradas", "objetivo",
        "cv_splits", "n_jobs_busquedas", "modelos", "profundidades_rf", "busquedas",
        "variantes_validacion", "variantes_finales", "cuantiles", "figuras"}
    if requeridos - c.keys():
        raise ValueError(f"Faltan claves de configuración: {sorted(requeridos-c.keys())}")
    if c["entradas"] != ENTRADAS or c["objetivo"] != OBJETIVO:
        raise ValueError("Este pipeline utiliza las variables y objetivo horarios del notebook.")
    if c["cobertura_minima"] != 99 or c["cv_splits"] != 3:
        raise ValueError("El experimento requiere cobertura del 99 % y tres particiones internas.")
    fechas = [fecha_utc(c[k]) for k in ("inicio", "inicio_validacion", "inicio_test", "fin_exclusivo")]
    if any(pd.isna(f) for f in fechas) or not all(a < b for a,b in zip(fechas,fechas[1:])):
        raise ValueError("Las fechas deben ser válidas y seguir inicio < validación < test < fin.")
    finales = {"lineal": "lineal", "rf": "rf_grid1", "gb": "gb_inicial"}
    if {n:v["fuente"] for n,v in c["variantes_finales"].items()} != finales:
        raise ValueError("Las variantes finales deben ser lineal, primera búsqueda RF y GB inicial.")
    if not all(v["minimo_cero"] is True for v in c["variantes_finales"].values()):
        raise ValueError("En test se aplica mínimo cero a los modelos puntuales.")
    if c["cuantiles"]["finales"] != {"q10":"alternativo_lineal", "q50":"original", "q90":"original"}:
        raise ValueError("Cuantiles finales: q10 alternativo, q50 y q90 originales.")
    for grupo in ("variantes_validacion", "variantes_finales"):
        for variante in c[grupo].values():
            if variante["fuente"] not in c["modelos"] and variante["fuente"] not in c["busquedas"]:
                raise ValueError(f"Fuente de modelo desconocida: {variante['fuente']}")


def huella(ruta):
    return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()


def metadatos_repositorio(root):
    def git(*args):
        try:
            return subprocess.check_output(["git", "-C", str(root), *args],
                                           text=True, stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    estado = git("status", "--porcelain", "--untracked-files=all")
    return {"commit": git("rev-parse", "HEAD"), "rama": git("branch", "--show-current"),
            "cambios_locales": bool(estado) if estado is not None else None, "estado": estado}


def nueva_ejecucion(c, root, stage):
    carpeta = root / c["salidas"] / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
                                      + "_" + stage + "_" + uuid.uuid4().hex[:8])
    carpeta.mkdir(parents=True, exist_ok=False)
    guardar_json(carpeta / "config.json", c)
    guardar_json(carpeta / "entorno.json", {"python": platform.python_version(),
        "dependencias": {n: version(n) for n in ("numpy", "pandas", "scikit-learn", "matplotlib", "joblib")},
        "git": metadatos_repositorio(root)})
    (carpeta / "limitaciones.txt").write_text(LIMITACIONES, encoding="utf-8")
    return carpeta


def exportar(tabla, carpeta, nombre):
    tabla.to_csv(carpeta / (nombre + ".csv"), index_label=tabla.index.name or "timestamp")


def preparar(c, root, out):
    entrada = root / c["entrada"]
    LOG.info("Cargando producción de %s", entrada)
    raw = cargar_produccion(entrada)
    raw = raw.loc[(raw.timestamp >= fecha_utc(c["inicio"])) &
                  (raw.timestamp < fecha_utc(c["fin_exclusivo"]))].copy()
    horario = agregar_produccion_horaria(raw, c["cobertura_minima"])
    variables = crear_variables_historicas(horario)
    limpio = variables.dropna().copy()
    particiones = separar_temporalmente(limpio, c["inicio_validacion"], c["inicio_test"])
    diferencias = raw.timestamp.diff()
    esperadas = int((raw.timestamp.max()-raw.timestamp.min()).total_seconds())+1
    calidad = {"entrada": {"ruta": str(entrada.resolve()), "bytes": entrada.stat().st_size,
                            "mtime_ns": entrada.stat().st_mtime_ns},
        "filas": len(raw), "primera_fecha": raw.timestamp.min(), "ultima_fecha": raw.timestamp.max(),
        "registros_esperados_entre_extremos": esperadas,
        "segundos_sin_registro": esperadas-len(raw),
        "mayor_intervalo_segundos": float(diferencias.max().total_seconds()),
        "timestamps_invalidos": 0, "timestamps_duplicados": 0, "timestamps_desordenados": 0,
        "tramos_con_hueco": int(diferencias.gt(pd.Timedelta(seconds=1)).sum()),
        "intervalos_mas_frecuentes": {str(k):int(v) for k,v in diferencias.value_counts().head(10).items()},
        "cobertura_temporal_pct": 100*len(raw)/esperadas,
        "nulos_potencia": int(raw.active_power_P1.isna().sum()),
        "ceros_potencia": int(raw.active_power_P1.eq(0).sum()),
        "potencia_w": raw.active_power_P1.describe().to_dict(),
        "horas": len(horario), "horas_invalidas": int((~horario.hora_valida).sum()),
        "filas_modelo": len(variables), "filas_completas": len(limpio),
        "filas_excluidas": len(variables)-len(limpio),
        "ausencias_por_columna": variables.isna().sum().to_dict(),
        "particiones": {n:{"filas":len(t),"inicio":t.index.min(),"fin":t.index.max()} for n,t in particiones.items()}}
    guardar_json(out / "calidad.json", calidad)
    exportar(horario,out,"produccion_horaria")
    exportar(horario[["cobertura_pct"]].describe(),out,"cobertura_resumen")
    exportar(horario.nsmallest(10,"cobertura_pct"),out,"horas_menor_cobertura")
    exportar(variables,out,"variables_con_ausencias")
    exportar(variables.loc[variables.isna().any(axis=1)],out,"filas_excluidas")
    for nombre,tabla in particiones.items(): exportar(tabla,out,nombre)
    guardar_json(out / "preparacion.json", {n:huella(out/(n+".csv")) for n in particiones})
    dibujar_predicciones(horario[["energia_estimada_kwh"]],out/"energia_primera_semana.png",
                          "PR20: energía horaria estimada",*c["figuras"]["produccion"])
    LOG.info("Preparadas %d filas; excluidas %d",len(limpio),len(variables)-len(limpio))


def validar_ejecucion(ruta, c, etapa):
    ruta = Path(ruta)
    if leer_json(ruta/"config.json") != c:
        raise ValueError("La configuración no coincide con la ejecución precedente.")
    estado = leer_json(ruta/"estado.json")
    if estado != {"etapa":etapa,"estado":"completo"}:
        raise ValueError(f"Se requiere una etapa {etapa} completada.")
    return ruta


def leer_particion(preparada, nombre, c):
    ruta = preparada/(nombre+".csv")
    if huella(ruta) != leer_json(preparada/"preparacion.json")[nombre]:
        raise ValueError(f"La partición {nombre} cambió desde su preparación.")
    tabla = pd.read_csv(ruta,index_col=0)
    tabla.index = pd.to_datetime(tabla.index,utc=True)
    if tabla.empty or not tabla.index.is_unique or not tabla.index.is_monotonic_increasing:
        raise ValueError(f"Partición {nombre} vacía o índice inválido.")
    if tabla.isna().any().any():
        raise ValueError(f"Partición {nombre} con ausencias no eliminadas.")
    idx = tabla.index
    val, test = fecha_utc(c["inicio_validacion"]),fecha_utc(c["inicio_test"])
    mascara = {"train":idx < val,"val":(idx >= val)&(idx < test),"test":idx >= test}[nombre]
    if not mascara.all():
        raise ValueError(f"Fechas fuera del periodo de {nombre}.")
    return tabla


def exportar_probabilistico(y, originales, corregidos, referencia, out, prefijo):
    exportar(originales,out,prefijo+"_originales")
    exportar(originales.describe(),out,prefijo+"_resumen_originales")
    exportar(corregidos,out,prefijo+"_minimo_cero")
    cruces = diagnosticar_cruces(corregidos)
    exportar(cruces,out,prefijo+"_cruces")
    guardar_json(out/(prefijo+"_cruces_resumen.json"),{
        "horas":len(cruces), "horas_con_cruce":int(cruces.cruce.sum()),
        "porcentaje_cruces":float(cruces.cruce.mean()*100),
        "limites_invertidos":int(cruces.limites_invertidos.sum()),
        "inversion_maxima_kwh":float(cruces.inversion_kwh.max())})
    exportar(corregidos.assign(real=y,inversion_kwh=cruces.inversion_kwh)
             .loc[cruces.limites_invertidos].nlargest(10,"inversion_kwh"),out,prefijo+"_mayores_inversiones")
    grupos, marginal = evaluar_cuantiles(y,corregidos,referencia)
    exportar(grupos,out,prefijo+"_cobertura")
    exportar(marginal,out,prefijo+"_calibracion_pinball")


def desarrollar(c, preparada, out):
    # No leer ni calcular hashes de test.csv durante selección.
    train,val = (leer_particion(preparada,n,c) for n in ("train","val"))
    X,y = train[ENTRADAS],train[OBJETIVO]
    Xv,yv = val[ENTRADAS],val[OBJETIVO]
    modelos, especificaciones = {},dict(c["modelos"])
    for nombre,spec in c["modelos"].items():
        LOG.info("Entrenando %s",nombre)
        modelos[nombre] = crear_modelo(spec["tipo"],spec["parametros"]).fit(X,y)
    for nombre,spec in c["busquedas"].items():
        LOG.info("Búsqueda temporal %s",nombre)
        busqueda, resultados, limites = buscar_temporal(X,y,spec,c["cv_splits"],c["n_jobs_busquedas"])
        modelos[nombre] = busqueda.best_estimator_
        especificaciones[nombre] = {"tipo":spec["tipo"],"parametros":dict(spec["parametros"],**busqueda.best_params_)}
        exportar(resultados,out,nombre+"_cv")
        exportar(limites,out,nombre+"_particiones")
        guardar_json(out/(nombre+"_mejor.json"),{"parametros":busqueda.best_params_,"MAE_cv_kwh":-busqueda.best_score_})
    pred = referencias(Xv)
    originales = pd.DataFrame(index=Xv.index)
    train_metrics = []
    for nombre,spec in c["variantes_validacion"].items():
        modelo = modelos[spec["fuente"]]
        originales[nombre],pred[nombre] = predecir(modelo,Xv,spec["minimo_cero"])
        _,pt = predecir(modelo,X,spec["minimo_cero"])
        mt = evaluar_predicciones(y,pt.to_frame(nombre)).iloc[0].to_dict()
        train_metrics.append(dict(modelo=nombre,**mt))
    exportar(pd.DataFrame(train_metrics).set_index("modelo"),out,"metricas_train")
    exportar(evaluar_predicciones(yv,pred),out,"metricas_validacion")
    exportar(pred.assign(real=yv),out,"predicciones_validacion")
    exportar(originales,out,"predicciones_validacion_originales")
    guardar_json(out/"negativos.json",{n:int(originales[n].lt(0).sum()) for n in originales})
    lineal = modelos["lineal"]
    exportar(pd.DataFrame({"coeficiente":lineal.coef_},index=ENTRADAS),out,"coeficientes_lineal")
    guardar_json(out/"intercepto_lineal.json",{"kwh":float(lineal.intercept_)})
    error = pred["lineal_minimo_cero"]-yv
    exportar(pd.DataFrame({"real":yv,"prediccion":pred["lineal_minimo_cero"],"error":error,
                          "error_absoluto":error.abs()}).nlargest(10,"error_absoluto"),out,"mayores_errores_lineal")
    guardar_json(out/"sesgo_lineal.json",{"error_medio_kwh":float(error.mean())})
    profundidades = []
    for profundidad in c["profundidades_rf"]:
        params = dict(c["modelos"]["rf_inicial"]["parametros"],max_depth=profundidad)
        m = crear_modelo("rf",params).fit(X,y)
        modelos["rf_profundidad_"+str(profundidad)] = m
        fila = {"profundidad":str(profundidad)}
        for nombre,xx,yy in (("train",X,y),("val",Xv,yv)):
            fila.update({nombre+"_"+k:v for k,v in evaluar_predicciones(yy,predecir(m,xx)[1].to_frame("rf")).iloc[0].items()})
        profundidades.append(fila)
    exportar(pd.DataFrame(profundidades),out,"comparacion_profundidades")
    params = c["cuantiles"]["parametros"]
    qmodelos = entrenar_cuantiles(X,y,params)
    qo,q = predecir_cuantiles(qmodelos,Xv)
    guardar_json(out/"diagnostico_q10.json",dict(
        diagnosticar_q10(qmodelos["q10"],X,y),
        minimo_validacion_original=float(qo.q10.min()),
        maximo_validacion_original=float(qo.q10.max()),
        porcentaje_cero_validacion=float(q.q10.eq(0).mean()*100)))
    exportar_probabilistico(yv,qo,q,y,out,"cuantiles_iniciales")
    alternativo = GradientBoostingRegressor(**dict(params,loss="quantile",alpha=.1,init=LinearRegression())).fit(X,y)
    qa_o,qa = qo.copy(),q.copy()
    qa_o["q10"],qa["q10"] = predecir(alternativo,Xv,True)
    exportar_probabilistico(yv,qa_o,qa,y,out,"cuantiles_alternativos")
    guardar_json(out/"diagnostico_q10_alternativo.json",diagnosticar_q10(alternativo,X,y))
    ordenados = ordenar_cuantiles(qa)
    exportar_probabilistico(yv,ordenados,ordenados,y,out,"cuantiles_ordenados")
    comparacion = []
    for nombre,tabla in (("inicial",q),("alternativo_ordenado",ordenados)):
        grupos,marginal = evaluar_cuantiles(yv,tabla,y)
        comparacion.append(dict(version=nombre,**grupos.loc["total"].to_dict(),pinball_media=marginal.pinball_modelo.mean()))
    exportar(pd.DataFrame(comparacion).set_index("version"),out,"comparacion_intervalos")
    for nombre,modelo in modelos.items(): joblib.dump(modelo,out/(nombre+".joblib"))
    for nombre,modelo in qmodelos.items(): joblib.dump(modelo,out/(nombre+"_original.joblib"))
    joblib.dump(alternativo,out/"q10_alternativo.joblib")
    guardar_json(out/"seleccion.json",{"especificaciones":especificaciones,
        "preparacion":str(preparada.resolve()), "preparacion_manifest_sha256":huella(preparada/"preparacion.json"),
        "variantes_finales":c["variantes_finales"]})
    dibujar_predicciones(pred.assign(real=yv),out/"comparacion_validacion.png","PR20: validación",*c["figuras"]["validacion"])
    dibujar_intervalo(yv,ordenados,out/"intervalo_validacion.png",*c["figuras"]["validacion"])


def evaluar_final(c, preparada, desarrollo, out):
    seleccion = leer_json(desarrollo/"seleccion.json")
    if (seleccion["preparacion"] != str(preparada.resolve()) or
        seleccion["preparacion_manifest_sha256"] != huella(preparada/"preparacion.json")):
        raise ValueError("El desarrollo no corresponde a esta preparación.")
    train,val,test = (leer_particion(preparada,n,c) for n in ("train","val","test"))
    datos = pd.concat([train,val]).sort_index()
    X,y,Xt,yt = datos[ENTRADAS],datos[OBJETIVO],test[ENTRADAS],test[OBJETIVO]
    pred = referencias(Xt)
    originales = pd.DataFrame(index=Xt.index)
    for nombre,variante in c["variantes_finales"].items():
        spec = seleccion["especificaciones"][variante["fuente"]]
        modelo = crear_modelo(spec["tipo"],spec["parametros"]).fit(X,y)
        originales[nombre],pred[nombre] = predecir(modelo,Xt,variante["minimo_cero"])
        joblib.dump(modelo,out/(nombre+"_final.joblib"))
    exportar(evaluar_predicciones(yt,pred),out,"metricas_test")
    exportar(pred.assign(real=yt),out,"predicciones_test")
    exportar(originales,out,"predicciones_test_originales")
    qmodelos = entrenar_cuantiles(X,y,c["cuantiles"]["parametros"],q10_lineal=True)
    qo,q = predecir_cuantiles(qmodelos,Xt)
    exportar_probabilistico(yt,qo,q,y,out,"cuantiles_test")
    ordenados = ordenar_cuantiles(q)
    exportar_probabilistico(yt,ordenados,ordenados,y,out,"cuantiles_test_ordenados")
    for nombre,modelo in qmodelos.items():joblib.dump(modelo,out/(nombre+"_final.joblib"))
    dibujar_predicciones(pred.assign(real=yt),out/"comparacion_test.png","PR20: test ya observado",*c["figuras"]["test"])
    dibujar_intervalo(yt,ordenados,out/"intervalo_test.png",*c["figuras"]["test"])


def ejecutar(c, root, etapa="preparacion", preparada=None, desarrollo=None):
    validar_config(c)
    if etapa not in ("preparacion","desarrollo","final","completo"):
        raise ValueError(f"Etapa desconocida: {etapa}")
    root = Path(root).resolve()
    # Comprobar dependencias antes de crear una nueva carpeta de resultados.
    if etapa in ("desarrollo","final"):
        if preparada is None: raise ValueError("Se requiere --prepared-run.")
        preparada = validar_ejecucion(preparada,c,"preparacion")
    if etapa == "final":
        if desarrollo is None: raise ValueError("Se requiere --development-run.")
        desarrollo = validar_ejecucion(desarrollo,c,"desarrollo")
    if etapa == "completo":
        preparada = ejecutar(c,root,"preparacion")
        desarrollo = ejecutar(c,root,"desarrollo",preparada)
        return ejecutar(c,root,"final",preparada,desarrollo)
    out = nueva_ejecucion(c,root,etapa)
    handler = logging.FileHandler(out/"ejecucion.log",encoding="utf-8")
    logging.getLogger().addHandler(handler)
    guardar_json(out/"estado.json",{"etapa":etapa,"estado":"en_curso"})
    try:
        guardar_json(out/"procedencia.json",{"preparacion":str(preparada) if preparada else None,
                                              "desarrollo":str(desarrollo) if desarrollo else None})
        if etapa == "preparacion": preparar(c,root,out)
        elif etapa == "desarrollo": desarrollar(c,preparada,out)
        else: evaluar_final(c,preparada,desarrollo,out)
        guardar_json(out/"estado.json",{"etapa":etapa,"estado":"completo"})
        LOG.info("Etapa %s completada: %s",etapa,out)
    except Exception:
        guardar_json(out/"estado.json",{"etapa":etapa,"estado":"fallido"})
        LOG.exception("Fallo en etapa %s. Se conservan resultados parciales en %s",etapa,out)
        raise
    finally:
        logging.getLogger().removeHandler(handler); handler.close()
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description="Experimento PR20 por etapas; por defecto solo preparación.")
    parser.add_argument("--config",required=True,type=Path)
    parser.add_argument("--stage",choices=["preparacion","desarrollo","final","completo"],default="preparacion")
    parser.add_argument("--prepared-run",type=Path,help="Carpeta de una preparación completada")
    parser.add_argument("--development-run",type=Path,help="Carpeta de desarrollo completado; necesaria en final")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    # Todas las rutas de configuración se interpretan desde la raíz del proyecto.
    root = args.config.resolve().parent.parent
    try:
        salida = ejecutar(leer_json(args.config),root,args.stage,args.prepared_run,args.development_run)
    except (ValueError,KeyError,FileNotFoundError) as error:
        parser.exit(2,f"Error: {error}\n")
    print(salida)


if __name__ == "__main__":
    main()
