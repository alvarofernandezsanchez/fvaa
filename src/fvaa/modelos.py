"""Estimadores y correcciones utilizados en PR20–2020."""
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error


ENTRADAS = ["energia_anterior_1h", "energia_anterior_2h", "energia_anterior_24h", "hora", "mes"]
OBJETIVO = "objetivo_kwh"


def crear_modelo(tipo, parametros):
    clases = {"lineal": LinearRegression, "rf": RandomForestRegressor,
              "gb": GradientBoostingRegressor}
    if tipo not in clases:
        raise ValueError(f"Tipo de modelo desconocido: {tipo}")
    return clases[tipo](**parametros)


def predecir(modelo, X, minimo_cero=False):
    """Devuelve predicción original y aplicada, conservando fechas."""
    original = pd.Series(modelo.predict(X), index=X.index)
    return original, original.clip(lower=0) if minimo_cero else original.copy()


def referencias(X):
    return pd.DataFrame({"persistencia": X["energia_anterior_1h"],
                         "persistencia_diaria": X["energia_anterior_24h"]})


def mae_no_negativo(y_real, y_pred):
    """Scorer GB del notebook: evalúa después de aplicar mínimo cero."""
    return mean_absolute_error(y_real, np.maximum(y_pred, 0))
