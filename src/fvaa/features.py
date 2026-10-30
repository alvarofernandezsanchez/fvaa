"""Construcción de variables para la predicción horaria de producción."""

import numpy as np
import pandas as pd


def crear_variables_historicas(
    df_horario: pd.DataFrame,
) -> pd.DataFrame:
    """Construye el objetivo horario, los retardos y el calendario.

    Cada fila en t predice la energía de [t, t + 1 h).
    Las entradas utilizan únicamente horas terminadas.

    Conserva las filas con valores ausentes y no modifica la entrada.
    """
    if not isinstance(df_horario, pd.DataFrame):
        raise TypeError("La entrada debe ser un pandas.DataFrame.")

    if df_horario.empty:
        raise ValueError("La tabla horaria está vacía.")

    if not df_horario.columns.is_unique:
        raise ValueError("La tabla contiene columnas duplicadas.")

    if "energia_estimada_kwh" not in df_horario.columns:
        raise ValueError("Falta la columna 'energia_estimada_kwh'.")

    indice = df_horario.index

    if not isinstance(indice, pd.DatetimeIndex):
        raise TypeError("El índice debe ser un DatetimeIndex.")

    if indice.tz is None or str(indice.tz) != "UTC":
        raise ValueError("El índice debe utilizar la zona horaria UTC.")

    if indice.hasnans:
        raise ValueError("El índice contiene fechas ausentes.")

    if not indice.is_unique:
        raise ValueError("El índice contiene fechas duplicadas.")

    if not indice.is_monotonic_increasing:
        raise ValueError("El índice debe estar ordenado cronológicamente.")

    if not indice.equals(indice.floor("h")):
        raise ValueError("Cada timestamp debe coincidir con el inicio de una hora.")

    rejilla_esperada = pd.date_range(
        start=indice[0],
        end=indice[-1],
        freq="h",
    )

    if not indice.equals(rejilla_esperada):
        raise ValueError(
            "La rejilla horaria está incompleta. "
            "Conserva las horas ausentes antes de calcular los retardos."
        )

    energia = df_horario["energia_estimada_kwh"]

    if (
        not pd.api.types.is_numeric_dtype(energia)
        or pd.api.types.is_bool_dtype(energia)
        or pd.api.types.is_complex_dtype(energia)
    ):
        raise TypeError("'energia_estimada_kwh' debe contener números reales.")

    observada = energia.dropna()

    if not np.isfinite(observada.to_numpy(dtype=float)).all():
        raise ValueError("La energía contiene valores infinitos.")

    if (observada < 0).any():
        raise ValueError("La energía contiene valores negativos.")

    resultado = pd.DataFrame(index=indice)

    resultado["objetivo_kwh"] = energia
    resultado["energia_anterior_1h"] = energia.shift(1)
    resultado["energia_anterior_2h"] = energia.shift(2)
    resultado["energia_anterior_24h"] = energia.shift(24)

    resultado["hora"] = indice.hour
    resultado["mes"] = indice.month

    return resultado