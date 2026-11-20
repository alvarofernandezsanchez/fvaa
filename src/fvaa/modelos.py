
"""Modelos de regresión y referencias de persistencia."""

import numpy as np
import pandas as pd

from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ENTRADAS = [
    "energia_anterior_1h",
    "energia_anterior_2h",
    "energia_anterior_24h",
    "hora",
    "mes"
]

OBJETIVO = "objetivo_kwh"


def crear_modelo(tipo, parametros):
    if tipo == "ridge":
        return make_pipeline(StandardScaler(), Ridge(**parametros))

    modelos = {
        "lineal": LinearRegression,
        "rf": RandomForestRegressor,
        "gb": GradientBoostingRegressor
    }

    if tipo not in modelos:
        raise ValueError(f"Modelo desconocido: {tipo}")

    return modelos[tipo](**parametros)


def predecir(modelo, X, minimo_cero=False):
    original = pd.Series(modelo.predict(X), index=X.index)
    corregida = original.clip(lower=0) if minimo_cero else original.copy()

    return original, corregida


def referencias(X):
    return pd.DataFrame({
        "persistencia": X["energia_anterior_1h"],
        "persistencia_diaria": X["energia_anterior_24h"]
    })


def mae_no_negativo(y_real, y_pred):
    return mean_absolute_error(y_real, np.maximum(y_pred, 0))

