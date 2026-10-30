# Contrato de datos — PR20

## Alcance
- Instalación: PR20.
- Objetivo: predecir la potencia fotovoltaica media de un intervalo de 15 minutos,
  con horizonte de una hora.
- Periodo disponible en los archivos: 2019-11-22 a 2023-12-31.

## Producción
- Archivo: `pr20_prod_<año>.csv`.
- Cadencia nominal: 1 segundo.
- `timestamp`: instante de lectura en UTC.
- `active_power_P1`: potencia activa en W.
- Objetivo agregado: media de las lecturas válidas de cada intervalo de 15 minutos.
- Registrar cuántas lecturas válidas contribuyen a cada intervalo.

## Irradiación
- Archivo: `pr20_irrad_<año>.csv`.
- Cadencia: 1 minuto.
- `timestamp`: final del intervalo observado, en UTC.
- Variables: Wh/m² por intervalo de un minuto.
- Para cada intervalo de 15 minutos, sumar los valores de los 15 intervalos
  de un minuto. Para expresarlo como irradiancia media en W/m², dividir la
  energía acumulada por 0,25 horas.

## Tiempos y ausencias
- Interpretar los timestamps del CSV como UTC y hacer explícita la zona horaria
  al procesarlos.
- Mantener separados los ceros medidos y los timestamps ausentes.
- No rellenar ausencias con cero.
- Registrar la cobertura de producción e irradiación por intervalo.

## Observación sobre los metadatos
- `metadata.csv` indica fin de recogida: 2023-12-21.
- Los CSV contienen registros hasta 2023-12-31 23:59:59, con producción distinta
  de cero después del 21 de diciembre.
- Conservar los datos observados hasta el 31 de diciembre y dejar registrada
  esta discrepancia; no modificar los archivos originales.