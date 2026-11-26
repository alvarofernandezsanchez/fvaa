"""Descarga exclusivamente los datos PTProsumer usados en FVAA (Python 3.10+).

Usa enlaces directos de OSF y verifica el SHA-256 del .gz y del CSV descomprimido (valores fijados abajo,
obtenidos del manifest de la primera descarga y contrastados de forma independiente para la producción).
No recorre el catálogo de la API de OSF, que puede devolver HTTP 500.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil
from urllib.request import Request, urlopen

# nombre: (enlace directo, tamaño del .gz en bytes o None, SHA-256 del .gz, SHA-256 del CSV)
FUENTES = {
    'pr20_prod_2020.csv.gz': ('https://osf.io/download/ct8x4/', 230688449,
                              '10b98c7cd0b76b6fea5a99921ce7fcb3b351eeb7a5eaef22979fa27d588d3448',
                              '63a1a4e899064849d2dbe93fed6a88faa4e33f6b1a4e349221f59d3d2434911a'),
    'pr20_irrad_2020.csv.gz': ('https://osf.io/download/686e591baf953df9ae933921/', 7762845,
                               'cd86867541c6023af939b4ddf92a5ac373367cfb4ed1da1591dec1e977cc9e1b',
                               '033747a9fbe47af5046f5e0c539c2033c430b02656cdd9cafcb5495073795d0f'),
    'pr20_irrad_2021.csv.gz': ('https://osf.io/download/686e591e7c9840d0c73ef0a6/', 7742757,
                               '2bcec6d3bdfe9114887a64a2a8cdc72762e42cc3890833be5379afaa016d8352',
                               'b0af1fdf6dc1412c63b37416fb941f561e64451bafe7266eeaf1bf655b87cebf'),
}


def abrir(url):
    return urlopen(Request(url, headers={'User-Agent': 'FVAA-PR20/1.0', 'Accept-Encoding': 'identity'}), timeout=60)


def sha256(ruta):
    h = hashlib.sha256()
    with ruta.open('rb') as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b''):
            h.update(bloque)
    return h.hexdigest()


def descargar(nombre, destino):
    url, tamano, esperado_gz, esperado_csv = FUENTES[nombre]
    gz = destino / nombre[:-3] / nombre
    csv = gz.with_suffix('')
    gz.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not gz.exists()
    candidato = gz.with_suffix('.gz.part') if nuevo else gz
    if nuevo:
        with abrir(url) as origen, candidato.open('wb') as salida:
            if origen.status != 200 or origen.headers.get('Content-Range'):
                raise ValueError('Descarga incompleta')
            shutil.copyfileobj(origen, salida, 1024 * 1024)
    digest = sha256(candidato)
    if candidato.stat().st_size != tamano or digest != esperado_gz:
        raise ValueError(f'Archivo incorrecto: {candidato}')
    if nuevo:
        candidato.rename(gz)
    temporal = csv.with_suffix('.csv.part')
    with gzip.open(gz, 'rb') as origen, temporal.open('wb') as salida:
        shutil.copyfileobj(origen, salida, 1024 * 1024)
    digest_csv = sha256(temporal)
    if digest_csv != esperado_csv:
        raise ValueError(f'CSV incorrecto: {temporal}')
    if csv.exists():
        if sha256(csv) != digest_csv:
            raise ValueError(f'CSV local distinto; se conserva: {csv}')
        temporal.unlink()
    else:
        temporal.rename(csv)
    print(f'Verificado: {csv}')
    return {'nombre': nombre, 'url': url, 'sha256_gz': digest, 'sha256_csv': digest_csv, 'ruta': str(csv)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destino', type=Path, default=Path('data/raw/PTProsumer/PR20'))
    parser.add_argument('--descargar', action='store_true', help='Sin esta opción solo lista enlaces')
    args = parser.parse_args()
    for nombre, (url, tamano, _, _) in sorted(FUENTES.items()):
        print(nombre, tamano, url)
    if args.descargar:
        registros = [descargar(nombre, args.destino) for nombre in sorted(FUENTES)]
        (args.destino / 'manifest_pr20.json').write_text(json.dumps(registros, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
