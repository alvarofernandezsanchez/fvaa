"""Regresión de serialización CSV: precisión e índices, sin datos reales ni ajustes."""
import csv
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fvaa.cuantiles import evaluar_cuantiles
from fvaa.evaluacion import evaluar_predicciones
from fvaa.pipeline import (exportar, guardar_json, huella, leer_json,
                           leer_particion, exportar_probabilistico)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("particion,inicio", [
    ("train", "2020-08-31 20:00"),
    ("val", "2020-09-01"),
    ("test", "2020-11-01"),
])
def test_precision_exacta_csv_particiones(tmp_path, monkeypatch, particion, inicio):
    """Valores sensibles en pandas 3.0.6; no se presupone el fallo de todo lector futuro.

    Además de igualdad exacta se vigila el contrato round_trip: su retirada debe
    fallar incluso si otra versión de pandas ya preserva estos valores por defecto.
    """
    config = leer_json(ROOT / "configs/pr20_2020.json")
    valores = np.array([0.12345678901234566, 0.30000000000000004,
                        0.02741285661151851, 0.07551572766027369], dtype="float64")
    original = pd.DataFrame(
        {nombre: np.roll(valores, i)
         for i, nombre in enumerate([config["objetivo"], *config["entradas"]])},
        index=pd.date_range(inicio, periods=4, freq="h", tz="UTC", name="timestamp"),
    )
    # Mismo mecanismo de escritura y manifiesto que preparar().
    exportar(original, tmp_path, particion)
    guardar_json(tmp_path / "config.json", config)
    guardar_json(tmp_path / "preparacion.json", {
        particion: huella(tmp_path / (particion + ".csv"))})
    lector_real = pd.read_csv
    llamadas = []

    def lector_vigilado(*args, **kwargs):
        assert kwargs.get("float_precision") == "round_trip"
        llamadas.append(Path(args[0]).name)
        return lector_real(*args, **kwargs)

    monkeypatch.setattr("fvaa.pipeline.pd.read_csv", lector_vigilado)
    recuperada = leer_particion(tmp_path, particion, config)
    assert llamadas == [particion + ".csv"]
    pd.testing.assert_frame_equal(original, recuperada, check_exact=True, check_freq=False)
    pd.testing.assert_index_equal(original.index, recuperada.index, exact=True)
    np.testing.assert_array_equal(original.to_numpy(), recuperada.to_numpy())


def cabecera(ruta):
    with ruta.open(encoding="utf-8", newline="") as archivo:
        return next(csv.reader(archivo))


def test_encabezados_temporales_grupos_modelos_y_cuantiles(tmp_path):
    idx = pd.date_range("2020-09-01", periods=3, freq="h", tz="UTC", name="timestamp")
    real = pd.Series([0.0, 0.2, 0.4], index=idx)
    q = pd.DataFrame({"q10": [0., .1, .2], "q50": [0., .2, .4],
                      "q90": [.1, .3, .5]}, index=idx)
    exportar_probabilistico(real, q, q, real, tmp_path, "cuantiles")
    grupos, marginal = evaluar_cuantiles(real, q, real)
    assert grupos.index.name == "grupo"
    assert marginal.index.name == "cuantil"
    assert cabecera(tmp_path / "cuantiles_cobertura.csv")[0] == "grupo"
    assert cabecera(tmp_path / "cuantiles_calibracion_pinball.csv")[0] == "cuantil"
    assert cabecera(tmp_path / "cuantiles_originales.csv")[0] == "timestamp"
    assert cabecera(tmp_path / "cuantiles_cruces.csv")[0] == "timestamp"
    assert cabecera(tmp_path / "cuantiles_resumen_originales.csv")[0] == "estadistico"
    modelos = evaluar_predicciones(real, real.to_frame("referencia"))
    exportar(modelos, tmp_path, "metricas")
    assert cabecera(tmp_path / "metricas.csv")[0] == "modelo"
    # Otros nombres explícitos tampoco se sustituyen por timestamp.
    exportar(pd.DataFrame({"coeficiente": [1.]}, index=pd.Index(["hora"], name="variable")),
             tmp_path, "coeficientes")
    assert cabecera(tmp_path / "coeficientes.csv")[0] == "variable"
