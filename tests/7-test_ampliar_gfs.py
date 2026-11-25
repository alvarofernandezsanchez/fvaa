import pandas as pd
import pytest
from scripts.ampliar_gfs import convertir_3h


def test_promedios_nativos():
    t = pd.Timestamp('2020-01-01', tz='UTC')
    datos = pd.DataFrame([(t, 24, 27, 100.), (t, 24, 30, 150.),
                          (t, 30, 33, 300.), (t, 30, 36, 250.)],
                         columns=['emision_utc', 'inicio', 'fin', 'valor'])
    resultado = convertir_3h(datos)
    assert resultado.plazo_horas.tolist() == [27, 30, 33, 36]
    assert resultado.dswrf_media_w_m2.tolist() == [100., 200., 300., 200.]
    assert (resultado.fin_validez_utc - resultado.inicio_validez_utc).eq(pd.Timedelta(hours=3)).all()
    with pytest.raises(ValueError):
        convertir_3h(datos.iloc[1:])
