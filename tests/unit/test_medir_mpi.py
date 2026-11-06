# T21 | Responsable: Ashley | Pruebas de las partes puras de scripts/bench/medir_mpi.py y _comun_mpi.py.
"""Pruebas de T21 sin ejecutar mpirun.

Cubre: lectura de las líneas [verif] de los ejecutables MPI, procesos de cómputo en E2 (el rango 0
es maestro y no simula), speedup y eficiencia, lectura de T1, comparación V1 con el secuencial,
construcción del comando mpirun y el plan de puntos del barrido.

Uso:   python3 -m pytest -v tests/unit/test_medir_mpi.py
"""
import csv
import importlib.util
import statistics
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
def cm():
    return cargar("_comun_mpi", "_comun_mpi.py")


@pytest.fixture(scope="module")
def mm():
    return cargar("medir_mpi", "medir_mpi.py")


SALIDA_E2 = """\
[verif] backend=mpi_dinamico procesos=3 n_solicitado=1000 nivel_hilos_mpi=MPI_THREAD_FUNNELED nucleo=pp_core
[verif] rango=0 bloques=10 n_local=0
[verif] rango=1 bloques=6 n_local=600
[verif] rango=2 bloques=4 n_local=400
[verif] suma_n=1000 suma_n_rangos=1000 suma_hist=1000 k=121 estado=OK
[verif] v1_referencia=OK k_ref=121
[verif] tiempo_s=0.00379382
"""

SALIDA_E1 = """\
[verif] backend=mpi_estatico procesos=2 n_solicitado=11 nivel_hilos_mpi=MPI_THREAD_FUNNELED nucleo=pp_core
[verif] rango=0 inicio=0 fin=6 n_local=6
[verif] rango=1 inicio=6 fin=11 n_local=5
[verif] suma_n=11 suma_n_rangos=11 suma_hist=11 k=2 estado=OK
[verif] tiempo_s=0.001
"""


def test_parse_verif_dinamico(cm):
    v = cm.parse_verif(SALIDA_E2)
    assert v["backend"] == "mpi_dinamico"
    assert v["procesos"] == 3
    assert v["estado"] == "OK" and v["k"] == 121 and v["suma_n"] == 1000
    assert v["v1"] == "OK"
    assert [r["n_local"] for r in v["rangos"]] == [0, 600, 400]
    assert [r["bloques"] for r in v["rangos"]] == [10, 6, 4]
    assert v["tiempo_s"] == pytest.approx(0.00379382)


def test_parse_verif_estatico_sin_v1(cm):
    v = cm.parse_verif(SALIDA_E1)
    assert v["v1"] is None
    assert [(r["inicio"], r["fin"]) for r in v["rangos"]] == [(0, 6), (6, 11)]
    assert v["rangos"][0]["bloques"] is None


def test_reparto_y_bloques_texto(cm):
    v = cm.parse_verif(SALIDA_E2)
    assert cm.reparto_texto(v["rangos"]) == "0:0;1:600;2:400"
    assert cm.bloques_texto(v["rangos"]) == "0:10;1:6;2:4"
    assert cm.bloques_texto(cm.parse_verif(SALIDA_E1)["rangos"]) == ""


def test_procesos_de_computo_e2_excluye_al_maestro(cm):
    assert cm.procesos_de_computo("mpi_dinamico", 4) == 3
    assert cm.procesos_de_computo("mpi_dinamico", 1) == 1  # sin trabajadores, el rango 0 simula todo
    assert cm.procesos_de_computo("mpi_estatico", 4) == 4


def test_resumir_speedup_eficiencia(cm):
    t = [1.0, 1.2, 0.8, 1.1, 0.9]
    assert cm.resumir(t) == (pytest.approx(statistics.mean(t)), pytest.approx(statistics.stdev(t)))
    assert cm.resumir([2.0]) == (2.0, 0.0)
    assert cm.speedup(60.0, 15.0) == pytest.approx(4.0)
    assert cm.eficiencia(60.0, 15.0, 8) == pytest.approx(0.5)
    assert cm.speedup(None, 1.0) == "" and cm.eficiencia(None, 1.0, 2) == ""


def test_sobresuscripcion(cm):
    assert cm.sobresuscrito(16, 24) == 0
    assert cm.sobresuscrito(32, 24) == 1


def test_comando_mpi(cm):
    cmd = cm.comando_mpi("mpirun", 4, "pp_mpi_estatico", ["--n", "10"], bind_to="core", oversubscribe=False)
    assert cmd == ["mpirun", "-np", "4", "--bind-to", "core", "pp_mpi_estatico", "--n", "10"]
    cmd = cm.comando_mpi("mpirun", 4, "x", [], bind_to="none", oversubscribe=True)
    assert cmd == ["mpirun", "-np", "4", "--bind-to", "none", "--oversubscribe", "x"]


def test_equivalente_compara_k_n_hist(cm):
    ref = {"k": "5", "n": "10", "hist512": "1;2"}
    assert cm.equivalente({"k": "5", "n": "10", "hist512": "1;2", "tiempo_s": "9"}, ref)
    assert not cm.equivalente({"k": "6", "n": "10", "hist512": "1;2"}, ref)
    assert not cm.equivalente({"k": "5", "n": "10", "hist512": "1;3"}, ref)


def escribir_t1(ruta, **cambios):
    fila = dict(backend="serial", n="20000000", semilla="20261015", config_id="0", dias="120",
                k="2122915", media="59.70", desviacion="0.77")
    fila.update(cambios)
    with open(ruta, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fila))
        w.writeheader()
        w.writerow(fila)


def test_leer_t1_coincide(cm, tmp_path):
    ruta = tmp_path / "t1.csv"
    escribir_t1(ruta)
    t1 = cm.leer_t1(ruta, n=20_000_000, semilla=20261015, config_id=0)
    assert t1 == {"media": pytest.approx(59.70), "k": "2122915", "dias": "120"}


def test_leer_t1_sin_coincidencia_o_ausente(cm, tmp_path):
    ruta = tmp_path / "t1.csv"
    escribir_t1(ruta, n="1000")
    assert cm.leer_t1(ruta, n=20_000_000, semilla=20261015, config_id=0) is None
    assert cm.leer_t1(tmp_path / "no_existe.csv", n=1, semilla=1, config_id=0) is None


def test_plan_de_puntos(mm):
    puntos = mm.plan(["mpi_estatico", "mpi_dinamico"], [2, 4])
    assert puntos == [("mpi_estatico", 2), ("mpi_estatico", 4), ("mpi_dinamico", 2), ("mpi_dinamico", 4)]


def test_lista_enteros(cm):
    assert cm.lista_enteros("2, 4,8,16") == [2, 4, 8, 16]
    with pytest.raises(ValueError):
        cm.lista_enteros("2,0")


def test_fila_resumen_e2_registra_computo(mm):
    reps = [{"tiempo_s": str(t), "k": "7", "n": "100", "hist512": "1", "nodos": "1", "distribucion": "h:4"}
            for t in (2.0, 2.0, 2.0)]
    cal = dict(reps[0], tiempo_s="3.0")
    verif = {"rangos": [{"rango": i, "n_local": n, "bloques": b, "inicio": None, "fin": None, "hilos": None}
                        for i, (n, b) in enumerate([(0, 4), (50, 2), (30, 1), (20, 1)])]}
    fila = mm.fila_resumen("mpi_dinamico", 4, cal, reps, verif, t_serial=8.0, fuente_t1="x", equivalente=True,
                           fisicos=24, logicos=24, base={"n": 100})
    assert fila["t_serial"] == 8.0 and fila["fuente_t1"] == "x" and fila["n"] == 100
    assert fila["procesos"] == 4 and fila["procesos_computo"] == 3
    assert fila["media"] == pytest.approx(2.0) and fila["desviacion"] == 0.0
    assert fila["speedup"] == pytest.approx(4.0)
    assert fila["eficiencia"] == pytest.approx(1.0)
    assert fila["eficiencia_computo"] == pytest.approx(4.0 / 3)
    assert fila["reparto_rangos"] == "0:0;1:50;2:30;3:20"
    assert fila["bloques_rangos"] == "0:4;1:2;2:1;3:1"
    assert fila["t1"] == 2.0 and fila["t3"] == 2.0 and "t4" not in fila
    assert fila["equivalente_serial"] == 1 and fila["sobresuscrito"] == 0
    assert "maestro" in fila["nota"]
