"""Alineación de pronósticos GFS de tres horas con emisiones horarias."""

import numpy as np
import pandas as pd


def cargar_gfs(ruta, lat=32.75, lon=343.0):
    datos = pd.read_csv(ruta)
    datos = datos.loc[(datos['lat'] == lat) & (datos['lon'] == lon)].copy()
    if datos.empty:
        raise ValueError('No hay datos GFS para el punto elegido')
    fechas = ['emision_utc', 'inicio_validez_utc', 'fin_validez_utc']
    for c in fechas:
        datos[c] = pd.to_datetime(datos[c], utc=True)
    if (datos[fechas].isna().any().any()
        or any(not datos[c].eq(datos[c].dt.floor('h')).all() for c in fechas)
        or not (datos.fin_validez_utc - datos.inicio_validez_utc).eq(pd.Timedelta(hours=3)).all()
        or not datos.duracion_intervalo_h.eq(3).all()
        or not (datos.fin_validez_utc - datos.emision_utc).eq(pd.to_timedelta(datos.plazo_horas, unit='h')).all()
        or (datos.inicio_validez_utc < datos.emision_utc).any()
        or datos.duplicated(['emision_utc', 'inicio_validez_utc']).any()
        or not np.isfinite(datos.dswrf_media_w_m2).all()):
        raise ValueError('Intervalos, plazos o valores GFS no válidos')
    return datos


def alinear_gfs(indice, datos, latencia_h=6):
    """Latencia supuesta, no fecha de publicación comprobada."""
    if latencia_h < 0:
        raise ValueError('La latencia no puede ser negativa')
    datos = datos.copy()
    datos['disponible'] = datos.emision_utc + pd.Timedelta(hours=latencia_h)
    # Media de 3 h constante en cada una de las tres horas.
    datos['ghi'] = datos.dswrf_media_w_m2.clip(lower=0)
    horas = pd.concat([
        datos.assign(objetivo=datos.inicio_validez_utc + pd.Timedelta(hours=i))
        for i in range(3)
    ]).sort_values('disponible')
    if horas.duplicated(['disponible', 'objetivo']).any():
        raise ValueError('Pronósticos horarios ambiguos')
    resultado = pd.DataFrame(index=indice)
    for h in range(24):
        consulta = pd.DataFrame({'t': indice, 'objetivo': indice + pd.Timedelta(hours=h)})
        pred = pd.merge_asof(consulta, horas[['disponible', 'objetivo', 'ghi']],
                             left_on='t', right_on='disponible', by='objetivo',
                             direction='backward')
        resultado[f'pronostico_h{h}'] = pred.ghi.to_numpy()
    return resultado
