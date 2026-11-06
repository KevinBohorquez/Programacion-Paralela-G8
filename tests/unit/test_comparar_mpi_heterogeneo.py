"""Pruebas de T32 (scripts/bench/comparar_mpi_heterogeneo.py): partes puras, sin mpirun.

Uso:   python3 -m pytest -v tests/unit/test_comparar_mpi_heterogeneo.py
"""
import importlib.util
import sys
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[2] / "scripts" / "bench"


@pytest.fixture(scope="module")
def cmh():
    sys.path.insert(0, str(BENCH))
    spec = importlib.util.spec_from_file_location("comparar_mpi_heterogeneo", BENCH / "comparar_mpi_heterogeneo.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


HOSTS = [("nodo1", 2), ("nodo2", 2)]


def fila(backend, media, trabajo, procesos=4, n=400, eq=1, sd=0.1, desb=1.0):
    return dict(backend=backend, procesos=procesos, n=n, media=media, desviacion=sd, equivalente=eq,
                trabajo_rangos=trabajo, desbalance=desb)


def test_trabajo_por_nodo_texto(cmh):
    assert cmh.trabajo_nodos_texto(HOSTS, 4, "100;100;100;100") == "nodo1=200;nodo2=200"
    assert cmh.trabajo_nodos_texto(HOSTS, 4, "0;150;150;100") == "nodo1=150;nodo2=250"
    assert cmh.trabajo_nodos_texto([], 2, "5;5") == "local=10"
    assert cmh.trabajo_nodos_texto(HOSTS, 4, "") == ""


def test_argumentos_del_ejecutor(cmh):
    args = cmh.argumentos_ejecutor(cmh.construir_parser().parse_args(
        ["--n", "1e6", "--procesos", "4,8", "--hosts", "nodo1:4,nodo2:4", "--red-tcp", "eth0", "--lote", "1000"]))
    assert args[args.index("--experimento") + 1] == "x3"
    assert args[args.index("--backend") + 1] == "mpi_estatico,mpi_dinamico"
    assert args[args.index("--recursos") + 1] == "4,8"
    assert args[args.index("--cargas") + 1] == "1000000"
    assert args[args.index("--hosts") + 1] == "nodo1:4,nodo2:4"
    assert args[args.index("--lote") + 1] == "1000"


def test_resumir_empareja_e1_y_e2(cmh):
    filas = [fila("mpi_estatico", 2.0, "100;100;100;100", desb=1.0),
             fila("mpi_dinamico", 1.5, "0;150;150;100", desb=1.125),
             fila("mpi_estatico", 1.0, "", procesos=8)]
    r = cmh.resumir(filas, HOSTS)
    assert len(r) == 2
    p4 = r[0]
    assert (p4["procesos"], p4["n"]) == (4, 400)
    assert p4["t_e1"] == 2.0 and p4["t_e2"] == 1.5
    assert p4["razon_e2_e1"] == pytest.approx(0.75)
    assert p4["mas_rapido"] == "E2"
    assert p4["nodos_e2"] == "nodo1=150;nodo2=250"
    assert p4["equivalentes"] == 1
    p8 = r[1]
    assert p8["t_e2"] == "" and p8["razon_e2_e1"] == "" and p8["mas_rapido"] == ""


def test_resumir_marca_no_equivalente(cmh):
    filas = [fila("mpi_estatico", 2.0, "1;1;1;1"), fila("mpi_dinamico", 2.0, "0;2;1;1", eq=0)]
    assert cmh.resumir(filas, HOSTS)[0]["equivalentes"] == 0


def test_tabla_markdown(cmh):
    r = cmh.resumir([fila("mpi_estatico", 2.0, "1;1;1;1"), fila("mpi_dinamico", 1.0, "0;2;1;1")], HOSTS)
    tabla = cmh.tabla_markdown(r)
    lineas = tabla.splitlines()
    assert lineas[0].startswith("| procesos | n |") and set(lineas[1]) <= set("|- ")
    assert "E2" in lineas[2] and "0.500" in lineas[2]
