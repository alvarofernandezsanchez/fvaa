# Equivalencia del cargador por bloques con el original

Alcance: comprobación por pruebas sintéticas y por muestras reales. No se ejecutó el cargador original sobre las 31,6 millones de filas de PR20-2020 (no cabe en 2 GB de RAM), así que no es una prueba completa del fichero.

## Pruebas sintéticas (`tests/test_cargador_trozos.py`)
- Mismo DataFrame que `fvaa.produccion.cargar_produccion` (`assert_frame_equal`, `check_exact=True`) con trozos de 400 filas.
- El validador de `scripts/memoria_limitada/lean.py` acepta y rechaza los mismos casos que el original, con el mismo tipo y mensaje de excepción (duplicados, desorden, varias lecturas por segundo, potencia negativa, sin potencia). Ante un fallo llama a la función original.

## Muestras reales (`pr20_prod_2020.csv`, 1,5 millones de filas cada una, trozos de 300 000)
| Muestra | Primer timestamp (UTC) | Último timestamp (UTC) | DataFrame | Agregado horario |
|---|---|---|---|---|
| Inicio | 2020-01-01 00:00:00 | 2020-01-18 09:16:10 | idéntico | idéntico |
| Medio (filas 15 000 001 a 16 500 000) | 2020-06-22 20:09:48 | 2020-07-10 05:24:49 | idéntico | idéntico |
| Final | 2020-12-14 14:43:44 | 2020-12-31 23:59:59 | idéntico | idéntico |

Comparación exacta (`check_exact=True`) entre `cargar_produccion` y `cargar_produccion_trozos`, y entre `agregar_produccion_horaria` de ambos; `validar_lean` no dio error en ninguna.
Script: ver el bloque de comparación descrito arriba (cargar la muestra con ambas funciones y `assert_frame_equal`).
