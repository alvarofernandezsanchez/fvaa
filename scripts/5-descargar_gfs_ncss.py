"""Descarga DSWRF GFS (celda 32,75 N, 343 E) de GDEX por NCSS, sin GRIB globales.

Guarda promedios nativos (sin transformar) en data/raw/gfs_36h/nativos_dswrf.csv.
Es reanudable: no repite las peticiones ya guardadas.
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import pandas as pd

BASE = "https://tds.gdex.ucar.edu/thredds/ncss/grid/files/d084001"
LAT, LON = 32.75, 343.0


def peticiones():
    """2020: plazos nuevos 27-36 h. 31/12/2019: 3-36 h, por la latencia al inicio del año."""
    for emision in pd.date_range("2019-12-31 00:00", "2020-12-31 18:00", freq="6h", tz="UTC"):
        if emision.year == 2019:
            plazos = range(3, 37, 3)
        else:
            plazos = range(27, 37, 3)
        for plazo in plazos:
            yield emision, plazo


def descargar(peticion):
    emision, plazo = peticion
    horas = 3 if plazo % 6 == 3 else 6  # f003, f009, ... son medias de 3 h; f006, f012, ... de 6 h
    variable = f"Downward_Short-Wave_Radiation_Flux_surface_{horas}_Hour_Average"
    archivo = f"gfs.0p25.{emision:%Y%m%d%H}.f{plazo:03d}.grib2"
    url = (f"{BASE}/{emision:%Y}/{emision:%Y%m%d}/{archivo}"
           f"?var={variable}&latitude={LAT}&longitude={LON - 360}&accept=csv")
    for intento in range(4):
        try:
            with urlopen(url, timeout=60) as r:
                tabla = pd.read_csv(StringIO(r.read().decode()))
            break
        except HTTPError as error:
            if error.code == 429:  # Límite del servidor: parar y no insistir.
                return {"emision_utc": emision, "plazo": plazo, "error": "429",
                        "retry_after": error.headers.get("Retry-After")}
            fallo = error
            time.sleep(2 * (intento + 1))
        except Exception as error:
            fallo = error
            time.sleep(2 * (intento + 1))
    else:
        return {"emision_utc": emision, "plazo": plazo, "error": str(fallo)}
    if len(tabla) != 1:
        return {"emision_utc": emision, "plazo": plazo, "error": f"filas={len(tabla)}"}
    centro = pd.to_datetime(tabla["time"].iloc[0], utc=True)  # NCSS devuelve el centro del intervalo
    inicio = (centro - pd.Timedelta(hours=horas / 2) - emision) / pd.Timedelta(hours=1)
    fin = (centro + pd.Timedelta(hours=horas / 2) - emision) / pd.Timedelta(hours=1)
    if fin != plazo or inicio != plazo - horas:
        return {"emision_utc": emision, "plazo": plazo, "error": f"intervalo {inicio}-{fin}"}
    return {"emision_utc": emision, "plazo": plazo, "inicio": int(inicio), "fin": int(fin),
            "valor": float(tabla.iloc[0, -1])}


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--salida", type=Path, default=Path("data/raw/gfs_36h/nativos_dswrf.csv"))
    p.add_argument("--max-segundos", type=int, default=90, help="Tiempo máximo de esta ejecución")
    p.add_argument("--hilos", type=int, default=2, help="Concurrencia baja: GDEX limita peticiones")
    args = p.parse_args()
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    previo = pd.read_csv(args.salida, parse_dates=["emision_utc"]) if args.salida.is_file() else pd.DataFrame(
        columns=["emision_utc", "plazo", "inicio", "fin", "valor"])
    hechos = set(zip(pd.to_datetime(previo.emision_utc, utc=True), previo.plazo))
    pendientes = [x for x in peticiones() if x not in hechos]
    print(f"Pendientes: {len(pendientes)} de {len(hechos) + len(pendientes)}")
    inicio_t = time.time()
    nuevas, errores = [], []
    with ThreadPoolExecutor(args.hilos) as pool:
        for lote in range(0, len(pendientes), args.hilos * 2):
            if time.time() - inicio_t > args.max_segundos:
                break
            ok = []
            for r in pool.map(descargar, pendientes[lote:lote + args.hilos * 2]):
                (errores if "error" in r else ok).append(r)
            nuevas += ok
            if ok:  # Guardar cada lote para poder reanudar.
                previo = pd.concat([previo, pd.DataFrame(ok)], ignore_index=True)
                previo.to_csv(args.salida, index=False)
            if any(e.get("error") == "429" for e in errores):
                print("Límite 429 de GDEX: parada. Retry-After:", [e.get("retry_after") for e in errores][:1])
                break
    print(f"Guardadas: {len(nuevas)}; con error: {len(errores)}")
    for e in errores[:5]:
        print(e)
