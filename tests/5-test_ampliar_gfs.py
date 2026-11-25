import pandas as pd
import pytest
import os
from scripts.ampliar_gfs import convertir_3h
from scripts.descargar_gfs_ncss import bloquear


def test_promedios_nativos():
    t = pd.Timestamp('2020-01-01', tz='UTC')
    datos = pd.DataFrame([(t, 24, 27, 100.), (t, 24, 30, 150.),
                          (t, 30, 33, 300.), (t, 30, 36, 250.)],
                         columns=['emision_utc', 'inicio', 'fin', 'valor'])
    resultado = convertir_3h(datos)
    assert resultado.plazo_horas.tolist() == [27, 30, 33, 36]
    assert resultado.dswrf_media_w_m2.tolist() == [100., 200., 300., 200.]
    assert (resultado.fin_validez_utc - resultado.inicio_validez_utc).eq(pd.Timedelta(hours=3)).all()
    sin_pareja = convertir_3h(datos.iloc[1:])  # falta f027: f030 no se reconstruye
    assert sin_pareja.plazo_horas.tolist() == [33, 36]


def test_descarga_parcial_sin_pareja_no_inventa_intervalos():
    t = pd.Timestamp('2020-01-01', tz='UTC')
    datos = pd.DataFrame([(t, 24, 27, 100.), (t, 30, 36, 250.),           # f030 sin su pareja de 3 h
                          (t + pd.Timedelta(hours=6), 24, 27, 10.), (t + pd.Timedelta(hours=6), 24, 30, 30.)],
                         columns=['emision_utc', 'inicio', 'fin', 'valor'])
    resultado = convertir_3h(datos)
    assert resultado.plazo_horas.tolist() == [27, 27, 30]  # solo f027 y la pareja completa
    assert resultado.dswrf_media_w_m2.tolist() == [100., 10., 50.]


def test_bloqueo_de_instancia_unica(tmp_path):
    lock = tmp_path / 'x.lock'
    bloquear(lock)
    with pytest.raises(SystemExit):
        bloquear(lock)
    lock.write_text('999999999')  # PID inexistente: bloqueo huérfano, se reemplaza
    bloquear(lock)
    assert lock.read_text() == str(os.getpid())
