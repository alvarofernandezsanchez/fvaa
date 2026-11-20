"""Comprueba las muestras del notebook sin cargar los CSV anuales ni ajustar modelos."""

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd

from fvaa.features import crear_variables_historicas, anadir_irradiacion_historica


def test_muestras_comunes_24h_y_cortes_temporales():
    notebook = json.loads((
        Path(__file__).resolve().parents[1] / "notebooks/FVAA_fase1.ipynb"
    ).read_text(encoding="utf-8"))
    indice = pd.date_range("2020-01-01", periods=240, freq="h", tz="UTC")
    produccion = pd.DataFrame({"energia_estimada_kwh": 1.0}, index=indice)
    produccion.loc[indice[145], "energia_estimada_kwh"] = np.nan
    irradiacion = pd.DataFrame({
        "GHI_media_w_m2": 10.0, "Clear sky GHI_media_w_m2": 20.0
    }, index=indice)
    entorno = dict(
        pd=pd, produccion=produccion, irradiacion=irradiacion,
        crear_variables_historicas=crear_variables_historicas,
        anadir_irradiacion_historica=anadir_irradiacion_historica,
        INICIO_VAL=indice[80], INICIO_TEST=indice[140]
    )
    exec("".join(notebook["cells"][5]["source"]), entorno)
    codigo = ast.parse("".join(notebook["cells"][9]["source"]))
    dividir = next(n for n in codigo.body if isinstance(n, ast.FunctionDef) and n.name == "dividir")
    exec(compile(ast.Module(body=[dividir], type_ignores=[]), "notebook", "exec"), entorno)

    for objetivo in ["perfil_24h", "total_24h"]:
        y = entorno["objetivos"][objetivo]
        tr, va, te = entorno["dividir"](y, 24, entorno["nivel1"] + entorno["meteo"])
        # En t=160 las entradas 1/2/24 h son válidas, pero falta parte del día anterior.
        assert entorno["X"].loc[indice[160]].notna().all()
        assert not te.loc[indice[160]]
        assert te.loc[indice[180]]
        assert entorno["referencias"][objetivo].loc[tr | va | te].notna().all().all()
        assert (indice[tr] + pd.Timedelta(hours=24) <= indice[80]).all()
        assert (indice[va] + pd.Timedelta(hours=24) <= indice[140]).all()


def test_variables_historicas_no_cambian_con_presente_o_futuro():
    indice = pd.date_range("2020-01-01", periods=72, freq="h", tz="UTC")
    produccion = pd.DataFrame({"energia_estimada_kwh": np.arange(72)}, index=indice)
    irradiacion = pd.DataFrame({
        "GHI_media_w_m2": np.arange(72),
        "Clear sky GHI_media_w_m2": np.arange(72) + 100
    }, index=indice)
    original = anadir_irradiacion_historica(crear_variables_historicas(produccion), irradiacion)
    produccion.loc[indice[48]:] = 99999
    irradiacion.loc[indice[48]:] = 99999
    cambiado = anadir_irradiacion_historica(crear_variables_historicas(produccion), irradiacion)
    pd.testing.assert_series_equal(
        original.drop(columns="objetivo_kwh").loc[indice[48]],
        cambiado.drop(columns="objetivo_kwh").loc[indice[48]]
    )
