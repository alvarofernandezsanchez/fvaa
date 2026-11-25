import pandas as pd
import pytest
from fvaa.pronosticos import cargar_gfs, alinear_gfs


def datos_ejemplo():
    t = pd.Timestamp('2020-01-01', tz='UTC')
    return pd.DataFrame({
        'emision_utc': [t, t + pd.Timedelta(hours=6)],
        'inicio_validez_utc': [t + pd.Timedelta(hours=9)] * 2,
        'fin_validez_utc': [t + pd.Timedelta(hours=12)] * 2,
        'plazo_horas': [12, 6], 'duracion_intervalo_h': [3, 3],
        'lat': [32.75] * 2, 'lon': [343.] * 2,
        'dswrf_media_w_m2': [100., 200.]
    })


def test_horizontes_y_disponibilidad():
    datos = datos_ejemplo()
    t = pd.date_range('2020-01-01 06:00', periods=7, freq='h', tz='UTC')
    p = alinear_gfs(t, datos, latencia_h=3)
    assert p.loc[t[0], 'pronostico_h3'] == 100
    assert p.loc[t[3], 'pronostico_h0'] == 200
    assert p.loc[t[0], 'pronostico_h5'] == 100
    assert pd.isna(p.loc[t[0], 'pronostico_h6'])
    assert pd.isna(p.loc[t[6], 'pronostico_h0'])
    datos.loc[1, 'dswrf_media_w_m2'] = 9999
    assert alinear_gfs(t, datos, 3).loc[t[0], 'pronostico_h3'] == 100


def test_intervalo_incorrecto(tmp_path):
    datos = datos_ejemplo()
    ruta = tmp_path / 'gfs.csv'
    datos.to_csv(ruta, index=False)
    assert len(cargar_gfs(ruta)) == 2
    datos.loc[0, 'duracion_intervalo_h'] = 6
    datos.to_csv(ruta, index=False)
    with pytest.raises(ValueError):
        cargar_gfs(ruta)


def test_negativos():
    datos = datos_ejemplo()
    datos.loc[0, 'dswrf_media_w_m2'] = -4
    t = pd.date_range('2020-01-01 06:00', periods=1, freq='h', tz='UTC')
    assert alinear_gfs(t, datos, 3).iloc[0]['pronostico_h3'] == 0


def test_cobertura_horizonte_24h():
    # Datos sintéticos: ejecución cada 6 h; plazos de 3 h hasta 36 h.
    t = pd.Timestamp('2020-01-02', tz='UTC')
    indice = pd.date_range(t, periods=6, freq='h')
    filas = []
    for emision in pd.date_range(t - pd.Timedelta(hours=12), t, freq='6h'):
        for plazo in range(3, 37, 3):
            filas.append({
                'emision_utc': emision,
                'inicio_validez_utc': emision + pd.Timedelta(hours=plazo - 3),
                'fin_validez_utc': emision + pd.Timedelta(hours=plazo),
                'plazo_horas': plazo, 'dswrf_media_w_m2': 100.0
            })
    datos = pd.DataFrame(filas)
    corto = alinear_gfs(indice, datos[datos.plazo_horas <= 24], 6)
    largo = alinear_gfs(indice, datos, 6)
    assert corto.iloc[:, 0].notna().all()
    assert not corto.notna().all(axis=1).any()
    assert largo.notna().all(axis=1).all()
