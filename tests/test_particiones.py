"""Pruebas de separación cronológica."""

import pandas as pd
import pytest

from fvaa.particiones import separar_temporalmente


def crear_tabla():
    """Genera seis horas de ejemplo alrededor de los cortes."""
    return pd.DataFrame(
        {"objetivo_kwh": [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]},
        index=pd.date_range(
            "2020-01-01",
            periods=6,
            freq="h",
            tz="UTC",
            name="timestamp",
        ),
    )


def test_cortes_asignan_cada_fila_al_periodo_correcto():
    df = crear_tabla()

    resultado = separar_temporalmente(
        df,
        inicio_validacion="2020-01-01 02:00",
        inicio_test="2020-01-01 04:00",
    )

    pd.testing.assert_frame_equal(resultado["train"], df.iloc[:2])
    pd.testing.assert_frame_equal(resultado["val"], df.iloc[2:4])
    pd.testing.assert_frame_equal(resultado["test"], df.iloc[4:])

    reconstruido = pd.concat([
        resultado["train"],
        resultado["val"],
        resultado["test"],
    ])

    assert reconstruido.index.is_unique
    pd.testing.assert_frame_equal(reconstruido, df)


def test_fechas_de_corte_invertidas_se_rechazan():
    with pytest.raises(ValueError, match="anterior"):
        separar_temporalmente(
            crear_tabla(),
            inicio_validacion="2020-01-01 04:00",
            inicio_test="2020-01-01 02:00",
        )


def test_particion_vacia_se_rechaza():
    with pytest.raises(ValueError, match="vacía"):
        separar_temporalmente(
            crear_tabla(),
            inicio_validacion="2020-01-02",
            inicio_test="2020-01-03",
        )


def test_modificar_una_particion_no_modifica_la_entrada():
    df = crear_tabla()
    original = df.copy(deep=True)

    resultado = separar_temporalmente(
        df,
        inicio_validacion="2020-01-01 02:00",
        inicio_test="2020-01-01 04:00",
    )

    resultado["train"].iloc[0, 0] = 999.0

    pd.testing.assert_frame_equal(df, original)