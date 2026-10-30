"""Pruebas de agregación horaria de producción fotovoltaica."""

import numpy as np
import pandas as pd

from fvaa.produccion import agregar_produccion_horaria


def test_potencia_constante_se_convierte_en_energia():
    """500 W durante una hora equivalen a 0,5 kWh."""
    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2020-01-01",
            periods=3600,
            freq="s",
            tz="UTC",
        ),
        "active_power_P1": 500.0,
    })

    resultado = agregar_produccion_horaria(df)
    hora = resultado.iloc[0]

    assert len(resultado) == 1
    assert resultado.index[0] == pd.Timestamp("2020-01-01", tz="UTC")
    assert hora["registros"] == 3600
    assert hora["cobertura_pct"] == 100.0
    assert bool(hora["hora_valida"])
    assert hora["energia_estimada_kwh"] == 0.5


def test_cobertura_del_99_por_ciento_es_valida():
    """Exactamente 3.564 lecturas válidas alcanzan el umbral."""
    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2020-01-01",
            periods=3600,
            freq="s",
            tz="UTC",
        ),
        "active_power_P1": 500.0,
    })

    df.loc[3564:, "active_power_P1"] = np.nan

    resultado = agregar_produccion_horaria(df)
    hora = resultado.iloc[0]

    assert hora["registros"] == 3564
    assert hora["cobertura_pct"] == 99.0
    assert bool(hora["hora_valida"])
    assert hora["energia_estimada_kwh"] == 0.5


def test_cobertura_inferior_al_99_por_ciento_no_es_valida():
    """Con 3.563 lecturas la energía debe quedar ausente."""
    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2020-01-01",
            periods=3600,
            freq="s",
            tz="UTC",
        ),
        "active_power_P1": 500.0,
    })

    df.loc[3563:, "active_power_P1"] = np.nan

    resultado = agregar_produccion_horaria(df)
    hora = resultado.iloc[0]

    assert hora["registros"] == 3563
    assert not bool(hora["hora_valida"])
    assert pd.isna(hora["energia_estimada_kwh"])


def test_hora_sin_registros_se_conserva_como_ausente():
    """Una hora vacía se conserva sin convertirla en energía cero."""
    df = pd.DataFrame({
        "timestamp": pd.date_range(
            "2020-01-01",
            periods=3 * 3600,
            freq="s",
            tz="UTC",
        ),
        "active_power_P1": 500.0,
    })

    df = df.loc[df["timestamp"].dt.hour != 1].copy()

    resultado = agregar_produccion_horaria(df)
    hora_vacia = resultado.loc[pd.Timestamp("2020-01-01 01:00", tz="UTC")]

    assert len(resultado) == 3
    assert hora_vacia["registros"] == 0
    assert not bool(hora_vacia["hora_valida"])
    assert pd.isna(hora_vacia["energia_estimada_kwh"])