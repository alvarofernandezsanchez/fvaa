
import pandas as pd

from fvaa.contracts import COLUMNAS_IRRADIACION
from fvaa.irradiacion import (
    cargar_irradiacion,
    agregar_irradiacion_15min,
    agregar_irradiacion_horaria
)


def crear_datos(fechas):
    return pd.DataFrame({
        "timestamp": fechas,
        **{columna: 1.0 for columna in COLUMNAS_IRRADIACION}
    })


def test_carga_utc(tmp_path):
    fechas = pd.date_range("2020-01-01 00:01", periods=15, freq="min")
    datos = crear_datos(fechas)

    ruta = tmp_path / "irradiacion.csv"
    datos.to_csv(ruta, index=False)

    assert str(cargar_irradiacion(ruta)["timestamp"].dt.tz) == "UTC"


def test_agregacion_15min():
    fechas = pd.date_range(
        "2020-01-01 00:01", periods=15, freq="min", tz="UTC"
    )

    cuartos = agregar_irradiacion_15min(crear_datos(fechas))

    assert cuartos.loc["2020-01-01 00:15", "GHI"] == 15
    assert cuartos.loc["2020-01-01 00:15", "GHI_media_w_m2"] == 60


def test_agregacion_horaria():
    fechas = pd.date_range(
        "2020-01-01 09:01", periods=60, freq="min", tz="UTC"
    )

    horas = agregar_irradiacion_horaria(
        agregar_irradiacion_15min(crear_datos(fechas))
    )

    assert horas.loc["2020-01-01 09:00", "GHI_media_w_m2"] == 60
    assert horas.loc["2020-01-01 09:00", "intervalos_validos"] == 4


def test_hora_incompleta():
    fechas = pd.date_range(
        "2020-01-01 09:01", periods=60, freq="min", tz="UTC"
    )

    datos = crear_datos(fechas).drop(index=34)

    horas = agregar_irradiacion_horaria(
        agregar_irradiacion_15min(datos)
    )

    assert horas.loc["2020-01-01 09:00", "intervalos_validos"] == 3
    assert pd.isna(horas.loc["2020-01-01 09:00", "GHI_media_w_m2"])


def test_frontera_de_ano():
    fechas = pd.date_range(
        "2020-12-31 23:01", periods=60, freq="min", tz="UTC"
    )

    horas = agregar_irradiacion_horaria(
        agregar_irradiacion_15min(crear_datos(fechas))
    )

    assert horas.index[0] == pd.Timestamp("2020-12-31 23:00", tz="UTC")
    assert len(horas) == 1
