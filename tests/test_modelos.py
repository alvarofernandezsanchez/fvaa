
import numpy as np
import pandas as pd

from fvaa.modelos import crear_modelo, predecir


def test_ridge():
    X = pd.DataFrame({
        "energia_1h": [0.0, 0.1, 0.2, 0.3],
        "ghi_1h": [0.0, 100.0, 200.0, 300.0]
    })

    y = pd.Series([0.0, 0.1, 0.2, 0.3])

    modelo = crear_modelo("ridge", {"alpha": 1.0}).fit(X, y)
    _, pred = predecir(modelo, X, minimo_cero=True)

    assert np.isfinite(pred).all()
    assert (pred >= 0).all()
