from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "raw" / "PTProsumer" / "PR20"
files = sorted(
    path for path in DATA_DIR.rglob("*.csv*")
    if path.is_file()
)

for path in files:
    if "irrad" in path.name.lower():
        columns = [
            "TOA",
            "Clear sky GHI", "Clear sky BHI",
            "Clear sky DHI", "Clear sky BNI",
            "GHI", "BHI", "DHI", "BNI",
        ]
    else:
        columns = ["active_power_P1"]

    stats = {
        column: {
            "validos": 0,
            "nulos_o_no_numericos": 0,
            "ceros": 0,
            "negativos": 0,
            "suma": 0.0,
            "minimo": None,
            "maximo": None,
        }
        for column in columns
    }

    for chunk in pd.read_csv(
        path,
        usecols=columns,
        chunksize=1_000_000,
    ):
        for column in columns:
            values = pd.to_numeric(chunk[column], errors="coerce")
            stats[column]["nulos_o_no_numericos"] += int(values.isna().sum())
            values = values.dropna()

            if values.empty:
                continue

            stats[column]["validos"] += len(values)
            stats[column]["ceros"] += int((values == 0).sum())
            stats[column]["negativos"] += int((values < 0).sum())
            stats[column]["suma"] += float(values.sum())

            current_min = float(values.min())
            current_max = float(values.max())

            if stats[column]["minimo"] is None:
                stats[column]["minimo"] = current_min
                stats[column]["maximo"] = current_max
            else:
                stats[column]["minimo"] = min(
                    stats[column]["minimo"], current_min
                )
                stats[column]["maximo"] = max(
                    stats[column]["maximo"], current_max
                )

    print(f"\n--- {path.name} ---")
    for column, result in stats.items():
        mean = (
            result["suma"] / result["validos"]
            if result["validos"]
            else None
        )
        print(
            f"{column}: válidos={result['validos']}, "
            f"nulos/no numéricos={result['nulos_o_no_numericos']}, "
            f"ceros={result['ceros']}, negativos={result['negativos']}, "
            f"mín={result['minimo']}, máx={result['maximo']}, "
            f"media={mean}"
        )