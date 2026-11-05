# Sala de control | Líneas de avance (--progreso, docs/contrato-sala-control.md §1).
#
# Comprueba que --progreso no cambia k ni hist512 (serial, OpenMP y MPI E1/E2/híbrido), que las líneas
# [prog] aparecen solo con la opción, que su formato es el del contrato y que hay a lo sumo una línea
# por cada 1 % de total por emisor, más la línea final con hecho=total.
#
# Uso (tras compilar):   pytest -q tests/integration/test_progreso.py
# Variables opcionales:  PP_BIN_DIR=<carpeta src/backends del build>; PP_MPIEXEC=<mpiexec>;
#                        PP_MPI_EXTRA="--oversubscribe ..." (argumentos extra de mpiexec)
import csv
import os
import re
import shlex
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get("PP_BIN_DIR", RAIZ / "build" / "src" / "backends"))
CONFIG = RAIZ / "config" / "sintetico.yaml"
MPIEXEC = os.environ.get("PP_MPIEXEC", "")
MPI_EXTRA = shlex.split(os.environ.get("PP_MPI_EXTRA", ""))

N = 20011  # primo: no divisible entre el número de procesos ni de hilos
NP = 3

RE_AVANCE = re.compile(r"^\[prog\] (?:rango=(\d+) )?hecho=(\d+) total=(\d+)$")
RE_BLOQUE = re.compile(r"^\[prog\] rango=(\d+) bloque=(\d+),(\d+)$")

CASOS = {
    "serial": (BIN / "serial" / "pp_serial", False, []),
    "openmp": (BIN / "openmp" / "pp_openmp", False, ["--hilos", "4", "--schedule", "dynamic"]),
    "mpi_estatico": (BIN / "mpi" / "pp_mpi_estatico", True, []),
    "mpi_dinamico": (BIN / "mpi" / "pp_mpi_dinamico", True, ["--lote", "1000"]),
    "hibrido": (BIN / "hybrid" / "pp_hibrido", True, ["--hilos", "2", "--schedule", "static"]),
}


def ejecutar(nombre, tmp_path, progreso):
    exe, es_mpi, extra = CASOS[nombre]
    if not exe.exists():
        pytest.skip(f"no se encontró {exe}")
    if es_mpi and not MPIEXEC:
        pytest.skip("PP_MPIEXEC no definido")
    salida = tmp_path / f"{nombre}_{int(progreso)}.csv"
    cmd = [str(exe), "--config", str(CONFIG), "--n", str(N), "--dias", "30", "--silencioso",
           "--salida", str(salida), *extra]
    if progreso:
        cmd.append("--progreso")
    if es_mpi:
        cmd = [MPIEXEC, "-np", str(NP), *MPI_EXTRA, *cmd]
    r = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=300)
    with open(salida, newline="") as f:
        fila = next(csv.DictReader(f))
    return fila, r.stdout, r.stderr


def lineas_prog(texto):
    return [l for l in texto.splitlines() if l.startswith("[prog]")]


@pytest.mark.parametrize("nombre", list(CASOS))
def test_resultado_identico_y_lineas_solo_con_la_opcion(nombre, tmp_path):
    base, out0, err0 = ejecutar(nombre, tmp_path, False)
    con, out1, err1 = ejecutar(nombre, tmp_path, True)
    assert (base["k"], base["n"], base["hist512"]) == (con["k"], con["n"], con["hist512"])
    assert not lineas_prog(err0) and not lineas_prog(out0), "sin --progreso no debe haber líneas [prog]"
    assert not lineas_prog(out1), "las líneas [prog] van a stderr"
    lineas = lineas_prog(err1)
    assert lineas, "con --progreso debe haber líneas [prog] en stderr"

    if nombre == "mpi_dinamico":
        bloques = []
        for l in lineas:
            m = RE_BLOQUE.match(l)
            assert m, f"línea con formato inválido: {l!r}"
            assert int(m.group(1)) != 0, "el maestro no se asigna bloques"
            bloques.append((int(m.group(2)), int(m.group(3))))
        bloques.sort()
        assert bloques[0][0] == 0 and bloques[-1][1] == N
        assert all(a[1] == b[0] for a, b in zip(bloques, bloques[1:])), "los bloques deben cubrir [0, N)"
        return

    por_emisor = {}
    for l in lineas:
        m = RE_AVANCE.match(l)
        assert m, f"línea con formato inválido: {l!r}"
        if nombre in ("serial", "openmp"):
            assert m.group(1) is None, "serial y OpenMP no llevan rango="
        else:
            assert m.group(1) is not None, "E1 e híbrido llevan rango="
        por_emisor.setdefault(m.group(1), []).append((int(m.group(2)), int(m.group(3))))

    assert len(por_emisor) == (NP if CASOS[nombre][1] else 1)
    suma_total = 0
    for avances in por_emisor.values():
        total = avances[0][1]
        assert all(t == total for _, t in avances)
        hechos = [h for h, _ in avances]
        assert hechos == sorted(hechos) and len(set(hechos)) == len(hechos)
        assert hechos[-1] == total, "la última línea de cada emisor es hecho=total"
        assert len(avances) <= 101, "a lo sumo una línea por cada 1 % (más la final)"
        suma_total += total
    assert suma_total == N
