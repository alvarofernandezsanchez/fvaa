
"""Irradiación de 1 minuto a intervalos de 15 minutos y 1 hora."""

import pandas as pd
from .contracts import COLUMNAS_IRRADIACION, validar_irradiacion


def cargar_irradiacion(ruta):
    datos = pd.read_csv(ruta, usecols=["timestamp", *COLUMNAS_IRRADIACION])
    datos["timestamp"] = pd.to_datetime(datos["timestamp"], utc=True)

    validar_irradiacion(datos)
    return datos


def agregar_irradiacion_15min(datos, cobertura_minima=99):
    validar_irradiacion(datos)

    if not 0 < cobertura_minima <= 100:
        raise ValueError("Cobertura mínima no válida")

    # Los timestamps indican el final de cada minuto.
    fin = datos["timestamp"].dt.ceil("15min")
    grupos = datos.groupby(fin)

    cuartos = grupos[COLUMNAS_IRRADIACION].sum(min_count=15)
    conteos = grupos[COLUMNAS_IRRADIACION].count().min(axis=1)

    indice = pd.date_range(
        fin.iloc[0], fin.iloc[-1], freq="15min", name="timestamp"
    )

    cuartos = cuartos.reindex(indice)
    cuartos["minutos_validos"] = conteos.reindex(indice, fill_value=0)
    cuartos["cobertura_pct"] = cuartos["minutos_validos"] / 15 * 100
    cuartos["intervalo_valido"] = cuartos["cobertura_pct"] >= cobertura_minima

    for columna in COLUMNAS_IRRADIACION:
        cuartos[f"{columna}_media_w_m2"] = (
            cuartos[columna] / 0.25
        ).where(cuartos["intervalo_valido"])

    return cuartos


def agregar_irradiacion_horaria(cuartos):
    """Suma cuatro cuartos válidos y etiqueta la hora al inicio."""

    if not isinstance(cuartos.index, pd.DatetimeIndex) or str(cuartos.index.tz) != "UTC":
        raise ValueError("Los cuartos deben tener un índice UTC")

    if not cuartos.index.is_unique:
        raise ValueError("Hay cuartos de hora duplicados")

    columnas = ["GHI", "Clear sky GHI"]
    validos = cuartos["intervalo_valido"] & cuartos[columnas].notna().all(axis=1)

    horas = cuartos[columnas].where(validos).resample(
        "1h", closed="right", label="left"
    ).sum(min_count=4)

    horas.columns = ["GHI_media_w_m2", "Clear sky GHI_media_w_m2"]

    horas["intervalos_validos"] = validos.resample(
        "1h", closed="right", label="left"
    ).sum()

    horas["cobertura_pct"] = horas["intervalos_validos"] / 4 * 100

    return horas
