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

## Coordinación pendiente

El contrato horario de producción de este experimento difiere de `docs/data_contract.md`, que describe potencia media en 15 minutos con horizonte de una hora. Ese contrato común se mantiene sin cambios. Antes de integrar irradiación hay que acordar resolución, objetivo y disponibilidad de sus variables en el instante de predicción. No se implementa ni simula irradiación.

## Validación de la extracción

Los tests existentes cubren cobertura, rejilla, retardos, cortes temporales y alineación de métricas. Las pruebas añadidas verifican carga UTC, contratos, mínimo cero, conservación de originales, cruces y ordenación, cobertura/pinball y la conexión por etapas con un CSV sintético pequeño. Solo en la configuración de esos tests se reducen árboles y grids; `configs/pr20_2020.json` conserva los del notebook.

La validación sintética comprueba comportamiento y conexiones; no impone las métricas reales del notebook. El usuario ha comunicado la reproducción de las métricas compartidas con datos reales en Windows tras preservar la precisión de las particiones CSV. Los resultados, el entorno y los límites de esa equivalencia se documentan en [Reproducibilidad PR20–2020](docs/reproducibilidad_pr20_2020.md); no se ha realizado una comparación exhaustiva de todos los artefactos.
