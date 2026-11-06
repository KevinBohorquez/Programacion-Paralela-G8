"""Pruebas de T26 (scripts/bench/ejecutar_barridos.py) sin binarios reales.

Cubre la generación del plan X1/X2/X3, las factorizaciones del híbrido, la carga de la escalabilidad
débil, la marca de sobresuscripción, la construcción de comandos (mpirun --bind-to none en el
híbrido), la verificación de k entre backends y la escritura del CSV con un ejecutor falso.

Uso:   python3 -m pytest -v tests/unit/test_ejecutar_barridos.py
"""
import csv
import importlib.util
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BENCH = RAIZ / "scripts" / "bench"


def cargar(nombre, archivo):
    sys.path.insert(0, str(BENCH))
    spec = importlib.util.spec_from_file_location(nombre, BENCH / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def eb():
    return cargar("ejecutar_barridos", "ejecutar_barridos.py")


@pytest.fixture(scope="module")
def cb():
    return cargar("_comun_bench", "_comun_bench.py")


# ---------- factorizaciones del híbrido ----------
def test_factorizaciones_excluyen_casos_puros_si_hay_mixtos(eb):
    assert eb.factorizaciones(16) == [(2, 8), (4, 4), (8, 2)]
    assert eb.factorizaciones(8) == [(2, 4), (4, 2)]
    assert eb.factorizaciones(4) == [(2, 2)]


def test_factorizaciones_sin_mixtos_usan_todos_los_pares(eb):
    assert eb.factorizaciones(1) == [(1, 1)]
    assert eb.factorizaciones(2) == [(1, 2), (2, 1)]
    assert eb.factorizaciones(7) == [(1, 7), (7, 1)]


def test_parsear_factorizaciones(eb):
    assert eb.parsear_factorizaciones("2x8, 4x4,8X2") == [(2, 8), (4, 4), (8, 2)]
    assert eb.parsear_factorizaciones("") is None
    with pytest.raises(ValueError):
        eb.parsear_factorizaciones("2y8")


# ---------- plan ----------
def test_x1_fija_n_y_recorre_recursos(eb):
    plan = eb.generar_plan("x1", ["openmp", "mpi_estatico"], [1, 2, 4], n=1000)
    assert {p.n for p in plan} == {1000}
    omp = [(p.procesos, p.hilos) for p in plan if p.backend == "openmp"]
    mpi = [(p.procesos, p.hilos) for p in plan if p.backend == "mpi_estatico"]
    assert omp == [(1, 1), (1, 2), (1, 4)]
    assert mpi == [(1, 1), (2, 1), (4, 1)]


def test_serial_solo_con_un_recurso_y_va_primero(eb):
    plan = eb.generar_plan("x1", ["openmp", "serial"], [2, 4], n=10)
    assert plan[0].backend == "serial" and plan[0].recursos == 1
    assert sum(p.backend == "serial" for p in plan) == 1


def test_x2_n_proporcional_a_recursos(eb):
    plan = eb.generar_plan("x2", ["mpi_dinamico"], [1, 2, 4, 8, 16], n=500)
    assert [(p.procesos, p.n) for p in plan] == [(1, 500), (2, 1000), (4, 2000), (8, 4000), (16, 8000)]


def test_x2_hibrido_usa_el_presupuesto_total(eb):
    plan = eb.generar_plan("x2", ["hibrido"], [16], n=100)
    assert [(p.procesos, p.hilos, p.n) for p in plan] == [(2, 8, 1600), (4, 4, 1600), (8, 2, 1600)]


def test_x3_barre_cargas_con_recursos_fijos(eb):
    plan = eb.generar_plan("x3", ["openmp"], [8], n=0, cargas=[100, 200, 300])
    assert [(p.n, p.hilos) for p in plan] == [(100, 8), (200, 8), (300, 8)]


def test_x3_sin_cargas_falla(eb):
    with pytest.raises(ValueError):
        eb.generar_plan("x3", ["openmp"], [8], n=0, cargas=None)


def test_hibrido_con_factorizaciones_explicitas_filtra_por_presupuesto(eb):
    plan = eb.generar_plan("x1", ["hibrido"], [8, 16], n=10, factorizaciones=[(2, 8), (4, 2), (3, 3)])
    assert [(p.procesos, p.hilos) for p in plan] == [(4, 2), (2, 8)]


def test_backend_desconocido(eb):
    with pytest.raises(ValueError):
        eb.generar_plan("x1", ["cuda"], [1], n=10)


# ---------- sobresuscripción y comandos ----------
def test_sobresuscrito_compara_recursos_con_nucleos(eb):
    p16 = eb.Punto("x1", "openmp", 10, 1, 16)
    assert eb.sobresuscrito(p16, 8) is True
    assert eb.sobresuscrito(p16, 16) is False
    assert eb.sobresuscrito(eb.Punto("x1", "hibrido", 10, 4, 4), 12) is True


def opciones(eb, **cambios):
    base = dict(build_dir="/b", config="/c.yaml", semilla=7, config_id=0, schedule="static", lote=0,
                hosts=[], hostfile="", red_tcp="", bind_mpi="", omp_bind="close", omp_places="cores",
                mpirun_extra=[], nucleos=24, slots=24)
    base.update(cambios)
    return eb.Opciones(**base)


def test_comando_openmp(eb):
    cmd = eb.comando(eb.Punto("x1", "openmp", 100, 1, 4), opciones(eb))
    assert cmd[0] == "/b/src/backends/openmp/pp_openmp"
    assert cmd[cmd.index("--hilos") + 1] == "4" and cmd[cmd.index("--schedule") + 1] == "static"
    assert cmd[cmd.index("--n") + 1] == "100" and "--silencioso" in cmd


def test_comando_hibrido_usa_bind_to_none_y_exporta_omp(eb):
    cmd = eb.comando(eb.Punto("x1", "hibrido", 100, 2, 8), opciones(eb))
    assert cmd[:3] == ["mpirun", "-np", "2"]
    assert cmd[cmd.index("--bind-to") + 1] == "none"
    assert "OMP_PROC_BIND" in cmd and "OMP_PLACES" in cmd
    assert cmd[cmd.index("--hilos") + 1] == "8"
    assert "/b/src/backends/hybrid/pp_hibrido" in cmd


def test_comando_mpi_con_hosts_red_y_oversubscribe(eb):
    o = opciones(eb, hosts=[("nodo1", 2), ("nodo2", 2)], red_tcp="eth0", slots=4, lote=500)
    cmd = eb.comando(eb.Punto("x1", "mpi_dinamico", 100, 8, 1), o)
    assert cmd[cmd.index("--host") + 1] == "nodo1:2,nodo2:2"
    assert "--oversubscribe" in cmd and "slot" in cmd
    assert cmd[cmd.index("btl_tcp_if_include") + 1] == "eth0"
    assert cmd[cmd.index("--lote") + 1] == "500"
    cmd4 = eb.comando(eb.Punto("x1", "mpi_dinamico", 100, 4, 1), o)
    assert "--oversubscribe" not in cmd4


def test_comando_serial_sin_mpirun(eb):
    cmd = eb.comando(eb.Punto("x1", "serial", 100, 1, 1), opciones(eb))
    assert cmd[0].endswith("pp_serial") and "--hilos" not in cmd


# ---------- ejecución con un ejecutor falso ----------
class Falso:
    """Devuelve k = n // 10 salvo para el backend `malo`; registra las llamadas."""

    def __init__(self, malo=None):
        self.llamadas = []
        self.malo = malo

    def __call__(self, punto):
        self.llamadas.append(punto)
        k = punto.n // 10 + (1 if punto.backend == self.malo else 0)
        verif = [] if punto.procesos == 1 else [{"rango": r, "n_local": punto.n // punto.procesos}
                                               for r in range(punto.procesos)]
        return {"tiempo_s": str(1.0 / punto.recursos), "k": str(k), "n": str(punto.n),
                "hist512": "1;2", "commit": "abc", "columna_nueva": "x"}, verif


META = {"commit": "deadbeef", "cpu": "CPU falsa", "nucleos_fisicos": 4}


def test_ejecutar_plan_calentamiento_reps_y_equivalencia(eb):
    plan = eb.generar_plan("x1", ["serial", "openmp"], [1, 2], n=1000)
    falso = Falso()
    filas = eb.ejecutar_plan(plan, falso, repeticiones=3, nucleos=4, meta=META, referencia="serial")
    # serial (ref + 1 calentamiento + 3) se reutiliza como referencia: no hay corrida extra
    assert len(falso.llamadas) == 3 * 4
    assert all(f["equivalente"] == 1 for f in filas)
    omp2 = filas[-1]
    assert omp2["backend"] == "openmp" and omp2["hilos"] == 2
    assert omp2["media"] == pytest.approx(0.5) and omp2["repeticiones"] == 3
    assert omp2["k"] == "100" and omp2["k_ref"] == "100" and omp2["commit"] == "deadbeef"
    assert omp2["commit_binario"] == "abc" and omp2["sobresuscrito"] == 0


def test_referencia_serial_se_corre_una_vez_por_n(eb):
    plan = eb.generar_plan("x2", ["openmp"], [1, 2], n=100)
    falso = Falso()
    filas = eb.ejecutar_plan(plan, falso, repeticiones=1, nucleos=4, meta=META, referencia="serial")
    refs = [p for p in falso.llamadas if p.backend == "serial"]
    assert sorted(p.n for p in refs) == [100, 200]
    assert all(f["equivalente"] == 1 for f in filas)


def test_k_distinto_marca_no_equivalente(eb):
    plan = eb.generar_plan("x1", ["serial", "mpi_estatico"], [1, 2], n=1000)
    filas = eb.ejecutar_plan(plan, Falso(malo="mpi_estatico"), repeticiones=1, nucleos=4, meta=META,
                             referencia="serial")
    assert [f["equivalente"] for f in filas] == [1, 0, 0]


def test_referencia_ninguna_deja_vacio(eb):
    plan = eb.generar_plan("x1", ["openmp"], [2], n=10)
    falso = Falso()
    filas = eb.ejecutar_plan(plan, falso, repeticiones=1, nucleos=4, meta=META, referencia="ninguna")
    assert filas[0]["equivalente"] == "" and len(falso.llamadas) == 2


def test_desbalance_y_trabajo_por_rango(eb):
    plan = eb.generar_plan("x1", ["mpi_estatico"], [4], n=400)
    fila = eb.ejecutar_plan(plan, Falso(), repeticiones=1, nucleos=4, meta=META, referencia="ninguna")[0]
    assert fila["trabajo_rangos"] == "100;100;100;100"
    assert fila["desbalance"] == pytest.approx(1.0)


def test_escribir_csv_y_anexar(eb, tmp_path):
    plan = eb.generar_plan("x1", ["openmp"], [1, 2], n=10)
    filas = eb.ejecutar_plan(plan, Falso(), repeticiones=2, nucleos=1, meta=META, referencia="ninguna")
    ruta = tmp_path / "sub" / "x1.csv"
    eb.escribir_csv(filas, ruta)
    eb.escribir_csv(filas[:1], ruta, anexar=True)
    with open(ruta, newline="") as f:
        leidas = list(csv.DictReader(f))
    assert len(leidas) == 3
    assert leidas[1]["sobresuscrito"] == "1"  # 2 hilos > 1 núcleo
    assert leidas[0]["tiempos"].count(";") == 1
    for col in ("experimento", "backend", "n", "procesos", "hilos", "recursos", "nodos", "afinidad",
                "media", "desviacion", "k", "equivalente", "commit", "cpu", "fecha"):
        assert col in leidas[0]


def test_estimacion_de_duracion(eb):
    plan = eb.generar_plan("x1", ["openmp"], [1, 2], n=1_000_000)
    # (1 calentamiento + 2 reps) * 1e6 * 3 us = 9 s con 1 hilo; 4.5 s con 2
    assert eb.estimar_segundos(plan, repeticiones=2, us_por_escenario=3.0, nucleos=24) == pytest.approx(13.5)


# ---------- utilidades comunes ----------
def test_parsear_verif(cb):
    texto = ("[verif] backend=mpi_dinamico procesos=3\n[verif] rango=0 bloques=4 n_local=0\n"
             "[verif] rango=1 bloques=2 n_local=125000\n[verif] rango=2 bloques=2 n_local=75000\n"
             "[verif] suma_n=200000 k=1 estado=OK\n")
    r = cb.parsear_verif(texto)
    assert [x["n_local"] for x in r] == [0, 125000, 75000] and r[1]["bloques"] == 2


def test_leer_fila_simulador_tolera_columnas_extra(cb, tmp_path):
    ruta = tmp_path / "r.csv"
    ruta.write_text("backend,n,k,tiempo_s,hist512,nodos,bloques\nserial,10,3,0.5,1;2,1,\n"
                    "serial,10,3,0.4,1;2,1,\n")
    fila = cb.leer_fila_simulador(ruta)
    assert fila["tiempo_s"] == "0.4" and fila["nodos"] == "1"


def test_hosts_y_asignacion(cb, tmp_path):
    hosts = cb.parsear_hosts("nodo1:2,nodo2:2,nodo3")
    assert hosts == [("nodo1", 2), ("nodo2", 2), ("nodo3", 1)]
    assert cb.asignar_rangos(hosts, 4) == ["nodo1", "nodo1", "nodo2", "nodo2"]
    assert cb.asignar_rangos(hosts, 7) == ["nodo1", "nodo1", "nodo2", "nodo2", "nodo3", "nodo1", "nodo2"]
    hf = tmp_path / "hosts"
    hf.write_text("# comentario\nnodo1 slots=8\nnodo2\n")
    assert cb.leer_hostfile(hf) == [("nodo1", 8), ("nodo2", 1)]


def test_desbalance_ignora_maestro(cb):
    assert cb.desbalance([0, 150, 50]) == pytest.approx(1.5)
    assert cb.desbalance([]) == ""


def test_bind_omp_auto_usa_false_en_hibrido_y_close_en_openmp(eb):
    from types import SimpleNamespace
    o = SimpleNamespace(omp_bind="auto")
    assert eb.bind_omp(SimpleNamespace(backend="hibrido"), o) == "false"
    assert eb.bind_omp(SimpleNamespace(backend="openmp"), o) == "close"
    assert eb.bind_omp(SimpleNamespace(backend="hibrido"), SimpleNamespace(omp_bind="spread")) == "spread"
