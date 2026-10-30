"""Carga y agregación horaria de producción fotovoltaica."""

from pathlib import Path

import pandas as pd

from .contracts import validar_produccion


def cargar_produccion(ruta: str | Path) -> pd.DataFrame:
    """Lee la producción, convierte las fechas a UTC y valida la tabla."""
    ruta = Path(ruta)

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe un archivo de producción en: {ruta}"
        )

    df = pd.read_csv(
        ruta,
        usecols=["timestamp", "active_power_P1"],
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="raise",
    )

    validar_produccion(df)

    return df


def agregar_produccion_horaria(
    df: pd.DataFrame,
    cobertura_minima: float = 99.0,
) -> pd.DataFrame:
    """Agrega lecturas en intervalos [t, t + 1 h), etiquetados en t.

    La energía se estima suponiendo que la potencia media observada
    representa toda la hora. Las horas con cobertura insuficiente
    conservan su fila y tienen energía ausente.
    """
    if not 0 < cobertura_minima <= 100:
        raise ValueError(
            "La cobertura mínima debe ser mayor que 0 y como máximo 100."
        )

    validar_produccion(df)

    horario = (
        df.resample(
            "1h",
            on="timestamp",
            closed="left",
            label="left",
        )["active_power_P1"]
        .agg(
            potencia_media_w="mean",
            registros="count",
        )
    )

    horario["cobertura_pct"] = horario["registros"] / 3600 * 100

    horario["hora_valida"] = (
        horario["cobertura_pct"] >= cobertura_minima
    )

    horario["energia_estimada_kwh"] = (
        horario["potencia_media_w"] / 1000
    ).where(horario["hora_valida"])

    return horario