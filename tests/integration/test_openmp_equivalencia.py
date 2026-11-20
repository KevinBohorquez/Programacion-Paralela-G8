# T17 | Responsable: Lita (borrador preparado junto con T15; revisión: Ashley) | V1 secuencial vs OpenMP.
#
# V1: k, n e histograma idénticos entre el secuencial y OpenMP para cualquier número de hilos y schedule.
# Incluye comprobaciones mínimas de V3 (se simulan exactamente N escenarios) y V4 (dos corridas iguales).
#
# Uso (tras compilar):   pytest -q tests/integration/test_openmp_equivalencia.py
# Variable opcional:     PP_BIN_DIR=<carpeta con serial/pp_serial y openmp/pp_openmp>  (por defecto build/src/backends)
import csv
import os
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get("PP_BIN_DIR", RAIZ / "build" / "src" / "backends"))
SERIAL = BIN / "serial" / "pp_serial"
OPENMP = BIN / "openmp" / "pp_openmp"
CONFIG = RAIZ / "config" / "sintetico.yaml"

N = 5003  # primo: no divisible entre 2, 4, 8 ni 16
HILOS = [1, 2, 4, 8]
SCHEDULES = ["static", "dynamic", "dynamic:7", "guided"]

pytestmark = pytest.mark.skipif(
    not (SERIAL.exists() and OPENMP.exists()),
    reason=f"compile primero (cmake --build build); no se encontró {SERIAL} u {OPENMP}",
)


def ejecutar(exe, tmp_path, nombre, *extra, config_id=3, semilla=777, n=N):
    salida = tmp_path / f"{nombre}.csv"
    cmd = [str(exe), "--config", str(CONFIG), "--n", str(n), "--semilla", str(semilla),
           "--config-id", str(config_id), "--silencioso", "--salida", str(salida), *map(str, extra)]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    with open(salida, newline="") as f:
        return next(csv.DictReader(f))


CLAVES_RESULTADO = ("n", "k", "p_hat", "wilson_inf", "wilson_sup", "hist512")


def resultado(fila):
    return {c: fila[c] for c in CLAVES_RESULTADO}


@pytest.fixture(scope="module")
def referencia(tmp_path_factory):
    return ejecutar(SERIAL, tmp_path_factory.mktemp("serial"), "serial")


def test_referencia_valida(referencia):
    assert int(referencia["n"]) == N
    hist = [int(x) for x in referencia["hist512"].split(";")]
    assert len(hist) == 512 and sum(hist) == N
    assert 0 < int(referencia["k"]) < N, "la configuración de prueba debe tener inundaciones y no inundaciones"


@pytest.mark.parametrize("hilos", HILOS)
@pytest.mark.parametrize("schedule", SCHEDULES)
def test_v1_openmp_igual_a_serial(referencia, tmp_path, hilos, schedule):
    fila = ejecutar(OPENMP, tmp_path, "omp", "--hilos", hilos, "--schedule", schedule)
    assert resultado(fila) == resultado(referencia)  # bit a bit (el CSV guarda 17 cifras)
    assert int(fila["hilos"]) == hilos


@pytest.mark.parametrize("config_id", [0, 1, 12999])
def test_v1_indice_global_estable(tmp_path, config_id):
    """El índice global c*N+j (no el hilo) decide el resultado, también con config_id grandes."""
    ref = ejecutar(SERIAL, tmp_path, "s", config_id=config_id)
    omp = ejecutar(OPENMP, tmp_path, "o", "--hilos", 4, "--schedule", "dynamic:5", config_id=config_id)
    assert resultado(omp) == resultado(ref)


def test_v3_conservacion_n(tmp_path):
    for n in (1, 2, 7, 1000):
        fila = ejecutar(OPENMP, tmp_path, f"n{n}", "--hilos", 8, n=n)
        assert int(fila["n"]) == n
        assert sum(int(x) for x in fila["hist512"].split(";")) == n


def test_v4_reproducibilidad(tmp_path):
    a = ejecutar(OPENMP, tmp_path, "a", "--hilos", 4, "--schedule", "dynamic:3")
    b = ejecutar(OPENMP, tmp_path, "b", "--hilos", 4, "--schedule", "dynamic:3")
    assert resultado(a) == resultado(b)


def test_semilla_distinta_cambia_resultado(tmp_path):
    a = ejecutar(OPENMP, tmp_path, "a", "--hilos", 2, semilla=1)
    b = ejecutar(OPENMP, tmp_path, "b", "--hilos", 2, semilla=2)
    assert resultado(a) != resultado(b)


def test_entrada_invalida_falla_con_codigo_distinto_de_cero(tmp_path):
    r = subprocess.run([str(OPENMP), "--config", str(CONFIG), "--n", "0"], capture_output=True, text=True)
    assert r.returncode != 0 and "error" in r.stderr
    r = subprocess.run([str(OPENMP), "--config", str(CONFIG), "--schedule", "inventado"], capture_output=True, text=True)
    assert r.returncode != 0


@pytest.mark.parametrize("opcion,valor", [
    ("--bloques", "4294967296"),            # 2^32: truncado a int sería 0 (grilla automática)
    ("--bloques", "2147483648"),            # INT_MAX + 1
    ("--hilos-por-bloque", "4294967328"),   # 2^32 + 32: truncado a int sería 32, un valor válido
    ("--hilos", "4294967300"),
])
def test_entero_fuera_de_rango_de_int_se_rechaza(opcion, valor):
    """La lectura de opciones es común a todos los ejecutables: un entero que no cabe en int se rechaza
    con código 2 en vez de truncarse en silencio (bloques e hilos por bloque de pp_cuda incluidos)."""
    r = subprocess.run([str(SERIAL), "--config", str(CONFIG), "--n", "10", opcion, valor],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 2, f"{opcion} {valor}: código {r.returncode}"
    assert "fuera de rango" in r.stderr and opcion[2:].replace("-", "_") in r.stderr, r.stderr
