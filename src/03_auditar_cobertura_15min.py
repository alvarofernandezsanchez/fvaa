from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data" / "raw" / "PTProsumer" / "PR20"
OUTPUT_DIR = ROOT_DIR / "reports" / "data_quality"

EXPECTED_SAMPLES = 15 * 60  # 900 registros de un segundo
CHUNK_SIZE = 1_000_000
THRESHOLDS = [90, 95, 99, 99.5]

files = sorted(
    path
    for path in DATA_DIR.rglob("pr20_prod_*.csv")
    if path.is_file()
)

if not files:
    raise FileNotFoundError(f"No encuentro archivos pr20_prod_*.csv en {DATA_DIR}")

all_details = []
all_summaries = []

for path in files:
    print(f"Analizando {path.name}...")

    counts = pd.Series(dtype="int64")
    first_timestamp = None
    last_timestamp = None

    for chunk in pd.read_csv(
        path,
        usecols=["timestamp"],
        chunksize=CHUNK_SIZE,
    ):
        timestamps = pd.to_datetime(chunk["timestamp"], errors="coerce").dropna()

        if timestamps.empty:
            continue

        intervals = timestamps.dt.floor("15min")
        chunk_counts = intervals.value_counts(sort=False).sort_index()
        counts = counts.add(chunk_counts, fill_value=0)

        chunk_first = intervals.min()
        chunk_last = intervals.max()

        first_timestamp = (
            chunk_first
            if first_timestamp is None
            else min(first_timestamp, chunk_first)
        )
        last_timestamp = (
            chunk_last
            if last_timestamp is None
            else max(last_timestamp, chunk_last)
        )

    if first_timestamp is None:
        print(f"  Sin timestamps válidos: {path.name}")
        continue

    # Incluye también intervalos enteros sin ningún registro.
    full_index = pd.date_range(
        start=first_timestamp,
        end=last_timestamp,
        freq="15min",
    )
    counts = counts.reindex(full_index, fill_value=0).astype("int64")

    coverage = counts / EXPECTED_SAMPLES * 100

    detail = pd.DataFrame(
        {
            "year": path.name.replace("pr20_prod_", "").replace(".csv", ""),
            "timestamp_15min": full_index,
            "samples_received": counts.to_numpy(),
            "expected_samples": EXPECTED_SAMPLES,
            "coverage_pct": coverage.to_numpy(),
        }
    )
    all_details.append(detail)

    summary = {
        "year": detail["year"].iloc[0],
        "intervals": len(detail),
        "coverage_mean_pct": coverage.mean(),
    }

    for threshold in THRESHOLDS:
        summary[f"intervals_at_least_{threshold}_pct"] = int(
            (coverage >= threshold).sum()
        )
        summary[f"share_at_least_{threshold}_pct"] = (
            (coverage >= threshold).mean() * 100
        )

    all_summaries.append(summary)

summary_df = pd.DataFrame(all_summaries)
detail_df = pd.concat(all_details, ignore_index=True)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
summary_path = OUTPUT_DIR / "pr20_cobertura_resumen.csv"
detail_path = OUTPUT_DIR / "pr20_cobertura_15min.csv"

summary_df.to_csv(summary_path, index=False)
detail_df.to_csv(detail_path, index=False)

print("\nResumen por año:")
print(summary_df.round(2).to_string(index=False))
print(f"\nResumen guardado en: {summary_path}")
print(f"Cobertura por intervalo guardada en: {detail_path}")