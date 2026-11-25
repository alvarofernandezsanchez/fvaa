"""Descarga exclusivamente los datos PTProsumer usados en FVAA (Python 3.10+)."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

API = 'https://api.osf.io/v2/nodes/9xs3a/files/osfstorage/'
NOMBRES = {'pr20_prod_2020.csv.gz', 'pr20_irrad_2020.csv.gz', 'pr20_irrad_2021.csv.gz'}
IDS = {'pr20_prod_2020.csv.gz': '686e6aa428660bf19b933b93',
       'pr20_irrad_2020.csv.gz': '686e591baf953df9ae933921'}


def abrir(url):
    return urlopen(Request(url, headers={'User-Agent': 'FVAA-PR20/1.0', 'Accept-Encoding': 'identity'}), timeout=60)


def enlace(valor):
    return valor['href'] if isinstance(valor, dict) else valor


def localizar(url):
    while url:
        with abrir(url) as respuesta:
            listado = json.load(respuesta)
        for archivo in listado['data']:
            a = archivo['attributes']
            nombre = a['name']
            if a['kind'] == 'folder':
                if nombre.upper().startswith('PR_') and nombre.upper() != 'PR_20':
                    continue
                if nombre.lower() in ('net-load', 'net_load', 'net load'):
                    continue
                yield from localizar(enlace(archivo['relationships']['files']['links']['related']))
            elif nombre in NOMBRES:
                yield archivo
        url = enlace(listado['links'].get('next'))


def sha256(ruta):
    h = hashlib.sha256()
    with ruta.open('rb') as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def descargar(archivo, destino):
    a = archivo['attributes']
    nombre = a['name']
    gz = destino / nombre[:-3] / nombre
    csv = gz.with_suffix('')
    gz.parent.mkdir(parents=True, exist_ok=True)
    esperado = (a.get('extra') or {}).get('hashes', {}).get('sha256')
    tamano = a.get('size')
    if not esperado and tamano is None:
        raise ValueError(f'No hay tamaño ni hash remoto: {nombre}')
    nuevo = not gz.exists()
    candidato = gz.with_suffix('.gz.part') if nuevo else gz
    if nuevo:
        with abrir(enlace(archivo['links']['download'])) as origen, candidato.open('wb') as salida:
            if origen.status != 200 or origen.headers.get('Content-Range'):
                raise ValueError('Descarga incompleta')
            shutil.copyfileobj(origen, salida, 1024 * 1024)
    digest = sha256(candidato)
    if (tamano is not None and candidato.stat().st_size != tamano) or (esperado and digest.lower() != esperado.lower()):
        raise ValueError(f'Archivo incorrecto: {candidato}')
    if nuevo:
        candidato.rename(gz)
    temporal = csv.with_suffix('.csv.part')
    with gzip.open(gz, 'rb') as origen, temporal.open('wb') as salida:
        shutil.copyfileobj(origen, salida, 1024 * 1024)
    digest_csv = sha256(temporal)
    if csv.exists():
        if sha256(csv) != digest_csv:
            raise ValueError(f'CSV local distinto; se conserva: {csv}')
        temporal.unlink()
    else:
        temporal.rename(csv)
    print(f'Verificado: {csv}')
    return {'nombre': nombre, 'id': archivo['id'], 'version': a.get('current_version'),
            'url': enlace(archivo['links']['download']), 'sha256_gz': digest,
            'sha256_csv': digest_csv, 'ruta': str(csv)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', type=Path, default=Path('data/raw/PTProsumer/PR20'))
    parser.add_argument('--descargar', action='store_true', help='Sin esta opción solo lista enlaces')
    args = parser.parse_args()
    encontrados = {}
    for archivo in localizar(API):
        nombre = archivo['attributes']['name']
        if nombre in encontrados or (nombre in IDS and archivo['id'] != IDS[nombre]):
            raise ValueError(f'Identidad ambigua o modificada: {nombre}')
        encontrados[nombre] = archivo
    if NOMBRES - encontrados.keys():
        raise FileNotFoundError(f'Faltan archivos: {NOMBRES - encontrados.keys()}')
    for nombre, archivo in sorted(encontrados.items()):
        print(nombre, archivo['id'], archivo['attributes'].get('size'), enlace(archivo['links']['download']))
    if args.descargar:
        registros = []
        for archivo in encontrados.values():
            registros.append(descargar(archivo, args.destino))
        (args.destino / 'manifest_pr20.json').write_text(json.dumps(registros, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
