
"""Variables explicativas para predecir energía horaria."""

import pandas as pd


def crear_variables_historicas(horas):
    indice = horas.index

    if (
        not isinstance(indice, pd.DatetimeIndex)
        or str(indice.tz) != "UTC"
        or indice.empty
    ):
        raise ValueError("Se necesita un índice horario UTC")

    if (
        not indice.equals(indice.floor("h"))
        or not indice.equals(
            pd.date_range(indice[0], periods=len(indice), freq="h")
        )
    ):
        raise ValueError("La rejilla horaria debe estar completa y ordenada")

    energia = horas["energia_estimada_kwh"]

    variables = pd.DataFrame(index=indice)
    variables["objetivo_kwh"] = energia

    variables["energia_anterior_1h"] = energia.shift(1)
    variables["energia_anterior_2h"] = energia.shift(2)
    variables["energia_anterior_24h"] = energia.shift(24)

    variables["hora"] = indice.hour
    variables["mes"] = indice.month

    return variables


def anadir_irradiacion_historica(variables, irradiacion):
    """Añade irradiación de horas anteriores a la predicción."""

    if not isinstance(irradiacion.index, pd.DatetimeIndex) or str(irradiacion.index.tz) != "UTC":
        raise ValueError("La irradiación debe tener índice UTC")

    if (
        not irradiacion.index.is_unique
        or not irradiacion.index.equals(irradiacion.index.floor("h"))
    ):
        raise ValueError("La irradiación necesita horas únicas y completas")

    salida = variables.copy()
    meteo = irradiacion.reindex(variables.index)

    for columna, nombre in [
        ("GHI_media_w_m2", "ghi"),
        ("Clear sky GHI_media_w_m2", "ghi_despejado")
    ]:
        salida[f"{nombre}_anterior_1h"] = meteo[columna].shift(1)
        salida[f"{nombre}_anterior_24h"] = meteo[columna].shift(24)

    return salida
