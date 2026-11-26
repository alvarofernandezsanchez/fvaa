# fvaa

Predicción de producción fotovoltaica con PTProsumer. El nivel 1 reproduce el experimento PR20–2020 con producción histórica y calendario. El notebook `notebooks/PR20.ipynb` conserva el desarrollo exploratorio y sus resultados originales.

## Instalación

Desde la raíz del proyecto, con el entorno existente activado:

```powershell
python -m pip install -e ".[dev]"
python -m pytest -q
python -m fvaa.pipeline --help
```

Se utilizan NumPy, pandas, scikit-learn, Matplotlib y joblib. No se exige actualizar sus versiones. Las versiones realmente instaladas se guardan en cada ejecución, junto con Python y el estado de Git. Los estimadores de scikit-learn utilizados trabajan en CPU; el pipeline no requiere CUDA.

## Datos y configuración

La configuración es `configs/pr20_2020.json`. Todas sus rutas se resuelven desde la raíz del proyecto (el directorio padre de `configs`), sin rutas personales. La disposición que ya existe en este proyecto es:

```text
data/raw/PTProsumer/PR20/pr20_prod_2020.csv/pr20_prod_2020.csv
```

La repetición del nombre corresponde a la carpeta de extracción del archivo. Si tu disposición es distinta, cambia únicamente `entrada` en la configuración. El CSV necesita `timestamp` y `active_power_P1`; las demás columnas no se cargan. La validación existente rechaza fechas inválidas, duplicadas o desordenadas, varias lecturas en el mismo segundo y potencias negativas o infinitas; permite potencia ausente. Se detiene con un error en lugar de corregir esas entradas silenciosamente. Los datos originales permanecen fuera de Git. Se conserva la carga anual existente, sin introducir procesamiento por bloques.

## Preparación de irradiación PR20

La irradiación se carga y agrega a intervalos de 15 minutos mediante `src/fvaa/irradiacion.py`. Para generar las tablas y los informes, ejecuta desde la raíz del proyecto: `python src/04_preparar_irradiacion_15min.py`.

Las tablas agregadas se guardan en `data/interim/PTProsumer/PR20/irradiacion_15min/`. Los informes de cobertura se guardan en `reports/data_quality/`.

El timestamp original marca el final del minuto. En cada cuarto se suman los valores en Wh/m²; la irradiancia media equivalente en W/m² se calcula dividiendo esa suma entre 0,25 horas. Los intervalos incompletos se marcan y no se rellenan con cero. El último cuarto de cada archivo anual puede quedar incompleto porque el archivo termina a las 23:59.

## Ejecución por etapas

El comando sin `--stage` ejecuta **solo preparación**:

```powershell
python -m fvaa.pipeline --config configs/pr20_2020.json --stage preparacion
```

Al terminar, el comando imprime su carpeta de resultados. Sustituye las dos rutas de ejemplo por las carpetas reales impresas:

```powershell
$preparacion = "reports/experimentos/<carpeta_preparacion>"
python -m fvaa.pipeline --config configs/pr20_2020.json --stage desarrollo --prepared-run $preparacion
$desarrollo = "reports/experimentos/<carpeta_desarrollo>"
python -m fvaa.pipeline --config configs/pr20_2020.json --stage final --prepared-run $preparacion --development-run $desarrollo
```

Desarrollo lee únicamente `train.csv` y `val.csv`, ejecuta las búsquedas internas sobre entrenamiento y exporta validación. No abre `test.csv`. Final requiere un desarrollo completado con la misma configuración y la misma preparación; reentrena con entrenamiento más validación y evalúa test. Las configuraciones finales están declaradas de antemano, sin selección automática mirando el test. No se cargan los modelos joblib de una ejecución anterior: se reconstruyen los estimadores desde parámetros JSON y se reentrenan.

El experimento completo requiere esta solicitud explícita:

```powershell
python -m fvaa.pipeline --config configs/pr20_2020.json --stage completo
```

Este es el comando preparado para reproducir los datos reales de PR20–2020. Incluye búsquedas costosas y no se ha ejecutado automáticamente. Las tres etapas generan carpetas distintas, enlazadas por su procedencia. Un fallo conserva sus resultados parciales con estado `fallido`, que no puede reutilizarse como etapa completada.

## Metodología y variantes

- UTC desde la primera conversión; cada fila en `t` representa `[t, t + 1 h)`.
- Potencia en W y energía estimada en kWh: media de las lecturas / 1000 para una hora. Se supone que la potencia observada representa la hora completa.
- Cobertura mínima del 99 % de 3.600 lecturas válidas. Las horas insuficientes conservan energía ausente; no se imputan ceros.
- Se conserva la rejilla horaria antes de calcular retardos de 1, 2 y 24 horas. Después se eliminan explícitamente filas incompletas y se registra su número. Las otras entradas son hora y mes.
- Objetivo: energía de la hora que comienza en `t`. Las entradas solo utilizan horas ya terminadas. En validación y test se usan las observaciones históricas disponibles en cada instante; no se sustituye el histórico por predicciones recursivas.
- Entrenamiento inicial: enero–agosto; validación: septiembre–octubre; test: noviembre–diciembre. `TimeSeriesSplit(n_splits=3)` se aplica al entrenamiento limpio, igual que en el notebook. Al existir filas excluidas, cada partición interna puede cubrir distinta duración de calendario.
- Se comparan persistencia, persistencia diaria, regresión lineal original y con mínimo cero, RF inicial y sus dos búsquedas, y GB inicial y su búsqueda. También se reproduce la comparación de profundidades RF.
- RF usa MAE original en las búsquedas; GB usa MAE después del mínimo cero. Se conservan las predicciones originales para auditar negativos.
- Configuraciones finales: regresión lineal, RF de la **primera** búsqueda y GB **inicial**. Se reentrenan con enero–octubre; los tres aplican mínimo cero en test. RF refinado y GB ajustado se evalúan en validación pero no reemplazan las variantes finales.
- Cuantiles: ajuste independiente q10/q50/q90; diagnóstico de q10 constante y alternativa con inicialización lineal. Se aplica mínimo cero a las predicciones, se diagnostican cruces y se ordenan por fila para la variante alternativa y para test. Los cuantiles finales son q10 alternativo y q50/q90 originales, reentrenados con enero–octubre. Se preservan las etapas anteriores a las correcciones.
- Pinball loss, calibración marginal (`<` y `<=`), cobertura, anchura y grupos de producción cero/positiva; referencias constantes estimadas con entrenamiento en validación y con desarrollo en test.

**Límites:** el test de 2020 ya fue observado; no es un nuevo periodo independiente para futuras mejoras. Ordenar cuantiles no resuelve su calibración. Este pipeline no ajusta reglas para mejorar la cobertura contra test y no copia las métricas del notebook como si fueran recién calculadas.

## Resultados por ejecución

Se crea una carpeta única bajo `reports/experimentos` con fecha UTC y sufijo aleatorio. No se sobrescriben ejecuciones anteriores. Cada carpeta contiene `config.json`, `entorno.json`, `procedencia.json`, `estado.json`, `ejecucion.log` y `limitaciones.txt`.

| Etapa | Archivos principales |
|---|---|
| Preparación | `calidad.json` (ruta, tamaño y mtime del CSV, auditoría y exclusiones), `produccion_horaria.csv`, `variables_con_ausencias.csv`, `filas_excluidas.csv`, `train.csv`, `val.csv`, `test.csv`, hashes de las particiones y figura de energía |
| Desarrollo | Métricas y predicciones de validación y entrenamiento, negativos, coeficientes, errores de regresión, profundidades RF, `*_cv.csv` con errores por partición, cortes internos, mejores parámetros, cuantiles originales/corregidos/ordenados, cruces, calibración, pinball, diagnósticos q10, modelos y figuras |
| Final | Métricas y predicciones de test separadas, cuantiles antes/después de ordenación, cruces, cobertura, calibración, pinball, modelos finales y figuras |

Los modelos `.joblib` y las carpetas `reports/` no entran en Git. **Solo deben cargarse modelos joblib de fuentes de confianza.** El pipeline los exporta, pero no ofrece carga de archivos joblib arbitrarios. Los hashes se calculan sobre los CSV horarios preparados, no sobre el CSV original de varios GB; la identificación del original registra ruta, bytes y mtime.

## Correspondencia con el notebook

| Sección | Implementación |
|---|---|
| Carga y validación | `produccion.cargar_produccion`, `contracts.validar_produccion` |
| Calidad y agregación | `pipeline.preparar`, `produccion.agregar_produccion_horaria` |
| Objetivo, retardos y calendario | `features.crear_variables_historicas` |
| Exclusiones y separación | `pipeline.preparar`, `particiones.separar_temporalmente` |
| Referencias, modelos y correcciones | `modelos.referencias`, `crear_modelo`, `predecir` |
| Profundidades y validación | `pipeline.desarrollar`, `evaluacion.evaluar_predicciones` |
| Búsquedas temporales | `busquedas.buscar_temporal` |
| Cuantiles y diagnóstico | `cuantiles.entrenar_cuantiles`, `diagnosticar_q10`, `diagnosticar_cruces`, `ordenar_cuantiles`, `evaluar_cuantiles` |
| Reentrenamiento y test | `pipeline.evaluar_final` |
| Figuras | `figuras.dibujar_predicciones`, `dibujar_intervalo` |

## Estado de irradiación

El **nivel 2 ya está integrado** en `notebooks/FVAA_fase1.ipynb`: compara producción y calendario con y sin irradiación histórica para la siguiente hora, el perfil de 24 h y el total de 24 h. Incluye referencias sobre las mismas muestras que los modelos, selección por validación, cuantiles y estudio del tamaño de entrenamiento en validación. Las tablas y gráficas se generan al ejecutar el notebook.

Ejecuta sus celdas en orden con el entorno del proyecto, desde la raíz o desde `notebooks/`. Utiliza producción de 2020 e irradiación de 2020 y, si existe, 2021 para completar el límite anual; las rutas se resuelven desde la raíz. La carga anual de producción requiere memoria para las lecturas por segundo.

La preparación de irradiación a 15 minutos sigue disponible en `src/fvaa/irradiacion.py` y `src/04_preparar_irradiacion_15min.py`. El **pipeline histórico descrito arriba continúa siendo independiente** y reproduce únicamente producción horaria PR20–2020; no ejecuta el nivel 2 del notebook.

Los retardos utilizan horas terminadas en UTC, suponiendo que están disponibles al emitir. CAMS retrospectivo no demuestra disponibilidad inmediata ni equivale a pronósticos archivados. El test de 2020 es conocido y su evaluación es retrospectiva. El nivel 3 (pronósticos GFS) se describe en su sección más abajo.

## Validación de la extracción

Los tests existentes cubren cobertura, rejilla, retardos, cortes temporales y alineación de métricas. Las pruebas añadidas verifican carga UTC, contratos, mínimo cero, conservación de originales, cruces y ordenación, cobertura/pinball y la conexión por etapas con un CSV sintético pequeño. Solo en la configuración de esos tests se reducen árboles y grids; `configs/pr20_2020.json` conserva los del notebook.

La validación sintética comprueba comportamiento y conexiones; no impone las métricas reales del notebook. El usuario ha comunicado la reproducción de las métricas compartidas con datos reales en Windows tras preservar la precisión de las particiones CSV. Los resultados, el entorno y los límites de esa equivalencia se documentan en [Reproducibilidad PR20–2020](docs/reproducibilidad_pr20_2020.md); no se ha realizado una comparación exhaustiva de todos los artefactos.

## Nivel 3: pronósticos GFS y comparación de variables meteorológicas

Estado: **resultados completos de una ejecución con carga por trozos (no la oficial del notebook)**. Cuatro configuraciones x tres objetivos (1 h, perfil 24 h, total 24 h) x Ridge/RF/GB, latencias GFS de 6 h (principal) y 3 h (sensibilidad), con pronósticos GFS de 2020 completos. Tablas, selección por validación y figuras en [resultados/resultados_nivel3.md](resultados/resultados_nivel3.md). Es un solo experimento (PR20, 2020, test ya observado); no se generaliza.

Configuraciones (mismas muestras, particiones, modelos, hiperparámetros y métricas por objetivo; la muestra común es la intersección de las cuatro):

1. Nivel 1: producción histórica y calendario.
2. Nivel 2: nivel 1 más irradiación histórica CAMS.
3. Nivel 3A: nivel 1 más pronósticos GFS, sin CAMS.
4. Nivel 3B: nivel 1, CAMS y pronósticos GFS.

La mejora porcentual se calcula con el mismo modelo y objetivo: 2 frente a 1, 3A frente a 1, 3B frente a 2 y 3B frente a 3A (si 3B mejora a 3A, CAMS aporta valor aun con pronósticos). La selección de modelo usa validación, no test. El test de 2020 ya se observó antes, así que no es una evaluación independiente nueva.

### Datos GFS

- Fuente: NCEP GFS 0,25° (GDEX d084001), variable DSWRF en superficie, celda 32,75° N y 343° E (17° O). Es una aproximación a Madeira, no la ubicación confirmada de PR20.
- `data/interim/gfs_pr20_2020/gfs_madeira_3h_2020.csv` (del compañero, no se obtiene con ningún script de este repositorio: hay que aportarlo): 25 puntos, 1.464 ejecuciones de 2020, plazos de 3 a 24 h, medias de 3 h. No se versiona (datos pesados).
- Ampliación a 36 h (ruta usada): subset por lotes de GDEX (cuenta gratuita con ORCID, solicitud por API `https://gdex.ucar.edu/api/submit/`), dataset ds084.1, DSWRF, nivel SFC 0, un solo punto (32,75 N, 343 E). Solicitud 996991: ciclos de 6 h de 2020 con los productos f027, f030, f033 y f036; solicitud 996992: ciclos del 31/12/2019 con f003 a f036 (por la latencia en las primeras horas del año). Salen archivos GRIB2 de un punto; `python scripts/leer_gdex_grib2.py <carpeta_grib2> data/raw/gfs_36h/nativos_dswrf.csv` los lee con un lector mínimo (sin ecCodes, no es un lector estándar) y se detiene si algún mensaje no es DSWRF de superficie en la celda, un promedio con empaquetado simple y sin bitmap, o su intervalo no coincide con el nombre. Después, `python scripts/ampliar_gfs.py <csv_original> data/raw/gfs_36h/nativos_dswrf.csv data/interim/gfs_pr20_2020/gfs_madeira_3h_2020_36h.csv` une los nuevos intervalos al CSV original sin modificarlo (11.712 filas originales reutilizadas + 5.904 nuevas = 17.616; 1.468 ciclos con plazos de 3 a 36 h). El notebook usa el CSV de 36 h si existe y, si no, el de 24 h.
- `scripts/descargar_gfs_ncss.py` (NCSS) queda como ruta alternativa que no se usó para los resultados finales: el servidor NCSS cortaba las conexiones. Con descargas parciales, `scripts/ampliar_gfs.py` omite los tramos de 6 h cuya pareja de 3 h falta y no inventa valores; los objetivos de 24 h con GFS solo se evalúan con cobertura completa.
- Latencia: `LATENCIA_GFS_H` (6 h por defecto). Para la sensibilidad de 3 h se ejecuta el notebook con 3 y se informan las dos; la elección no se hace con el test. Comparación común entre latencias: cada columna `pronostico_hk` se anula donde no estaría disponible con 6 h (la latencia más restrictiva), por columna y antes de ajustar (`pron.where(alinear_gfs(..., 6).notna())` en el notebook). Después, cada objetivo exige solo las columnas que usa: el de 1 h exige `h0` y los de 24 h exigen `h0` a `h23`. Así, con 3 h y con 6 h cada objetivo usa las mismas filas, y el de 1 h no depende de las columnas de 24 h.
- Diferencia con la rejilla del compañero: la ampliación cubre **solo la celda 32,75° N, 343° E**, que es la única que usa el notebook. Los otros 24 puntos solo llegan a 24 h.
- Productos de 3 h y 6 h: f003, f009, ..., f027, f033 son medias de 3 h; f006, f012, ..., f030, f036 son medias de 6 h desde el plazo anterior múltiplo de 6. El segundo tramo de tres horas se reconstruye como `2 * A6h - A3h` y no se solapa con el primero (`tests/test_comparacion_gfs.py`). Se comprobó con un caso real (2020-06-15 00 UTC, f012): 2 x 475 - 220 = 730, igual al CSV del compañero.
- Valores negativos: el CSV original tiene 10.828 filas con DSWRF entre -20 y -2 W/m². Todas son del tipo "derivado de productos GFS de 3 h y 6 h", ninguna es de un producto directo. Se atribuyen a la resta `2 * A6h - A3h` con valores nativos redondeados, no a una medición. No se eliminan del CSV; `alinear_gfs` los trunca a 0 al alinear, y esa decisión es nuestra, no de GFS.

### Fugas temporales

La hora de inicialización de GFS no es la de publicación. No tenemos fechas de disponibilidad verificadas, así que cada ejecución se considera disponible `latencia` horas después de su inicialización. La latencia principal es de 6 h (**hipótesis**, no disponibilidad histórica acreditada). El notebook informa de la cobertura con 0, 3 y 6 h. Para cada emisión t y cada hora t+h se usa el último pronóstico disponible en t (`pd.merge_asof(direction="backward")`), no el último de esa hora respecto a su propia fecha. Los objetivos de 24 h usan siempre 24 horas de pronóstico (plazos de hasta 36 h). Si la cobertura no es suficiente en las tres particiones, esos objetivos no se evalúan con GFS y el notebook lo indica; no se usan horizontes parciales ni se rellenan faltantes.

### Reproducir

```powershell
python -m pytest -q
python descargar_pr20.py --descargar   # producción e irradiación PTProsumer PR20 (OSF, enlaces directos; verifica SHA-256 del .gz y del CSV)
# subset de GDEX (solicitudes 996991 y 996992, ver arriba) y después:
python scripts/leer_gdex_grib2.py <carpeta_grib2> data/raw/gfs_36h/nativos_dswrf.csv
python scripts/ampliar_gfs.py data/interim/gfs_pr20_2020/gfs_madeira_3h_2020.csv data/raw/gfs_36h/nativos_dswrf.csv data/interim/gfs_pr20_2020/gfs_madeira_3h_2020_36h.csv
```

Después, ejecutar `notebooks/FVAA_fase1.ipynb` desde un kernel nuevo. Con 2 GB de RAM, `python scripts/memoria_limitada/preparar_ejecucion.py` crea copias no oficiales `notebooks/_run_lat6.ipynb` y `_run_lat3.ipynb` (carga de producción por trozos y cada una con su latencia GFS fija, 6 h y 3 h; nada más cambia; no se versionan); los resultados publicados salen de esas copias. La carga de producción necesita memoria para 31,6 millones de filas.

### Versiones y entorno

Resultados publicados obtenidos con Python 3.10.12 (Linux 6.1), numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2, scipy 1.15.3, matplotlib 3.10.9, joblib 1.6.0, threadpoolctl 3.8.0, ipykernel 7.3.0, nbconvert 7.17.2, nbclient 0.11.0, nbformat 5.11.1 y pytest 9.2.0. Están fijadas en `requirements-experimento.txt`; se comprobó que `pip install -r requirements-experimento.txt -e .` instala en un entorno nuevo con Python 3.10.12 y que `pip check` no da errores. La suite completa se ha ejecutado en Linux; en Windows fallaba el bloqueo de NCSS (ruta solo Linux), y ese test se omite allí. Los modelos usan `random_state=42`; con otras versiones de scikit-learn o numpy los valores pueden cambiar en las últimas cifras.

### Cargador por bloques

La ejecución con 2 GB de RAM sustituye `cargar_produccion` por `scripts/memoria_limitada/trozos.py` (lectura en trozos de 1 millón de filas con matrices preasignadas) y `fvaa.produccion.validar_produccion` por la versión de `lean.py` (mismas comprobaciones sin tablas hash de 31 millones de filas; ante cualquier incumplimiento llama a la función original, así que los errores y mensajes son idénticos). La equivalencia con el cargador original se comprueba en `tests/test_cargador_trozos.py` (DataFrame idéntico con `check_exact=True` en trozos pequeños, y mismo tipo y mensaje de error en duplicados, desorden, varias lecturas por segundo, potencia negativa y sin potencia) y sobre muestras reales del CSV de PR20 (ver `resultados/equivalencia_cargador.md`). No se ejecutó el cargador original sobre los 31,6 millones de filas por falta de RAM: esa parte es una comprobación por muestras, no una prueba completa.

### Limitaciones

- Descarga GFS a 36 h completa (1468 ciclos, plazos de 3 a 36 h, 17616 filas, sin huecos). El lector de GRIB2 es mínimo y propio (`scripts/leer_gdex_grib2.py`), no un lector estándar. Validó 5904/5904 mensajes con comprobaciones explícitas (`tests/test_leer_gdex_grib2.py`). La comparación con valores de NCSS hecha durante el desarrollo no se conserva como evidencia y no se afirma aquí.
- Latencia supuesta, ubicación aproximada y un solo año.
- CAMS retrospectivo no acredita disponibilidad inmediata.
