"""Separación cronológica de datos para entrenamiento y evaluación."""

import pandas as pd


def separar_temporalmente(
    df: pd.DataFrame,
    inicio_validacion: str,
    inicio_test: str,
) -> dict[str, pd.DataFrame]:
    """Divide la tabla en tres periodos cronológicos no solapados.

    Entrenamiento: fechas anteriores al inicio de validación.
    Validación: desde su inicio hasta el inicio de test, excluido.
    Test: desde su inicio en adelante.

    No elimina ausencias ni modifica la tabla original.
    """
    if not isinstance(df, pd.DataFrame):
        raise TypeError("La entrada debe ser un pandas.DataFrame.")

    if df.empty:
        raise ValueError("La tabla está vacía.")

    indice = df.index

    if not isinstance(indice, pd.DatetimeIndex):
        raise TypeError("El índice debe ser un DatetimeIndex.")

    if indice.tz is None or str(indice.tz) != "UTC":
        raise ValueError("El índice debe utilizar UTC.")

    if indice.hasnans:
        raise ValueError("El índice contiene fechas ausentes.")

    if not indice.is_unique:
        raise ValueError("El índice contiene fechas duplicadas.")

    if not indice.is_monotonic_increasing:
        raise ValueError("El índice debe estar ordenado cronológicamente.")

    fecha_val = pd.Timestamp(inicio_validacion)
    fecha_test = pd.Timestamp(inicio_test)

    # Las fechas sin zona horaria se interpretan como UTC.
    fecha_val = (
        fecha_val.tz_localize("UTC")
        if fecha_val.tzinfo is None
        else fecha_val.tz_convert("UTC")
    )
    fecha_test = (
        fecha_test.tz_localize("UTC")
        if fecha_test.tzinfo is None
        else fecha_test.tz_convert("UTC")
    )

    if pd.isna(fecha_val) or pd.isna(fecha_test):
        raise ValueError("Las fechas de corte no pueden ser ausentes.")

    if fecha_val >= fecha_test:
        raise ValueError(
            "El inicio de validación debe ser anterior al inicio de test."
        )

    particiones = {
        "train": df.loc[indice < fecha_val].copy(),
        "val": df.loc[
            (indice >= fecha_val) & (indice < fecha_test)
        ].copy(),
        "test": df.loc[indice >= fecha_test].copy(),
    }

    for nombre, tabla in particiones.items():
        if tabla.empty:
            raise ValueError(
                f"La partición '{nombre}' está vacía. "
                "Revisa las fechas de corte y el periodo disponible."
            )

    return particiones