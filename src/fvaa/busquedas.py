"""Búsquedas temporales; nunca reciben el conjunto de test."""
import pandas as pd
from sklearn.metrics import make_scorer
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from .modelos import crear_modelo, mae_no_negativo


def buscar_temporal(X, y, especificacion, n_splits=3, n_jobs=-1):
    cv = TimeSeriesSplit(n_splits=n_splits)
    limites = []
    for numero, (train, val) in enumerate(cv.split(X), 1):
        limites.append({"particion": numero, "train_inicio": X.index[train[0]],
                        "train_fin": X.index[train[-1]], "val_inicio": X.index[val[0]],
                        "val_fin": X.index[val[-1]]})
    scorers = {"neg_mean_absolute_error": "neg_mean_absolute_error",
               "mae_no_negativo": make_scorer(mae_no_negativo, greater_is_better=False)}
    busqueda = GridSearchCV(
        crear_modelo(especificacion["tipo"], especificacion["parametros"]),
        especificacion["grid"], scoring=scorers[especificacion["scorer"]], cv=cv,
        n_jobs=n_jobs, return_train_score=True, error_score="raise", verbose=1)
    busqueda.fit(X, y)
    resultados = pd.DataFrame(busqueda.cv_results_)
    # Mantener scores originales y errores positivos por cada partición.
    for columna in list(resultados):
        if columna.endswith(("test_score", "train_score")) and not columna.startswith("std_"):
            resultados["MAE_" + columna] = -resultados[columna]
    return busqueda, resultados, pd.DataFrame(limites)
