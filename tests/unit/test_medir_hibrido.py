# T27 | Responsable: Lita | Pruebas de las partes puras de scripts/bench/medir_hibrido.py.
"""Pruebas de T27 sin ejecutar mpirun.

Cubre: factorizaciones procesos x hilos de cada presupuesto (incluidos los extremos p=1 y h=1),
el comando mpirun con --bind-to none, la fila de resumen (speedup y eficiencia sobre núcleos
totales, afinidad registrada) y la generación de figuras a partir del resumen.

Uso:   python3 -m pytest -v tests/unit/test_medir_hibrido.py
"""
import csv
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BENCH = RAIZ / "scripts" / "bench"


def cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, BENCH / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def mh():
    return cargar("medir_hibrido", "medir_hibrido.py")


@pytest.mark.parametrize("presupuesto, esperado", [
    (2, [(1, 2), (2, 1)]),
    (4, [(1, 4), (2, 2), (4, 1)]),
    (8, [(1, 8), (2, 4), (4, 2), (8, 1)]),
    (16, [(1, 16), (2, 8), (4, 4), (8, 2), (16, 1)]),
    (6, [(1, 6), (2, 3), (3, 2), (6, 1)]),
])
def test_factorizaciones(mh, presupuesto, esperado):
    assert mh.factorizaciones(presupuesto) == esperado


def test_factorizaciones_producto_igual_al_presupuesto(mh):
    for b in (2, 4, 8, 16):
        assert all(p * h == b and p >= 1 and h >= 1 for p, h in mh.factorizaciones(b))


def test_plan_recorre_presupuestos_en_orden(mh):
    assert mh.plan([2, 4]) == [(2, 1, 2), (2, 2, 1), (4, 1, 4), (4, 2, 2), (4, 4, 1)]


def test_comando_hibrido_usa_bind_none(mh):
    cmd = mh.comando("mpirun", "pp_hibrido", 2, 4, ["--n", "10"], bind_to="none", oversubscribe=False,
                     schedule="static")
    assert cmd[:5] == ["mpirun", "-np", "2", "--bind-to", "none"]
    assert cmd[5] == "pp_hibrido"
    assert cmd[-4:] == ["--hilos", "4", "--schedule", "static"]


def test_fila_resumen(mh):
    reps = [{"tiempo_s": str(t), "k": "7", "n": "100", "hist512": "1", "hilos": "4", "nodos": "1",
             "distribucion": "h:2"} for t in (5.0, 5.0)]
    cal = dict(reps[0], tiempo_s="6.0")
    fila = mh.fila_resumen(8, 2, 4, cal, reps, t_serial=40.0, fuente_t1="t1.csv", equivalente=True,
                           afinidad="OMP_PROC_BIND=false;OMP_PLACES=cores;--bind-to none",
                           fisicos=24, logicos=24, base={"n": 100})
    assert fila["nucleos_totales"] == 8 and fila["procesos"] == 2 and fila["hilos"] == 4
    assert fila["factorizacion"] == "2x4"
    assert fila["hilos_efectivos"] == 4
    assert fila["speedup"] == pytest.approx(8.0)
    assert fila["eficiencia"] == pytest.approx(1.0)
    assert fila["afinidad"].startswith("OMP_PROC_BIND=false")
    assert fila["t1"] == 5.0 and fila["t_calentamiento"] == "6.0"
    assert fila["equivalente_serial"] == 1 and fila["sobresuscrito"] == 0


def escribir_resumen(ruta):
    campos = ["nucleos_totales", "procesos", "hilos", "factorizacion", "media", "desviacion", "speedup",
              "eficiencia", "equivalente_serial"]
    filas = []
    for b in (2, 4):
        for p, h in [(1, b), (b, 1)]:
            filas.append(dict(nucleos_totales=b, procesos=p, hilos=h, factorizacion=f"{p}x{h}", media=10 / b,
                              desviacion=0.1, speedup=b * 0.9, eficiencia=0.9, equivalente_serial=1))
    with open(ruta, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def test_figuras(mh, tmp_path):
    pytest.importorskip("matplotlib")
    ruta = tmp_path / "hibrido_resumen.csv"
    escribir_resumen(ruta)
    escritos = mh.figuras(ruta, tmp_path / "fig")
    nombres = sorted(p.name for p in escritos)
    assert nombres == ["hibrido_eficiencia.png", "hibrido_eficiencia.svg",
                       "hibrido_speedup.png", "hibrido_speedup.svg"]
    assert all(p.stat().st_size > 0 for p in escritos)
