from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

ROOT_DIR = Path(__file__).resolve().parents[1]

print(f"Proyecto: {ROOT_DIR}")
print(f"pandas: {pd.__version__}")
print(f"matplotlib: {matplotlib.__version__}")
print(f"scikit-learn: {sklearn.__version__}")
