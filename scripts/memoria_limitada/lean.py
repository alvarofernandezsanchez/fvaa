"""Validacion de produccion con menos memoria: mismas comprobaciones, sin tablas hash de 31 M filas."""
import numpy as np
import pandas as pd
import fvaa.contracts as c
import fvaa.produccion as p

_original = c.validar_produccion


def validar_lean(df):
    if not isinstance(df, pd.DataFrame) or df.empty or not df.columns.is_unique \
            or {"timestamp", "active_power_P1"}.difference(df.columns):
        return _original(df)  # casos de error baratos: usar la funcion original
    f = df["timestamp"]
    if not isinstance(f.dtype, pd.DatetimeTZDtype) or str(f.dt.tz) != "UTC" or f.isna().any():
        return _original(df)
    v = f.to_numpy("datetime64[ns]").view("int64")
    malo = False
    for a in range(0, len(v) - 1, 2_000_000):  # por bloques para ahorrar memoria
        b = v[a:a + 2_000_001]
        if (np.diff(b) <= 0).any() or (np.diff(b // 1_000_000_000) <= 0).any():
            malo = True
            break
    if malo:  # duplicados, desorden o varias lecturas por segundo
        return _original(df)  # recalcula con la funcion original solo si hay un problema (muestras pequenas)
    potencia = df["active_power_P1"]
    if not pd.api.types.is_numeric_dtype(potencia) or pd.api.types.is_bool_dtype(potencia) \
            or pd.api.types.is_complex_dtype(potencia):
        return _original(df)
    obs = potencia.to_numpy(dtype=float)
    obs = obs[~np.isnan(obs)]
    if obs.size == 0 or not np.isfinite(obs).all() or (obs < 0).any():
        return _original(df)


def activar():
    p.validar_produccion = validar_lean
