"""Prepara la irradiación PR20 anual en intervalos de 15 minutos."""

from pathlib import Path

import pandas as pd

from fvaa.irradiacion import (
    agregar_irradiacion_15min,
    cargar_irradiacion,
)


ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT_DIR / "data/raw/PTProsumer/PR20"
OUTPUT_DIR = (
    ROOT_DIR / "data/interim/PTProsumer/PR20/irradiacion_15min"
)
REPORT_DIR = ROOT_DIR / "reports/data_quality"


def main() -> None:
    archivos = sorted(
        ruta
        for ruta in RAW_DIR.rglob("pr20_irrad_*.csv")
        if ruta.is_file()
    )

    if not archivos:
        raise FileNotFoundError(
            f"No se encontraron CSV de irradiación en {RAW_DIR}"
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    resumen_anual = []
    coberturas_por_intervalo = []

    for ruta in archivos:
        anio = int(ruta.stem.rsplit("_", 1)[-1])
        print(f"Procesando irradiación de {anio}...")

        datos = cargar_irradiacion(ruta)
        agregado = agregar_irradiacion_15min(datos)

        ruta_datos = (
            OUTPUT_DIR / f"pr20_irradiacion_15min_{anio}.csv"
        )
        agregado.to_csv(ruta_datos, index_label="timestamp")

        cobertura = agregado["cobertura_pct"]
        fila = {
            "año": anio,
            "intervalos": len(agregado),
            "cobertura_media_pct": cobertura.mean(),
        }

        for umbral in [90, 95, 99, 99.5, 100]:
            nombre = str(umbral).replace(".", "_")
            cantidad = int((cobertura >= umbral).sum())
            fila[f"intervalos_ge_{nombre}_pct"] = cantidad
            fila[f"porcentaje_ge_{nombre}_pct"] = (
                cantidad / len(agregado) * 100
            )

        resumen_anual.append(fila)

        detalle = agregado[
            ["minutos_validos", "cobertura_pct", "intervalo_valido"]
        ].copy()
        detalle["año"] = anio
        coberturas_por_intervalo.append(
            detalle.reset_index()
        )

    resumen = (
        pd.DataFrame(resumen_anual)
        .sort_values("año")
        .reset_index(drop=True)
    )
    detalle_cobertura = pd.concat(
        coberturas_por_intervalo,
        ignore_index=True,
    )

    ruta_resumen = (
        REPORT_DIR / "pr20_irradiacion_cobertura_resumen.csv"
    )
    ruta_detalle = (
        REPORT_DIR / "pr20_irradiacion_cobertura_15min.csv"
    )

    resumen.to_csv(ruta_resumen, index=False)
    detalle_cobertura.to_csv(ruta_detalle, index=False)

    print("\nResumen anual:")
    print(resumen.to_string(index=False))
    print(f"\nDatos agregados: {OUTPUT_DIR}")
    print(f"Resumen de cobertura: {ruta_resumen}")
    print(f"Cobertura por intervalo: {ruta_detalle}")


if __name__ == "__main__":
    main()