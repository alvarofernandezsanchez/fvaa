import importlib.util
import struct
from pathlib import Path
import pytest

ruta = Path(__file__).resolve().parents[1] / 'scripts' / 'leer_gdex_grib2.py'
spec = importlib.util.spec_from_file_location('leer_gdex_grib2', ruta)
lector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lector)


def mensaje(valor=150, lat=32.75, lon=343.0, parametro=192, plazo=36, inicio=30, bitmap=255, plantilla_empaquetado=0):
    """GRIB2 sintético de un punto con la misma estructura que entrega GDEX (campo constante en 1 byte)."""
    s1 = bytearray(21); s1[0:4] = struct.pack('>I', 21); s1[4] = 1
    s3 = bytearray(72); s3[0:4] = struct.pack('>I', 72); s3[4] = 3
    s3[6:10] = struct.pack('>I', 1); s3[12:14] = struct.pack('>H', 0)
    s3[46:50] = struct.pack('>i', int(lat * 1e6)); s3[50:54] = struct.pack('>i', int(lon * 1e6))
    s4 = bytearray(58); s4[0:4] = struct.pack('>I', 58); s4[4] = 4
    s4[7:9] = struct.pack('>H', 8); s4[9] = 4; s4[10] = parametro; s4[17] = 1
    s4[18:22] = struct.pack('>I', inicio); s4[22] = 1
    s4[34:41] = struct.pack('>HBBBBB', 2020, 1, 2, 12, 0, 0)  # emisión 2020-01-01 00 UTC + 36 h
    s4[41] = 1; s4[46] = 0; s4[48] = 1; s4[49:53] = struct.pack('>I', plazo - inicio)
    s5 = bytearray(21); s5[0:4] = struct.pack('>I', 21); s5[4] = 5
    s5[5:9] = struct.pack('>I', 1); s5[9:11] = struct.pack('>H', plantilla_empaquetado)
    s5[11:15] = struct.pack('>f', 0.0); s5[19] = 8
    s6 = bytearray(6); s6[0:4] = struct.pack('>I', 6); s6[4] = 6; s6[5] = bitmap
    s7 = bytearray(6); s7[0:4] = struct.pack('>I', 6); s7[4] = 7; s7[5] = valor
    cuerpo = bytes(s1 + s3 + s4 + s5 + s6 + s7)
    cabecera = b'GRIB' + bytes(2) + bytes([0, 2]) + struct.pack('>Q', 16 + len(cuerpo) + 4)
    return cabecera + cuerpo + b'7777'


def escribir(tmp_path, **kw):
    ruta = tmp_path / 'gfs.0p25.2020010100.f036.grib2'
    ruta.write_bytes(mensaje(**kw))
    return ruta


def test_lee_valor_emision_e_intervalo(tmp_path):
    emision, inicio, plazo, valor = lector.leer(escribir(tmp_path))
    assert (emision.isoformat(), inicio, plazo, valor) == ('2020-01-01T00:00:00', 30, 36, 150.0)


@pytest.mark.parametrize('cambio', [dict(lat=33.0), dict(lon=342.0), dict(parametro=193),
                                    dict(bitmap=0), dict(plantilla_empaquetado=3), dict(inicio=24)])
def test_rechaza_lo_que_no_se_pidio(tmp_path, cambio):
    with pytest.raises(ValueError):
        lector.leer(escribir(tmp_path, **cambio))
