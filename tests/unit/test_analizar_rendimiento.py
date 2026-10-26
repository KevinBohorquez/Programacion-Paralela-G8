"""T33: métricas de rendimiento de analizar-rendimiento.py sobre CSV sintéticos mínimos."""

import csv
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "scripts" / "bench"
sys.path.insert(0, str(BENCH))


def cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, BENCH / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ar = cargar("analizar_rendimiento", "analizar-rendimiento.py")
ca = importlib.import_module("_comun_analisis")

META = dict(cpu="Intel(R) Core(TM) Ultra 9 275HX", nucleos_fisicos=24, nucleos_logicos=24, commit="abc123")


def escribir(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    campos = []
    for f in filas:
        campos += [c for c in f if c not in campos]
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, restval="")
        w.writeheader()
        w.writerows(filas)


def bench_sintetico(d):
    """T1 = 10 s con N = 1000; OpenMP con S = 2 (p=2) y S = 3.2 (p=4); E2 con 4 procesos."""
    escribir(d / "secuencial_t1.csv", [dict(backend="serial", n=1000, media=10.0, desviacion=0.1, **META)])
    escribir(d / "openmp.csv", [
        dict(backend="openmp", hilos=2, schedule="static", n=1000, t1=4.9, t2=5.1, media=5.0,
             desviacion=0.1, sobresuscrito=0, **META),
        dict(backend="openmp", hilos=4, schedule="static", n=1000, t1=3.125, t2=3.125, media=3.125,
             desviacion=0.0, sobresuscrito=0, **META),
    ])
    escribir(d / "mpi_resumen.csv", [
        dict(esquema="mpi_dinamico", procesos=4, procesos_computo=3, n=1000, t1=4.0, t2=4.0, media=4.0,
             desviacion=0.0, t_serial=10.0, sobresuscrito=0, **META),
    ])


def test_karp_flatt_formula_exacta():
    # S = 3.2 con p = 4: e = (1/3.2 - 1/4) / (1 - 1/4) = 0.0625 / 0.75
    assert ca.karp_flatt(3.2, 4) == pytest.approx((1 / 3.2 - 0.25) / 0.75)
    assert ca.karp_flatt(2.0, 2) == pytest.approx(0.0)
    assert ca.karp_flatt(2.0, 1) is None


def test_metricas_por_fila(tmp_path):
    bench_sintetico(tmp_path)
    filas = ar.analizar(tmp_path)
    omp4 = next(f for f in filas if f["backend"] == "openmp" and f["recursos"] == 4)
    assert omp4["speedup"] == pytest.approx(3.2)
    assert omp4["eficiencia"] == pytest.approx(0.8)
    assert omp4["throughput"] == pytest.approx(1000 / 3.125)
    assert omp4["karp_flatt"] == pytest.approx((1 / 3.2 - 0.25) / 0.75)
    assert omp4["fuente_t1"] == "secuencial_t1.csv"
    omp2 = next(f for f in filas if f["backend"] == "openmp" and f["recursos"] == 2)
    assert omp2["cv"] == pytest.approx(0.1 / 5.0)


def test_e2_eficiencia_sobre_rangos_de_computo(tmp_path):
    bench_sintetico(tmp_path)
    e2 = next(f for f in ar.analizar(tmp_path) if f["backend"] == "mpi_dinamico")
    assert e2["speedup"] == pytest.approx(2.5)
    assert e2["eficiencia"] == pytest.approx(2.5 / 4)
    assert e2["eficiencia_computo"] == pytest.approx(2.5 / 3)


def test_escalado_debil_x2(tmp_path):
    escribir(tmp_path / "x2.csv", [
        dict(experimento="x2", backend="serial", n=100, procesos=1, hilos=1, recursos=1, media=1.0,
             desviacion=0.0, tiempos="1.0", sobresuscrito=0, **META),
        dict(experimento="x2", backend="openmp", n=400, procesos=1, hilos=4, recursos=4, media=1.25,
             desviacion=0.0, tiempos="1.25", sobresuscrito=0, schedule="static", **META),
    ])
    filas = ar.analizar(tmp_path)
    x2 = next(f for f in filas if f["backend"] == "openmp")
    assert x2["eficiencia_debil"] == pytest.approx(1.0 / 1.25)


def test_x3_ajuste_lineal():
    puntos = [(1e6, 0.5 + 2e-6 * 1e6), (2e6, 0.5 + 2e-6 * 2e6), (4e6, 0.5 + 2e-6 * 4e6)]
    aj = ca.ajuste_lineal(puntos)
    assert aj["pendiente"] == pytest.approx(2e-6)
    assert aj["intercepto"] == pytest.approx(0.5)
    assert aj["r2"] == pytest.approx(1.0)
    assert aj["us_por_escenario"] == pytest.approx(2.0)


def test_sobresuscripcion_y_nota_nucleos_pe(tmp_path):
    escribir(tmp_path / "openmp.csv", [
        dict(backend="openmp", hilos=16, schedule="static", n=1000, media=1.0, desviacion=0.0, **META),
        dict(backend="openmp", hilos=32, schedule="static", n=1000, media=1.0, desviacion=0.0, **META),
    ])
    filas = {f["recursos"]: f for f in ar.analizar(tmp_path)}
    assert filas[32]["sobresuscrito"] == 1
    assert filas[16]["sobresuscrito"] == 0
    assert "E" in filas[16]["nota_nucleos"]


def test_tolera_entradas_faltantes_y_escribe_salidas(tmp_path, capsys):
    bench = tmp_path / "bench"
    bench_sintetico(bench)
    salida = tmp_path / "analisis"
    rutas = ar.main(["--bench", str(bench), "--salida", str(salida)])
    for nombre in ("rendimiento.csv", "rendimiento.md", "rendimiento.tex"):
        assert (salida / nombre).exists()
    assert "AVISO" in capsys.readouterr().err  # hibrido / x1 / x2 / x3 ausentes
    tex = (salida / "rendimiento.tex").read_text(encoding="utf-8")
    assert "\\begin{tabular}" in tex and "\\end{tabular}" in tex
    md = (salida / "rendimiento.md").read_text(encoding="utf-8")
    assert "| backend" in md
    with open(salida / "rendimiento.csv", newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 3
    assert rutas


def test_sin_ninguna_entrada_no_falla(tmp_path):
    rutas = ar.main(["--bench", str(tmp_path / "vacio"), "--salida", str(tmp_path / "out")])
    assert (tmp_path / "out" / "rendimiento.md").exists()
    assert isinstance(rutas, list)
    assert "Sin datos" in (tmp_path / "out" / "rendimiento.md").read_text(encoding="utf-8")
