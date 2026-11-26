"""El cargador por trozos (scripts/memoria_limitada) debe dar lo mismo que fvaa.produccion.cargar_produccion."""
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
import fvaa.contracts as contratos
import fvaa.produccion as produccion

CARPETA = Path(__file__).resolve().parents[1] / 'scripts' / 'memoria_limitada'


def cargar_modulo(nombre):
    spec = importlib.util.spec_from_file_location(nombre, CARPETA / f'{nombre}.py')
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


trozos = cargar_modulo('trozos')
lean = cargar_modulo('lean')


def escribir(tmp_path, tiempos, potencia, extra=True):
    datos = pd.DataFrame({'timestamp': tiempos, 'active_power_P1': potencia})
    if extra:
        datos['otra_columna'] = 1
    ruta = tmp_path / 'prod.csv'
    datos.to_csv(ruta, index=False)
    return ruta


def serie_valida(n=2500):
    tiempos = pd.date_range('2020-01-01 00:00:00', periods=n, freq='s', tz='UTC').astype(str)
    potencia = np.linspace(0, 5000, n)
    potencia[10:20] = np.nan  # huecos de potencia permitidos
    return tiempos, potencia


def test_mismo_dataframe_que_el_cargador_original(tmp_path):
    ruta = escribir(tmp_path, *serie_valida())
    original = produccion.cargar_produccion(ruta)
    por_trozos = trozos.cargar_produccion_trozos(ruta, filas=400)  # varios trozos
    pd.testing.assert_frame_equal(original, por_trozos, check_exact=True)
    assert str(por_trozos.timestamp.dtype) == 'datetime64[ns, UTC]'


def test_validacion_ligera_acepta_y_rechaza_como_la_original(tmp_path, monkeypatch):
    tiempos, potencia = serie_valida()
    casos = {
        'duplicado': (list(tiempos[:5]) + [tiempos[4]] + list(tiempos[5:]), np.append(potencia, 1.0)),
        'desordenado': (list(tiempos[::-1]), potencia),
        'varias_lecturas_por_segundo': (list(pd.date_range('2020-01-01', periods=2500, freq='500ms', tz='UTC')), potencia),
        'potencia_negativa': (tiempos, np.where(np.arange(len(potencia)) == 3, -1.0, potencia)),
        'sin_potencia': (tiempos, np.full(len(potencia), np.nan)),
    }
    for nombre, (t, p) in casos.items():
        datos = pd.DataFrame({'timestamp': pd.to_datetime(pd.Series(t), utc=True, format='ISO8601'), 'active_power_P1': p[:len(t)]})
        with pytest.raises((ValueError, TypeError)) as original:
            contratos.validar_produccion(datos)
        monkeypatch.setattr(produccion, 'validar_produccion', lean.validar_lean)
        with pytest.raises((ValueError, TypeError)) as ligera:
            lean.validar_lean(datos)
        assert type(original.value) is type(ligera.value) and str(original.value) == str(ligera.value), nombre
    ok = pd.DataFrame({'timestamp': pd.to_datetime(pd.Series(tiempos), utc=True), 'active_power_P1': potencia})
    assert contratos.validar_produccion(ok) is None and lean.validar_lean(ok) is None
