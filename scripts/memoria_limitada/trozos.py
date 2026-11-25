import numpy as np
import pandas as pd
import fvaa.produccion as _p


def cargar_produccion_trozos(ruta, filas=1_000_000):
    """Mismo DataFrame que fvaa.produccion.cargar_produccion, pero leyendo por trozos y
    rellenando arrays preasignados (evita duplicar 31 M filas en memoria)."""
    n = sum(len(t) for t in pd.read_csv(ruta, usecols=["active_power_P1"], chunksize=filas))
    ts = np.empty(n, dtype="int64")
    pot = np.empty(n, dtype="float64")
    i = 0
    for trozo in pd.read_csv(ruta, usecols=["timestamp", "active_power_P1"], chunksize=filas):
        t = pd.to_datetime(trozo["timestamp"], utc=True)
        ts[i:i + len(trozo)] = t.astype("int64").to_numpy()
        pot[i:i + len(trozo)] = trozo["active_power_P1"].to_numpy(dtype="float64")
        i += len(trozo)
    datos = pd.DataFrame({
        "timestamp": pd.Series(pd.DatetimeIndex(ts.view("datetime64[ns]"), tz="UTC")),
        "active_power_P1": pot})
    _p.validar_produccion(datos)
    return datos
