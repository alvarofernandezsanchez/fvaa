"""Cuantiles, cruces y calibración del experimento; sin ajuste al test."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_pinball_loss
from .evaluacion import calcular_metricas

CUANTILES = [("q10", .10), ("q50", .50), ("q90", .90)]


def entrenar_cuantiles(X, y, parametros, q10_lineal=False):
    modelos = {}
    for nombre, alpha in CUANTILES:
        params = dict(parametros, loss="quantile", alpha=alpha)
        if nombre == "q10" and q10_lineal:
            params["init"] = LinearRegression()
        modelos[nombre] = GradientBoostingRegressor(**params).fit(X, y)
    return modelos


def predecir_cuantiles(modelos, X):
    originales = pd.DataFrame({n: m.predict(X) for n,m in modelos.items()}, index=X.index)
    return originales, originales.clip(lower=0)


def ordenar_cuantiles(tabla):
    return pd.DataFrame(np.sort(tabla[[n for n,_ in CUANTILES]].to_numpy(), axis=1),
                        index=tabla.index, columns=[n for n,_ in CUANTILES])


def diagnosticar_cruces(tabla):
    return pd.DataFrame({
        "cruce": (tabla.q10 > tabla.q50) | (tabla.q50 > tabla.q90),
        "limites_invertidos": tabla.q10 > tabla.q90,
        "inversion_kwh": (tabla.q10 - tabla.q90).clip(lower=0)}, index=tabla.index)


def diagnosticar_q10(modelo, X, y):
    pred = modelo.predict(X)
    return {"minimo_original": float(pred.min()), "maximo_original": float(pred.max()),
            "constante": bool(np.all(pred == pred[0])),
            "arboles": int(len(modelo.estimators_)),
            "arboles_con_division": sum(int(a.tree_.n_leaves > 1) for a in modelo.estimators_.ravel()),
            "cuantil10_train": float(y.quantile(.10)), "fraccion_ceros_train": float(y.eq(0).mean())}


def evaluar_cuantiles(y, tabla, referencia):
    # Reutiliza las validaciones estrictas de alineación y finitud de métricas.
    for nombre,_ in CUANTILES:
        calcular_metricas(y, tabla[nombre])
    dentro = (y >= tabla.q10) & (y <= tabla.q90)
    anchura = tabla.q90 - tabla.q10
    def resumen(mascara):
        return {"horas": int(mascara.sum()), "cobertura_pct": float(dentro[mascara].mean()*100),
                "por_debajo_pct": float((y[mascara] < tabla.q10[mascara]).mean()*100),
                "por_encima_pct": float((y[mascara] > tabla.q90[mascara]).mean()*100),
                "anchura_media_kwh": float(anchura[mascara].mean())}
    grupos = {"total": resumen(pd.Series(True,index=y.index))}
    for nombre,mascara in {"produccion_cero": y.eq(0), "produccion_positiva": y.gt(0)}.items():
        if mascara.any(): grupos[nombre] = resumen(mascara)
    marginal = []
    for nombre,alpha in CUANTILES:
        marginal.append({"cuantil": nombre,
            "porcentaje_real_menor": float((y < tabla[nombre]).mean()*100),
            "porcentaje_real_menor_igual": float((y <= tabla[nombre]).mean()*100),
            "pinball_modelo": mean_pinball_loss(y,tabla[nombre],alpha=alpha),
            "pinball_constante": mean_pinball_loss(y,np.full(len(y),referencia.quantile(alpha)),alpha=alpha)})
    return pd.DataFrame.from_dict(grupos,orient="index").rename_axis("grupo"), pd.DataFrame(marginal).set_index("cuantil")
