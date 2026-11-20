"""Métricas para evaluar predicciones de energía fotovoltaica."""

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error


def calcular_metricas(
    y_real: pd.Series,
    y_pred: pd.Series,
) -> dict[str, float]:
    """Calcula MAE y RMSE en kWh sobre observaciones alineadas.

    No elimina ausencias ni modifica las predicciones.
    """
    if not isinstance(y_real, pd.Series) or not isinstance(y_pred, pd.Series):
        raise TypeError("Los valores reales y predichos deben ser pd.Series.")

    if y_real.empty:
        raise ValueError("No hay observaciones para evaluar.")

    if not y_real.index.equals(y_pred.index):
        raise ValueError(
            "Los índices reales y predichos deben coincidir y estar "
            "en el mismo orden."
        )

    if not y_real.index.is_unique:
        raise ValueError("El índice de evaluación contiene duplicados.")

    for nombre, serie in {"y_real": y_real, "y_pred": y_pred}.items():
        if (
            not pd.api.types.is_numeric_dtype(serie)
            or pd.api.types.is_bool_dtype(serie)
            or pd.api.types.is_complex_dtype(serie)
        ):
            raise TypeError(f"'{nombre}' debe contener números reales.")

        if serie.isna().any():
            raise ValueError(f"'{nombre}' contiene valores ausentes.")

        if not np.isfinite(serie.to_numpy(dtype=float)).all():
            raise ValueError(f"'{nombre}' contiene valores infinitos.")

    return {
        "MAE_kwh": float(mean_absolute_error(y_real, y_pred)),
        "RMSE_kwh": float(np.sqrt(mean_squared_error(y_real, y_pred))),
    }


def evaluar_predicciones(
    y_real: pd.Series,
    predicciones: pd.DataFrame,
) -> pd.DataFrame:
    """Evalúa una columna por modelo sobre las mismas observaciones."""
    if not isinstance(predicciones, pd.DataFrame):
        raise TypeError("'predicciones' debe ser un pandas.DataFrame.")

    if predicciones.shape[1] == 0:
        raise ValueError("No hay modelos para evaluar.")

    if not predicciones.columns.is_unique:
        raise ValueError("Los nombres de los modelos deben ser únicos.")

    resultados = {
        nombre: calcular_metricas(y_real, predicciones[nombre])
        for nombre in predicciones.columns
    }

    tabla = pd.DataFrame.from_dict(resultados, orient="index")
    tabla.index.name = "modelo"

    return tabla