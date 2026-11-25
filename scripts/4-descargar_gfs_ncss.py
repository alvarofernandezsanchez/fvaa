"""Descarga DSWRF GFS (celda 32,75 N, 343 E) de GDEX por NCSS, sin GRIB globales.

Guarda promedios nativos (sin transformar) en data/raw/gfs_36h/nativos_dswrf.csv.
Es reanudable: no repite las peticiones ya guardadas.
"""
import argparse
import atexit
import os
import time
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen
import pandas as pd

BASE = "https://tds.gdex.ucar.edu/thredds/ncss/grid/files/d084001"
LAT, LON = 32.75, 343.0
PAUSA = 2  # segundos entre peticiones de cada hilo


def bloquear(ruta):
    """Una sola descarga a la vez: crea un archivo de bloqueo con el PID o aborta si ese PID sigue vivo."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(2):
        try:
            fd = os.open(ruta, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                os.kill(int(ruta.read_text()), 0)
            except (ValueError, ProcessLookupError, FileNotFoundError):
                ruta.unlink(missing_ok=True)  # Bloqueo huérfano de un proceso que ya no existe.
                continue
            raise SystemExit(f"Ya hay una descarga en marcha (bloqueo {ruta}).")
        with os.fdopen(fd, "w") as f:
            f.write(str(os.getpid()))
        atexit.register(lambda: ruta.unlink(missing_ok=True))
        return
    raise SystemExit(f"No se pudo crear el bloqueo {ruta}.")


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
    try:  # Sin reintentos automáticos: cualquier error se devuelve y detiene la descarga.
        with urlopen(url, timeout=60) as r:
            tabla = pd.read_csv(StringIO(r.read().decode()))
    except HTTPError as error:
        return {"emision_utc": emision, "plazo": plazo, "error": str(error.code),
                "retry_after": error.headers.get("Retry-After")}
    except Exception as error:
        return {"emision_utc": emision, "plazo": plazo, "error": str(error)}
    time.sleep(PAUSA)
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
    p.add_argument("--hilos", type=int, default=1, help="Concurrencia baja: GDEX limita peticiones")
    args = p.parse_args()
    bloquear(args.salida.with_suffix(".lock"))
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
            if errores:  # Primer error (429, 403, 5xx, desafío...): parar sin insistir.
                print("Error del servidor: parada. Retry-After:", [e.get("retry_after") for e in errores][:1])
                break
    print(f"Guardadas: {len(nuevas)}; con error: {len(errores)}")
    for e in errores[:5]:
        print(e)
