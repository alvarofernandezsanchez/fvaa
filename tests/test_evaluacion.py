"""Pruebas de evaluación de predicciones."""

import numpy as np
import pandas as pd
import pytest

from fvaa.evaluacion import calcular_metricas, evaluar_predicciones


def test_metricas_con_errores_conocidos():
    indice = pd.date_range(
        "2020-01-01",
        periods=3,
        freq="h",
        tz="UTC",
    )

    real = pd.Series([0.0, 0.2, 0.4], index=indice)
    prediccion = pd.Series([0.0, 0.1, 0.6], index=indice)

    resultado = calcular_metricas(real, prediccion)

    # Errores absolutos: 0, 0.1 y 0.2.
    assert resultado["MAE_kwh"] == pytest.approx(0.1)
    assert resultado["RMSE_kwh"] == pytest.approx(
        np.sqrt((0.1**2 + 0.2**2) / 3)
    )


def test_indices_desalineados_se_rechazan():
    real = pd.Series([0.1, 0.2], index=[0, 1])
    prediccion = pd.Series([0.1, 0.2], index=[1, 0])

    with pytest.raises(ValueError, match="índices"):
        calcular_metricas(real, prediccion)


@pytest.mark.parametrize("valor_invalido", [np.nan, np.inf, -np.inf])
def test_predicciones_no_finitas_se_rechazan(valor_invalido):
    real = pd.Series([0.1, 0.2])
    prediccion = pd.Series([0.1, valor_invalido])

    with pytest.raises(ValueError):
        calcular_metricas(real, prediccion)


def test_evalua_varios_modelos():
    real = pd.Series([0.0, 0.2, 0.4])

    predicciones = pd.DataFrame({
        "Perfecto": [0.0, 0.2, 0.4],
        "Constante": [0.2, 0.2, 0.2],
    })

    resultado = evaluar_predicciones(real, predicciones)

    assert resultado.index.name == "modelo"
    assert resultado.loc["Perfecto", "MAE_kwh"] == 0.0
    assert resultado.loc["Perfecto", "RMSE_kwh"] == 0.0
    assert resultado.loc["Constante", "MAE_kwh"] == pytest.approx(
        0.4 / 3
    )