
import numpy as np
import pandas as pd
import pytest

from fvaa.features import crear_variables_historicas, anadir_irradiacion_historica


def test_retardos_de_produccion():
    idx = pd.date_range("2020-01-01", periods=50, freq="h", tz="UTC")
    datos = pd.DataFrame({
        "energia_estimada_kwh": np.arange(50) / 100
    }, index=idx)

    variables = crear_variables_historicas(datos)

    assert variables.loc[idx[25], "energia_anterior_1h"] == 0.24
    assert variables.loc[idx[25], "energia_anterior_24h"] == 0.01


def test_no_desplazar_horas_ausentes():
    idx = pd.date_range("2020-01-01", periods=50, freq="h", tz="UTC")
    datos = pd.DataFrame({"energia_estimada_kwh": 0.2}, index=idx)

    datos.loc[idx[5], "energia_estimada_kwh"] = np.nan
    variables = crear_variables_historicas(datos)

    assert pd.isna(variables.loc[idx[6], "energia_anterior_1h"])

    with pytest.raises(ValueError, match="rejilla horaria"):
        crear_variables_historicas(datos.drop(index=idx[5]))


def test_irradiacion_historica_y_sin_fuga():
    idx = pd.date_range("2020-01-01", periods=50, freq="h", tz="UTC")
    datos = pd.DataFrame({"energia_estimada_kwh": 0.2}, index=idx)
    variables = crear_variables_historicas(datos)

    meteo = pd.DataFrame({
        "GHI_media_w_m2": np.arange(50),
        "Clear sky GHI_media_w_m2": np.arange(50) + 100
    }, index=idx)

    original = anadir_irradiacion_historica(variables, meteo)

    assert original.loc[idx[25], "ghi_anterior_1h"] == 24
    assert original.loc[idx[25], "ghi_anterior_24h"] == 1

    meteo.loc[idx[25]:, "GHI_media_w_m2"] = 1e6
    cambiado = anadir_irradiacion_historica(variables, meteo)

    assert cambiado.loc[idx[25], "ghi_anterior_1h"] == 24


def test_irradiacion_hueco_no_desplaza_retrasos():
    idx = pd.date_range("2020-01-01", periods=50, freq="h", tz="UTC")

    variables = crear_variables_historicas(
        pd.DataFrame({"energia_estimada_kwh": 0.2}, index=idx)
    )

    meteo = pd.DataFrame({
        "GHI_media_w_m2": 10.0,
        "Clear sky GHI_media_w_m2": 20.0
    }, index=idx).drop(idx[5])

    completo = anadir_irradiacion_historica(variables, meteo)

    assert pd.isna(completo.loc[idx[6], "ghi_anterior_1h"])
