import pandas as pd

from fvaa.contracts import COLUMNAS_IRRADIACION
from fvaa.irradiacion import (
    agregar_irradiacion_15min,
    cargar_irradiacion,
)


def crear_datos_irradiacion(timestamps):
    return pd.DataFrame({
        "timestamp": timestamps,
        **{
            columna: [1.0] * len(timestamps)
            for columna in COLUMNAS_IRRADIACION
        },
    })


def test_agregar_15_minutos_suma_y_convierte_unidades():
    timestamps = pd.date_range(
        "2020-01-01 00:01",
        periods=15,
        freq="min",
        tz="UTC",
    )
    resultado = agregar_irradiacion_15min(
        crear_datos_irradiacion(timestamps)
    )

    fila = resultado.loc[pd.Timestamp("2020-01-01 00:15", tz="UTC")]

    assert fila["GHI"] == 15.0
    assert fila["GHI_media_w_m2"] == 60.0
    assert fila["minutos_validos"] == 15
    assert fila["cobertura_pct"] == 100.0
    assert bool(fila["intervalo_valido"])


def test_intervalo_incompleto_no_se_marca_como_valido():
    timestamps = pd.date_range(
        "2020-01-01 00:01",
        periods=14,
        freq="min",
        tz="UTC",
    )
    resultado = agregar_irradiacion_15min(
        crear_datos_irradiacion(timestamps)
    )

    fila = resultado.loc[pd.Timestamp("2020-01-01 00:15", tz="UTC")]

    assert fila["minutos_validos"] == 14
    assert fila["cobertura_pct"] < 99.0
    assert not bool(fila["intervalo_valido"])
    assert pd.isna(fila["GHI_media_w_m2"])


def test_cargar_irradiacion_convierte_timestamp_a_utc(tmp_path):
    timestamps = pd.date_range(
        "2020-01-01 00:01",
        periods=15,
        freq="min",
    )
    ruta = tmp_path / "irradiacion.csv"
    crear_datos_irradiacion(timestamps).to_csv(ruta, index=False)

    resultado = cargar_irradiacion(ruta)

    assert str(resultado["timestamp"].dt.tz) == "UTC"