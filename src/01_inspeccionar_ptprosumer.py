from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import sklearn

ROOT_DIR = Path(__file__).resolve().parents[1]

print(f"Proyecto: {ROOT_DIR}")
print(f"pandas: {pd.__version__}")
print(f"matplotlib: {matplotlib.__version__}")
print(f"scikit-learn: {sklearn.__version__}")


DATA_DIR = ROOT_DIR / "data" / "raw" / "PTProsumer" / "PR20"
files = sorted(
    path for path in DATA_DIR.rglob("*.csv*")
    if path.is_file()
)

print(f"\nCarpeta de datos: {DATA_DIR}")
print(f"Archivos encontrados: {len(files)}")

for path in files:
    print(f"\n--- {path.relative_to(ROOT_DIR)} ---")
    print(f"Tamaño: {path.stat().st_size / (1024 ** 2):.2f} MB")

    try:
        sample = pd.read_csv(path, nrows=3)
        print("Columnas:", sample.columns.tolist())
        print("Tipos:", sample.dtypes.to_dict())
        print(sample.head(2).to_string(index=False))
    except Exception as error:
        print(f"Error al leer la muestra: {error}")

def auditar_timestamps(path, frecuencia_segundos):
    filas = 0
    timestamps_invalidos = 0
    duplicados = 0
    desordenados = 0
    tramos_con_hueco = 0
    primero = ultimo = minimo = maximo = anterior = None

    for chunk in pd.read_csv(
        path,
        usecols=["timestamp"],
        chunksize=1_000_000,
    ):
        filas += len(chunk)
        ts = pd.to_datetime(chunk["timestamp"], errors="coerce")
        timestamps_invalidos += int(ts.isna().sum())
        ts = ts.dropna()

        if ts.empty:
            continue

        if primero is None:
            primero = ts.iloc[0]

        minimo_actual = ts.min()
        maximo_actual = ts.max()
        minimo = minimo_actual if minimo is None else min(minimo, minimo_actual)
        maximo = maximo_actual if maximo is None else max(maximo, maximo_actual)

        diferencias = ts.diff()
        if anterior is not None:
            diferencias.iloc[0] = ts.iloc[0] - anterior

        frecuencia = pd.Timedelta(seconds=frecuencia_segundos)
        duplicados += int((diferencias == pd.Timedelta(0)).sum())
        desordenados += int((diferencias < pd.Timedelta(0)).sum())
        tramos_con_hueco += int((diferencias > frecuencia).sum())

        anterior = ts.iloc[-1]
        ultimo = anterior

    return {
        "filas": filas,
        "primero_en_archivo": primero,
        "ultimo_en_archivo": ultimo,
        "timestamp_minimo": minimo,
        "timestamp_maximo": maximo,
        "timestamps_invalidos": timestamps_invalidos,
        "duplicados": duplicados,
        "desordenados": desordenados,
        "tramos_con_hueco": tramos_con_hueco,
    }


print("\n=== AUDITORÍA TEMPORAL ===")
for path in files:
    frecuencia = 60 if "irrad" in path.name.lower() else 1
    resultado = auditar_timestamps(path, frecuencia)
    print(f"\n{path.name}")
    for campo, valor in resultado.items():
        print(f"  {campo}: {valor}")