"""Lee los GRIB2 de un solo punto entregados por GDEX (ds084.1, DSWRF) y escribe el CSV de promedios nativos.

Lector mínimo, sin ecCodes: solo acepta lo que se pidió (rejilla lat/lon de 1 punto, producto 4.8 de
promedio, DSWRF suelo, empaquetado simple, sin bitmap) y se detiene si algo no coincide.
Uso: python scripts/leer_gdex_grib2.py <carpeta_con_grib2> data/raw/gfs_36h/nativos_dswrf.csv
Los archivos se descargan con la API de GDEX (solicitudes 996991 y 996992, ver README).
"""
import argparse
import re
import struct
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

LAT, LON = 32.75, 343.0


def secciones(datos):
    pos, sec = 16, {}
    while datos[pos:pos + 4] != b'7777':
        largo = struct.unpack('>I', datos[pos:pos + 4])[0]
        sec[datos[pos + 4]] = datos[pos:pos + largo]
        pos += largo
    return sec


def firmado(valor):  # entero con signo y magnitud de GRIB2 (2 bytes)
    return -(valor & 0x7fff) if valor & 0x8000 else valor


def leer(ruta):
    datos = ruta.read_bytes()
    nombre = re.search(r'\.(\d{10})\.f(\d{3})\.grib2$', ruta.name)
    emision = datetime.strptime(nombre.group(1), '%Y%m%d%H')
    plazo = int(nombre.group(2))
    s = secciones(datos)
    s1, s3, s4, s5, s6, s7 = (s[i] for i in (1, 3, 4, 5, 6, 7))
    esperado = {
        'disciplina': (datos[6], 0), 'edicion': (datos[7], 2), 'puntos': (struct.unpack('>I', s3[6:10])[0], 1),
        'rejilla lat/lon': (struct.unpack('>H', s3[12:14])[0], 0),
        'lat': (struct.unpack('>i', s3[46:50])[0] / 1e6, LAT), 'lon': (struct.unpack('>i', s3[50:54])[0] / 1e6, LON),
        'producto 4.8': (struct.unpack('>H', s4[7:9])[0], 8), 'categoria': (s4[9], 4), 'parametro DSWRF': (s4[10], 192),
        'superficie': (s4[22], 1), 'unidad tiempo horas': (s4[17], 1), 'estadistico promedio': (s4[46], 0),
        'unidad intervalo horas': (s4[48], 1), 'empaquetado simple': (struct.unpack('>H', s5[9:11])[0], 0),
        'sin bitmap': (s6[5], 255), 'un solo intervalo': (s4[41], 1)}
    for clave, (obtenido, correcto) in esperado.items():
        if obtenido != correcto:
            raise ValueError(f'{ruta.name}: {clave} = {obtenido}, se esperaba {correcto}')
    inicio = struct.unpack('>I', s4[18:22])[0]
    largo = struct.unpack('>I', s4[49:53])[0]
    fin_gribe = datetime(*struct.unpack('>HBBBBB', s4[34:41]))
    if largo not in (3, 6):
        raise ValueError(f'{ruta.name}: se esperaba un promedio de 3 h o de 6 h, no de {largo} h')
    if fin_gribe != emision + timedelta(hours=plazo) or inicio + largo != plazo:
        raise ValueError(f'{ruta.name}: intervalo inconsistente con el nombre')
    ref = struct.unpack('>f', s5[11:15])[0]
    e, d, bits = firmado(struct.unpack('>H', s5[15:17])[0]), firmado(struct.unpack('>H', s5[17:19])[0]), s5[19]
    x = int.from_bytes(s7[5:], 'big') >> (8 * len(s7[5:]) - bits) if bits else 0
    return emision, inicio, plazo, (ref + x * 2.0 ** e) / 10.0 ** d


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('carpeta', type=Path)
    p.add_argument('salida', type=Path)
    args = p.parse_args()
    filas = [leer(f) for f in sorted(args.carpeta.rglob('*.grib2'))]
    nativos = pd.DataFrame(filas, columns=['emision_utc', 'inicio', 'fin', 'valor'])
    if nativos.duplicated(['emision_utc', 'inicio', 'fin']).any():
        raise ValueError('Archivos duplicados para la misma emisión e intervalo')
    nativos['emision_utc'] = nativos.emision_utc.dt.strftime('%Y-%m-%d %H:%M:%S+00:00')
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    nativos.sort_values(['emision_utc', 'inicio', 'fin']).to_csv(args.salida, index=False)
    print(len(nativos), 'promedios;', nativos.emision_utc.nunique(), 'emisiones')
