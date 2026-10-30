"""Rechazo explícito de entradas que invalidarían cobertura o energía."""
import numpy as np
import pandas as pd
import pytest
from fvaa.contracts import validar_produccion


def tabla():
    return pd.DataFrame({"timestamp":pd.date_range("2020-01-01",periods=3,freq="s",tz="UTC"),
                         "active_power_P1":[0.,10.,20.]})


@pytest.mark.parametrize("caso",["naive","otra_zona","nat","desorden","subsegundos","negativo","infinito","bool"])
def test_contratos_rechazan_entradas_invalidas(caso):
    df=tabla()
    if caso=="naive":df["timestamp"]=df.timestamp.dt.tz_localize(None)
    elif caso=="otra_zona":df["timestamp"]=df.timestamp.dt.tz_convert("Europe/Madrid")
    elif caso=="nat":df.loc[0,"timestamp"]=pd.NaT
    elif caso=="desorden":df=df.iloc[::-1]
    elif caso=="subsegundos":df.loc[1,"timestamp"]=df.loc[0,"timestamp"]+pd.Timedelta(milliseconds=500)
    elif caso=="negativo":df.loc[0,"active_power_P1"]=-1
    elif caso=="infinito":df.loc[0,"active_power_P1"]=np.inf
    elif caso=="bool":df["active_power_P1"]=True
    with pytest.raises((ValueError,TypeError)):validar_produccion(df)


def test_ausencia_de_potencia_permitida_no_es_cero():
    df=tabla();df.loc[1,"active_power_P1"]=np.nan
    validar_produccion(df)
    assert pd.isna(df.loc[1,"active_power_P1"])
