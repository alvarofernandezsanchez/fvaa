"""Figuras exportables sin interfaz gráfica ni modificación de datos."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def dibujar_predicciones(tabla, ruta, titulo, inicio=None, fin=None):
    vista = tabla.loc[inicio:fin] if inicio is not None else tabla.iloc[:168]
    if vista.empty:
        return
    ax = vista.plot(figsize=(14,5), title=titulo)
    ax.set(xlabel="Fecha y hora (UTC)", ylabel="Energía (kWh)")
    ax.figure.tight_layout()
    ax.figure.savefig(ruta, dpi=130)
    plt.close(ax.figure)


def dibujar_intervalo(y, cuantiles, ruta, inicio=None, fin=None):
    q = cuantiles.loc[inicio:fin] if inicio is not None else cuantiles.iloc[:168]
    if q.empty:
        return
    fig, ax = plt.subplots(figsize=(14,5))
    ax.plot(q.index,y.loc[q.index],label="Producción real")
    ax.plot(q.index,q.q50,label="Mediana estimada")
    ax.fill_between(q.index,q.q10.to_numpy(),q.q90.to_numpy(),alpha=.25,label="Intervalo q10–q90")
    ax.set(title="PR20: intervalo predictivo", xlabel="Fecha y hora (UTC)",ylabel="Energía (kWh)")
    ax.legend(); fig.tight_layout(); fig.savefig(ruta,dpi=130); plt.close(fig)
