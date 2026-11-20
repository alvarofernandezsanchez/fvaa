# Contrato de datos de FVAA — PR20

**Objetivo inicial:** predecir la energía `objetivo_kwh` del intervalo `[t, t+1 h)` al emitir en `t`. Las tablas utilizan UTC y se etiquetan al inicio de la hora.

## Producción

- Datos originales: `active_power_P1` en W, una lectura por segundo.
- Energía horaria estimada: potencia media / 1000, en kWh.
- Cobertura mínima del 99 % por hora, establecida por el equipo.

## Irradiación

- Datos originales: Wh/m² por minuto, etiquetados al final del intervalo.
- Cuatro intervalos completos de 15 minutos forman una hora.
- La suma en Wh/m² equivale numéricamente a la irradiancia media en W/m² durante esa hora.

## Variables y evaluación

- Las horas incompletas quedan como `NaN`, nunca como cero.
- Entradas: energía histórica de 1, 2 y 24 horas, calendario e irradiación histórica de 1 y 24 horas.
- Las entradas deben estar terminadas y disponibles al emitir. La disponibilidad efectiva de CAMS no está verificada, por lo que la comparación con irradiación observada es retrospectiva.
- Los niveles con y sin meteorología deben evaluarse sobre las mismas fechas y con idénticas particiones temporales.
- El test de 2020 ya se ha observado y no es una evaluación independiente nueva.

## Objetivos posteriores

Predecir también el perfil de energía de las próximas 24 horas y su energía total acumulada, utilizando una única emisión en `t`.

Los archivos originales no se modifican. Se conserva documentada la discrepancia entre la fecha de fin indicada en los metadatos de 2023 y los últimos registros de sus CSV.