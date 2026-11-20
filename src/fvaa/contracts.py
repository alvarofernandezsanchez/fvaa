"""Validaciones del contrato de entrada de producción fotovoltaica."""

import numpy as np
import pandas as pd


def validar_produccion(df: pd.DataFrame) -> None:
    """Valida producción con timestamps UTC y potencia en W.

    Se permiten columnas adicionales y potencia ausente.
    Los huecos temporales se gestionan durante la agregación.

    Raises:
        TypeError: Si la entrada o los tipos de columnas no son válidos.
        ValueError: Si los datos incumplen el contrato.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("La producción debe ser un pandas.DataFrame.")

    if df.empty:
        raise ValueError("La tabla de producción está vacía.")

    if not df.columns.is_unique:
        raise ValueError("La tabla contiene nombres de columnas duplicados.")

    obligatorias = {"timestamp", "active_power_P1"}
    faltantes = obligatorias.difference(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}."
        )

    fechas = df["timestamp"]
    potencia = df["active_power_P1"]

    # La carga debe convertir las fechas antes de validar.
    if not isinstance(fechas.dtype, pd.DatetimeTZDtype):
        raise TypeError(
            "'timestamp' debe contener fechas con zona horaria. "
            "Convierte con pd.to_datetime(..., utc=True)."
        )

    if str(fechas.dt.tz) != "UTC":
        raise ValueError("'timestamp' debe utilizar la zona horaria UTC.")

    if fechas.isna().any():
        raise ValueError("'timestamp' contiene fechas ausentes.")

    if fechas.duplicated().any():
        raise ValueError("La producción contiene timestamps duplicados.")

    if not fechas.is_monotonic_increasing:
        raise ValueError("Los timestamps deben estar ordenados de menor a mayor.")

    # La cobertura supone una cadencia nominal de un segundo.
    if fechas.dt.floor("s").duplicated().any():
        raise ValueError(
            "Hay varias lecturas dentro de un mismo segundo. "
            "Revisa la cadencia antes de calcular la cobertura."
        )

    if (
        not pd.api.types.is_numeric_dtype(potencia)
        or pd.api.types.is_bool_dtype(potencia)
        or pd.api.types.is_complex_dtype(potencia)
    ):
        raise TypeError("'active_power_P1' debe contener números reales en W.")

    potencia_observada = potencia.dropna()

    if potencia_observada.empty:
        raise ValueError("No hay ninguna lectura de potencia disponible.")

    if not np.isfinite(potencia_observada.to_numpy(dtype=float)).all():
        raise ValueError("'active_power_P1' contiene valores infinitos.")

    if (potencia_observada < 0).any():
        raise ValueError(
            "'active_power_P1' contiene potencia negativa. "
            "Revisa estas lecturas antes de procesar la producción."
        )

COLUMNAS_IRRADIACION = [
    "TOA",
    "Clear sky GHI",
    "Clear sky BHI",
    "Clear sky DHI",
    "Clear sky BNI",
    "GHI",
    "BHI",
    "DHI",
    "BNI",
]


def validar_irradiacion(df: pd.DataFrame) -> None:
    """Valida la estructura y los valores del CSV de irradiación."""

    if not isinstance(df, pd.DataFrame):
        raise TypeError("La irradiación debe ser un pandas.DataFrame.")

    if df.empty:
        raise ValueError("La tabla de irradiación está vacía.")

    requeridas = {"timestamp", *COLUMNAS_IRRADIACION}
    faltantes = requeridas.difference(df.columns)

    if faltantes:
        raise ValueError(
            f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}."
        )

    timestamps = df["timestamp"]

    if not isinstance(timestamps.dtype, pd.DatetimeTZDtype):
        raise TypeError("'timestamp' debe tener zona horaria.")

    if str(timestamps.dt.tz) != "UTC":
        raise ValueError("'timestamp' debe estar en UTC.")

    if timestamps.isna().any():
        raise ValueError("'timestamp' contiene fechas ausentes.")

    if timestamps.duplicated().any():
        raise ValueError("La irradiación contiene timestamps duplicados.")

    if not timestamps.is_monotonic_increasing:
        raise ValueError("Los timestamps deben estar ordenados.")

    if timestamps.dt.floor("min").duplicated().any():
        raise ValueError(
            "Hay más de una lectura dentro de algún minuto."
        )

    for columna in COLUMNAS_IRRADIACION:
        valores = df[columna]

        if (
            not pd.api.types.is_numeric_dtype(valores)
            or pd.api.types.is_bool_dtype(valores)
            or pd.api.types.is_complex_dtype(valores)
        ):
            raise TypeError(f"'{columna}' debe contener valores numéricos.")

        observados = valores.dropna()

        if not np.isfinite(observados.to_numpy(dtype=float)).all():
            raise ValueError(f"'{columna}' contiene valores infinitos.")

        if (observados < 0).any():
            raise ValueError(f"'{columna}' contiene valores negativos.")