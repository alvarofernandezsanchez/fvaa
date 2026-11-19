"""Carga y agregación de irradiación fotovoltaica."""

from pathlib import Path

import pandas as pd

from .contracts import COLUMNAS_IRRADIACION, validar_irradiacion


def cargar_irradiacion(ruta: str | Path) -> pd.DataFrame:
    """Lee el CSV, convierte los timestamps a UTC y valida la tabla."""
    ruta = Path(ruta)

    if not ruta.is_file():
        raise FileNotFoundError(
            f"No existe un archivo de irradiación en: {ruta}"
        )

    df = pd.read_csv(
        ruta,
        usecols=["timestamp", *COLUMNAS_IRRADIACION],
    )

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="raise",
    )

    validar_irradiacion(df)

    return df


def agregar_irradiacion_15min(
    df: pd.DataFrame,
    cobertura_minima: float = 99.0,
) -> pd.DataFrame:
    """Agrega irradiación de 1 min a cuartos etiquetados por su final.

    El timestamp original marca el final del minuto. Se suman los quince
    valores Wh/m²; la irradiancia media equivalente se expresa en W/m².
    Los intervalos incompletos se conservan con su cobertura.
    """
    if not 0 < cobertura_minima <= 100:
        raise ValueError(
            "La cobertura mínima debe ser mayor que 0 y como máximo 100."
        )

    validar_irradiacion(df)

    datos = df.copy()
    datos["intervalo_fin"] = datos["timestamp"].dt.ceil("15min")
    grupos = datos.groupby("intervalo_fin")

    agregado = grupos[COLUMNAS_IRRADIACION].sum(min_count=15)
    conteos = grupos[COLUMNAS_IRRADIACION].count()
    agregado["minutos_validos"] = conteos.min(axis=1)

    primer_timestamp = datos["timestamp"].iloc[0]
    primer_intervalo_fin = primer_timestamp.ceil("15min")

    if primer_intervalo_fin == primer_timestamp:
        primer_intervalo_fin += pd.Timedelta(minutes=15)

    rejilla = pd.date_range(
        start=primer_intervalo_fin,
        end=datos["timestamp"].iloc[-1].ceil("15min"),
        freq="15min",
        name="timestamp",
    )
    
    agregado = agregado.reindex(rejilla)

    agregado["minutos_validos"] = (
        agregado["minutos_validos"].fillna(0).astype(int)
    )
    agregado["cobertura_pct"] = (
        agregado["minutos_validos"] / 15 * 100
    )
    agregado["intervalo_valido"] = (
        agregado["cobertura_pct"] >= cobertura_minima
    )

    for columna in COLUMNAS_IRRADIACION:
        agregado[f"{columna}_media_w_m2"] = (
            agregado[columna] / 0.25
        ).where(agregado["intervalo_valido"])

    return agregado