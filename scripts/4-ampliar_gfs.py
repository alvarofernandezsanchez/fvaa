"""Añade los promedios GFS nativos descargados por NCSS al CSV existente."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd

LAT, LON = 32.75, 343.0


def leer_nativos(ruta):
    """Promedios nativos descargados con scripts/descargar_gfs_ncss.py (sin transformar)."""
    nativos = pd.read_csv(ruta, usecols=['emision_utc', 'inicio', 'fin', 'valor'])
    nativos['emision_utc'] = pd.to_datetime(nativos['emision_utc'], utc=True)
    if nativos.empty or not np.isfinite(nativos['valor']).all():
        raise ValueError('Promedios DSWRF ausentes o no finitos')
    return nativos


def convertir_3h(nativos):
    filas = []
    for emision, datos in nativos.groupby('emision_utc'):
        datos = datos.drop_duplicates()
        if datos.duplicated(['inicio', 'fin']).any():
            raise ValueError(f'Promedios contradictorios: {emision}')
        valores = datos.set_index(['inicio', 'fin']).valor
        for (inicio, fin), valor in valores.items():
            if inicio < 0 or fin > 36 or inicio % 3 or fin % 3:
                raise ValueError('Intervalo nativo no compatible')
            if fin - inicio == 3:
                origen = 'GFS directo'
            elif fin - inicio == 6 and (inicio, inicio + 3) in valores.index:
                valor = 2 * valor - valores.loc[(inicio, inicio + 3)]
                origen = 'derivado de productos GFS de 3 h y 6 h'
                inicio += 3
                if (inicio, fin) in valores.index:
                    continue  # Preferir promedio directo si existe.
            else:
                raise ValueError(f'No se puede reconstruir el intervalo {inicio}-{fin} de {emision}')
            filas.append((emision, fin, emision + pd.Timedelta(hours=inicio),
                          emision + pd.Timedelta(hours=fin), 3, LAT, LON, valor, origen))
    return pd.DataFrame(filas, columns=['emision_utc', 'plazo_horas', 'inicio_validez_utc',
        'fin_validez_utc', 'duracion_intervalo_h', 'lat', 'lon', 'dswrf_media_w_m2', 'origen'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('csv_original', type=Path)
    p.add_argument('nativos_csv', type=Path)
    p.add_argument('csv_salida', type=Path)
    args = p.parse_args()
    if args.csv_salida.resolve() == args.csv_original.resolve():
        p.error('La salida debe ser distinta del CSV original')
    original = pd.read_csv(args.csv_original)
    original = original.loc[(original.lat == LAT) & (original.lon == LON)].copy()
    for c in ['emision_utc', 'inicio_validez_utc', 'fin_validez_utc']:
        original[c] = pd.to_datetime(original[c], utc=True)
    nuevos = convertir_3h(leer_nativos(args.nativos_csv))
    # Conservar el CSV del compañero y añadir únicamente intervalos ausentes.
    claves = ['emision_utc', 'inicio_validez_utc']
    salida = pd.concat([original, nuevos], ignore_index=True)
    if salida.groupby(claves).dswrf_media_w_m2.agg(lambda x: x.max() - x.min()).gt(1e-5).any():
        raise ValueError('Los nuevos datos contradicen los originales')
    salida = salida.drop_duplicates(claves).sort_values(claves)
    args.csv_salida.parent.mkdir(parents=True, exist_ok=True)
    salida.to_csv(args.csv_salida, index=False)
    print(salida.groupby('plazo_horas').size().to_string())
    print('Guardado:', args.csv_salida)
