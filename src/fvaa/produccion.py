
"""Lectura de potencia y cálculo de energía horaria."""

import pandas as pd
from .contracts import validar_produccion


def cargar_produccion(ruta):
    datos = pd.read_csv(ruta, usecols=["timestamp", "active_power_P1"])
    datos["timestamp"] = pd.to_datetime(datos["timestamp"], utc=True)

    validar_produccion(datos)
    return datos


def agregar_produccion_horaria(datos, cobertura_minima=99):
    validar_produccion(datos)

    if not 0 < cobertura_minima <= 100:
        raise ValueError("Cobertura mínima no válida")

    horas = datos.resample("1h", on="timestamp")["active_power_P1"].agg(
        potencia_media_w="mean",
        registros="count"
    )

    horas["cobertura_pct"] = horas["registros"] / 3600 * 100
    horas["hora_valida"] = horas["cobertura_pct"] >= cobertura_minima

    horas["energia_estimada_kwh"] = (
        horas["potencia_media_w"] / 1000
    ).where(horas["hora_valida"])

    return horas
