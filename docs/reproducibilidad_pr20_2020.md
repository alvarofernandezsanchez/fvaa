# Reproducibilidad del experimento PR20–2020

## Alcance y procedencia

El nivel 1 predice la energía fotovoltaica de la próxima hora para PR20 durante 2020, usando solo histórico de producción y calendario. La implementación está en `src/fvaa`; `notebooks/PR20.ipynb` conserva la referencia exploratoria.

El commit base disponible al preparar este cierre es `399ddc3270ed940af036c1361048a050b00728d9` (extracción del experimento al pipeline por etapas). La corrección local de lectura con `float_precision="round_trip"` se encontraba añadida sobre esa base. Este documento no atribuye a esa base la corrección ni asigna un SHA al commit de cierre antes de crearlo.

El usuario comunica haber ejecutado preparación, desarrollo y evaluación final con los datos reales en Windows y haber reproducido las métricas compartidas del notebook tras corregir la lectura CSV. Los resultados reales que siguen proceden de esa ejecución del usuario: **no se han recalculado durante este cierre**. La equivalencia comunicada corresponde a esas métricas; no es una comparación exhaustiva de todas las predicciones, modelos, figuras y demás artefactos.

## Contrato horario y periodos

- UTC desde la primera conversión. Una fila en `t` representa `[t, t + 1 h)`.
- Potencia en W; energía estimada en kWh como potencia media observada / 1000 para una hora. Se supone que la media observada representa toda la hora.
- Cobertura mínima del 99 %: 3.564 de las 3.600 lecturas esperadas. No se sustituyen ausencias por cero.
- Objetivo: energía de la hora que comienza en `t`. Entradas: energía de las horas anteriores de 1, 2 y 24 horas, hora y mes. Los retardos se construyen sobre la rejilla completa antes de excluir filas incompletas.
- Entrenamiento inicial: enero–agosto, anterior a `2020-09-01 00:00 UTC`.
- Validación: desde `2020-09-01 00:00 UTC` hasta `2020-11-01 00:00 UTC`, excluyendo este último instante.
- Test: noviembre–diciembre, desde `2020-11-01 00:00 UTC` hasta el final de 2020.

Se mantienen `TimeSeriesSplit` con tres particiones internas, parámetros, semillas, grids y scorers del notebook. Tras fijar las configuraciones se reentrena con enero–octubre. Las variantes puntuales finales son regresión lineal con mínimo cero, RF de la primera búsqueda y GB inicial; no se eligen mirando el test. Los cuantiles finales son q10 con inicialización lineal y q50/q90 originales, con mínimo cero y ordenación posterior según el experimento.

## Ejecución por etapas

Desde la raíz del proyecto, con el entorno del experimento activado:

```powershell
python -m pip install -e ".[dev]"
python -m fvaa.pipeline --config configs/pr20_2020.json --stage preparacion
```

Usar como `$preparacion` la carpeta impresa por la primera etapa y como `$desarrollo` la carpeta impresa por la segunda; los marcadores siguientes deben sustituirse por esos nombres reales, sin copiar rutas personales:

```powershell
$preparacion = "reports/experimentos/<carpeta_preparacion>"
python -m fvaa.pipeline --config configs/pr20_2020.json --stage desarrollo --prepared-run $preparacion

$desarrollo = "reports/experimentos/<carpeta_desarrollo>"
python -m fvaa.pipeline --config configs/pr20_2020.json --stage final --prepared-run $preparacion --development-run $desarrollo
```

Las rutas del CSV original y las salidas se declaran de forma relativa en `configs/pr20_2020.json`. Desarrollo lee solo entrenamiento y validación. Final requiere una preparación y un desarrollo completados y coherentes, reconstruye las configuraciones finales y reentrena sin cargar modelos joblib arbitrarios. Cada etapa crea una carpeta propia con configuración, versiones, estado de Git, procedencia y resultados; no sobrescribe ejecuciones anteriores.

## Precisión de las particiones CSV

El usuario observó diferencias de aproximadamente `1e-16` en las entradas al guardar y recuperar las particiones horarias. Aunque pequeñas, podían modificar decisiones de los árboles y la configuración elegida por la búsqueda de Random Forest refinado. No se trata de modificar el grid ni de elegir otra metodología.

El mecanismo de escritura sigue siendo `exportar()` → `DataFrame.to_csv()`. La función común `leer_particion()` recupera entrenamiento, validación y test con:

```python
pd.read_csv(
    ruta,
    index_col=0,
    float_precision="round_trip",
)
```

Después recupera el índice temporal en UTC. Esta lectura preserva los valores float64 representados en las particiones exportadas y evita introducir esas diferencias al continuar entre etapas. No cambia la carga del CSV original, los modelos ni las reglas de tratamiento de cuantiles.

La regresión sintética usa decimales float64 sensibles, los exporta con el mismo mecanismo del pipeline y los recupera mediante `leer_particion()`, con configuración y manifiesto de hashes. Comprueba valores, tipos y fechas con igualdad exacta, sin tolerancias, para las tres particiones. Además vigila que se pase explícitamente `round_trip`: quitar esa opción debe hacer fallar la prueba aunque un lector predeterminado futuro preserve los decimales elegidos. El caso numérico por sí solo no demuestra que todas las versiones o motores de pandas fallen sin esa opción; tampoco demuestra equivalencia de cualquier CSV externo.

Las tablas de cobertura identifican su índice como `grupo`. Se mantienen `modelo` en métricas, `cuantil` en calibración, `variable` en coeficientes y `timestamp` en tablas temporales. Resúmenes estadísticos y configuraciones tienen etiquetas propias, asignadas únicamente a las tablas correspondientes.

## Entorno reportado por el usuario

| Componente | Versión reportada |
|---|---|
| Sistema | Windows |
| Python | 3.13.5 |
| scikit-learn | 1.9.1 |
| NumPy | 2.5.3 |
| pandas | 3.0.6 |

Estas versiones describen la ejecución real comunicada por el usuario. Cada ejecución del pipeline registra además sus propias versiones instaladas en `entorno.json`; no se han actualizado dependencias para este cierre.

## Métricas reales compartidas por el usuario

Evaluación puntual de test, con MAE y RMSE en kWh:

| Modelo | MAE (kWh) | RMSE (kWh) |
|---|---:|---:|
| persistencia | 0.044483539175974675 | 0.08430574558136093 |
| persistencia_diaria | 0.05566729021794218 | 0.11997388324508888 |
| lineal con mínimo cero | 0.03784569880599892 | 0.06767515515999142 |
| rf | 0.02741285661151851 | 0.05711278224122046 |
| gb | 0.02817638393059966 | 0.05825672793331946 |

Intervalo ordenado q10–q90 en test, nominalmente del 80 %:

| Medida | Resultado compartido |
|---|---:|
| Horas | 1.447 |
| Cobertura (%) | 54.11195577055978 |
| Anchura media (kWh) | 0.07551572766027369 |
| Por debajo (%) | 38.76986869384934 |
| Por encima (%) | 7.118175535590877 |

La ejecución real comunicada reproduce las métricas compartidas del notebook. No se afirma igualdad exhaustiva de todos los artefactos ni generalización a otros entornos, años o instalaciones.

## Verificación local y límites

Las pruebas sintéticas comprueban contratos, rejilla y retardos, particiones temporales, alineación de métricas, correcciones, cuantiles e integración entre etapas con grids pequeños. Las regresiones adicionales comprueban precisión de lectura y encabezados CSV. Se comprueba la sensibilidad del test de precisión retirando temporalmente `round_trip` y restaurando inmediatamente el código. Esa prueba de retirada vigila tanto el contrato de lectura como los valores, sin exigir diferencias numéricas con todos los lectores predeterminados.

Para verificar el código sin repetir los datos reales:

```powershell
python -m pytest -q
python -m fvaa.pipeline --help
git diff --check
```

Estas comprobaciones no sustituyen una reproducción con los CSV reales. Durante este cierre no se repiten la carga anual ni los entrenamientos; la evidencia real es la comunicada por el usuario. Una comparación exhaustiva de los artefactos y la reproducción en otros entornos quedan fuera de la equivalencia verificada.

El test de 2020 ya fue observado y **no constituye un nuevo periodo independiente para futuras mejoras**. La cobertura del intervalo queda por debajo de la nominal; ordenar cuantiles elimina cruces pero no corrige su calibración. No se ajusta contra test para ocultar esa limitación.

Antes de incorporar irradiación hay que coordinar resolución, objetivo y disponibilidad de las variables en el instante de predicción. Este experimento usa energía horaria, mientras que `docs/data_contract.md` describe potencia media en 15 minutos con horizonte de una hora. El contrato común permanece intacto; no se implementa ni simula irradiación, y la irradiación retrospectiva no se presenta como pronóstico disponible anticipadamente.
