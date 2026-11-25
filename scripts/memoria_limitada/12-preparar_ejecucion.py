"""Genera copias del notebook (no oficiales) para ejecutar con poca RAM (~2 GB).

Solo cambia la carga de la producción (lectura por trozos, mismo DataFrame y misma validación) y la latencia GFS.
No cambia modelos, particiones, variables ni métricas. Los resultados de estas copias se etiquetan
"ejecución con cargador por trozos, no la del notebook oficial". Uso desde la raíz del repo:
  python scripts/memoria_limitada/preparar_ejecucion.py   # crea notebooks/_run_lat6.ipynb y _run_lat3.ipynb (no se versionan)
"""
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
for lat in (6, 3):
    nb = json.load(open('notebooks/FVAA_fase1.ipynb'))
    s = ''.join(nb['cells'][1]['source'])
    s = s.replace('from fvaa.produccion import cargar_produccion, agregar_produccion_horaria',
                  'from fvaa.produccion import cargar_produccion, agregar_produccion_horaria\n'
                  f'sys.path.insert(0, "{AQUI}")\nimport lean; lean.activar()\n'
                  'from trozos import cargar_produccion_trozos as cargar_produccion  # SOLO EN ESTA EJECUCION (2 GB de RAM)')
    nb['cells'][1]['source'] = s.splitlines(keepends=True)
    for c in nb['cells']:
        t = ''.join(c['source'])
        if 'LATENCIA_GFS_H = 6' in t:
            c['source'] = t.replace('LATENCIA_GFS_H = 6', f'LATENCIA_GFS_H = {lat}').splitlines(keepends=True)
    json.dump(nb, open(f'notebooks/_run_lat{lat}.ipynb', 'w'), ensure_ascii=False, indent=1)
