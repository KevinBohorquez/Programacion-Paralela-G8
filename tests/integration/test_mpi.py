# T21 | Responsable: Ashley | Pruebas V1, V3 y V4 de MPI (E1 estático y E2 dinámico).
#
# V1: k, n e histograma idénticos a pp_serial (y v1_referencia=OK del propio ejecutable con --verificar).
# V3 (conservación, docs/contratos.md): la suma del trabajo por rango (n_local de las líneas [verif])
#     es exactamente N.
# V4 (reproducibilidad): dos corridas iguales dan el mismo resultado.
# Además, E2 termina limpio: cada trabajador recibe su STOP y el programa sale con código 0 antes del
#     tiempo límite (sin cuelgue); los bloques que el maestro asignó son los que procesaron los trabajadores.
#
# Uso (en la imagen pp-g8, tras compilar con -DPP_BUILD_MPI=ON):
#   PP_BIN_DIR=build/src/backends python3 -m pytest -q tests/integration/test_mpi.py
# Sin PP_BIN_DIR las pruebas se omiten.
import csv
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "bench"))
from _comun_mpi import parse_verif  # noqa: E402

CONFIG = RAIZ / "config" / "sintetico.yaml"
N = 10007    # primo: no divisible entre ningún número de procesos probado
LOTE = 100   # E2: 101 bloques, el último incompleto
TIEMPO_LIMITE = 120
PROCESOS = [1, 2, 4]
ESQUEMAS = ["pp_mpi_estatico", "pp_mpi_dinamico"]

BIN = Path(os.environ["PP_BIN_DIR"]) if os.environ.get("PP_BIN_DIR") else None
MPIEXEC = shutil.which("mpirun") or shutil.which("mpiexec")

pytestmark = [
    pytest.mark.skipif(BIN is None, reason="defina PP_BIN_DIR (p. ej. build/src/backends)"),
    pytest.mark.skipif(MPIEXEC is None, reason="no hay mpirun en el PATH"),
]

COMUNES = ["--config", str(CONFIG), "--n", str(N), "--semilla", "777", "--config-id", "3", "--silencioso"]


def entorno():
    env = dict(os.environ)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    return env


def leer(ruta):
    with open(ruta, newline="") as f:
        return next(csv.DictReader(f))


@pytest.fixture(scope="module")
def serial(tmp_path_factory):
    exe = BIN / "serial" / "pp_serial"
    if not exe.exists():
        pytest.skip(f"no existe {exe}")
    salida = tmp_path_factory.mktemp("serial") / "s.csv"
    subprocess.run([str(exe), *COMUNES, "--salida", str(salida)], check=True, capture_output=True, text=True,
                   timeout=TIEMPO_LIMITE)
    return leer(salida)


def correr_mpi(esquema, np_, salida):
    exe = BIN / "mpi" / esquema
    if not exe.exists():
        pytest.skip(f"no existe {exe}; compile con -DPP_BUILD_MPI=ON")
    cmd = [MPIEXEC, "-np", str(np_), "--oversubscribe", str(exe), *COMUNES, "--lote", str(LOTE),
           "--verificar", "--salida", str(salida)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIEMPO_LIMITE, env=entorno())
    except subprocess.TimeoutExpired:
        pytest.fail(f"E2/STOP: {esquema} con {np_} procesos no terminó en {TIEMPO_LIMITE} s (¿falta un STOP?)")
    assert r.returncode == 0, f"{' '.join(cmd)}\n{r.stdout}\n{r.stderr}"
    return leer(salida), parse_verif(r.stdout)


@pytest.mark.parametrize("np_", PROCESOS)
@pytest.mark.parametrize("esquema", ESQUEMAS)
def test_v1_igual_al_secuencial(esquema, np_, serial, tmp_path):
    fila, v = correr_mpi(esquema, np_, tmp_path / "r.csv")
    assert v["estado"] == "OK" and v["v1"] == "OK"
    assert v["procesos"] == np_
    for c in ("n", "k", "p_hat", "wilson_inf", "wilson_sup", "hist512"):
        assert fila[c] == serial[c], c


@pytest.mark.parametrize("np_", PROCESOS)
@pytest.mark.parametrize("esquema", ESQUEMAS)
def test_v3_suma_del_trabajo_por_rango_es_n(esquema, np_, tmp_path):
    _, v = correr_mpi(esquema, np_, tmp_path / "r.csv")
    assert len(v["rangos"]) == np_
    assert sum(r["n_local"] for r in v["rangos"]) == N
    assert v["suma_n"] == N and v["suma_n_rangos"] == N
    if esquema == "pp_mpi_estatico":  # intervalos contiguos que cubren [0, N)
        assert v["rangos"][0]["inicio"] == 0 and v["rangos"][-1]["fin"] == N
        assert all(a["fin"] == b["inicio"] for a, b in zip(v["rangos"], v["rangos"][1:]))


@pytest.mark.parametrize("np_", [2, 4])
def test_e2_termina_con_stop_para_cada_trabajador(np_, tmp_path):
    _, v = correr_mpi("pp_mpi_dinamico", np_, tmp_path / "r.csv")
    maestro, trabajadores = v["rangos"][0], v["rangos"][1:]
    bloques_esperados = -(-N // LOTE)
    assert maestro["n_local"] == 0, "el maestro no simula"
    assert maestro["bloques"] == bloques_esperados
    # cada WORK asignado fue procesado por algún trabajador y todos salieron del bucle (recibieron STOP)
    assert sum(t["bloques"] for t in trabajadores) == bloques_esperados
    assert len(trabajadores) == np_ - 1


@pytest.mark.parametrize("esquema", ESQUEMAS)
def test_v4_reproducible(esquema, tmp_path):
    a, _ = correr_mpi(esquema, 4, tmp_path / "a.csv")
    b, _ = correr_mpi(esquema, 4, tmp_path / "b.csv")
    assert (a["k"], a["n"], a["hist512"]) == (b["k"], b["n"], b["hist512"])
