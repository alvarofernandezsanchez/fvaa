"""Pruebas de construcción de variables históricas."""

import numpy as np
import pandas as pd
import pytest

from fvaa.features import crear_variables_historicas


def test_objetivo_retardos_y_calendario():
    """Cada entrada corresponde al intervalo histórico esperado."""
    indice = pd.date_range(
        "2020-01-01",
        periods=48,
        freq="h",
        tz="UTC",
        name="timestamp",
    )

    horario = pd.DataFrame(
        {"energia_estimada_kwh": np.arange(48, dtype=float) / 100},
        index=indice,
    )

    resultado = crear_variables_historicas(horario)
    fila = resultado.loc[indice[25]]

    assert len(resultado) == 48
    assert fila["objetivo_kwh"] == 0.25
    assert fila["energia_anterior_1h"] == 0.24
    assert fila["energia_anterior_2h"] == 0.23
    assert fila["energia_anterior_24h"] == 0.01
    assert fila["hora"] == 1
    assert fila["mes"] == 1
    assert pd.isna(resultado.iloc[0]["energia_anterior_1h"])


def test_hora_ausente_no_desplaza_el_historico():
    """Una energía ausente se propaga al retardo correspondiente."""
    indice = pd.date_range(
        "2020-01-01",
        periods=48,
        freq="h",
        tz="UTC",
    )

    horario = pd.DataFrame(
        {"energia_estimada_kwh": np.arange(48, dtype=float) / 100},
        index=indice,
    )

    horario.loc[indice[5], "energia_estimada_kwh"] = np.nan

    resultado = crear_variables_historicas(horario)

    assert len(resultado) == 48
    assert pd.isna(resultado.loc[indice[5], "objetivo_kwh"])
    assert pd.isna(resultado.loc[indice[6], "energia_anterior_1h"])
    assert resultado.loc[indice[6], "energia_anterior_2h"] == 0.04
    assert pd.isna(resultado.loc[indice[29], "energia_anterior_24h"])


def test_rejilla_con_hora_eliminada_se_rechaza():
    """Evita interpretar la fila anterior como la hora anterior."""
    indice = pd.date_range(
        "2020-01-01",
        periods=48,
        freq="h",
        tz="UTC",
    )

    horario = pd.DataFrame(
        {"energia_estimada_kwh": 0.5},
        index=indice,
    ).drop(index=indice[5])

    with pytest.raises(ValueError, match="rejilla horaria"):
        crear_variables_historicas(horario)


def test_energia_futura_no_modifica_entradas_del_presente():
    """Cambiar producción futura no debe cambiar las entradas en t."""
    indice = pd.date_range(
        "2020-01-01",
        periods=48,
        freq="h",
        tz="UTC",
    )

    horario = pd.DataFrame(
        {"energia_estimada_kwh": 0.2},
        index=indice,
    )

    original = crear_variables_historicas(horario)

    modificado = horario.copy()
    modificado.loc[indice[25]:, "energia_estimada_kwh"] = 0.6
    resultado = crear_variables_historicas(modificado)

    entradas = [
        "energia_anterior_1h",
        "energia_anterior_2h",
        "energia_anterior_24h",
        "hora",
        "mes",
    ]

    pd.testing.assert_series_equal(
        original.loc[indice[25], entradas],
        resultado.loc[indice[25], entradas],
    )