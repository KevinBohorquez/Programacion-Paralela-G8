# T40/T41 | Responsable: Lita | Lectura de la salida de pp_cuda y de E2 en los scripts de medición CUDA.
# No necesitan GPU: comprueban que medir_cuda.py y medir_cpu_gpu.py interpretan bien las líneas
# [cuda] y [verif] que escriben los ejecutables (formato de src/backends/cuda/main.cpp y comun.cpp).
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "bench"))


def _cargar(nombre):
    spec = importlib.util.spec_from_file_location(nombre, RAIZ / "scripts" / "bench" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


medir_cuda = _cargar("medir_cuda")
medir_cpu_gpu = _cargar("medir_cpu_gpu")

SALIDA_CUDA = """backend=cuda hilos=1 semilla=20261015 config_id=0
n=1000000 k=106235 p_hat=0.106235 wilson=[0.1056, 0.1068]
bloques=16 hilos_por_bloque=512 lanzamientos=2 gpu=NVIDIA GeForce RTX 4060;cc=8.9;sm=24;cuda_rt=13.3;driver=13.5
[cuda] sm=24 sm_usados=16 registros_por_hilo=94 bloques_por_sm_max=1 bloques_por_sm=1 olas=1 ocupacion_sm=0.333333 ocupacion_gpu=0.222222
[cuda] sm_observados=16 max_bloques_por_sm=1 media_bloques_por_sm=1 ocupacion_observada=0.333333 ocupacion_gpu_observada=0.222222
"""

SALIDA_E2 = """[verif] backend=mpi_dinamico_gpu procesos=4 n_solicitado=300007 nivel_hilos_mpi=MPI_THREAD_FUNNELED nucleo=pp_core
[verif] rango=0 bloques=5 n_local=0
[verif] rango=1 bloques=1 n_local=62500
[verif] rango=2 bloques=1 n_local=62500
[verif] rango=3 bloques=3 n_local=175007
[verif] suma_n=300007 suma_n_rangos=300007 suma_hist=300007 k=31867 estado=OK
[verif] v1_referencia=OK k_ref=31867
"""


def test_ocupacion_lee_teorica_y_observada():
    occ = medir_cuda.ocupacion(SALIDA_CUDA)
    assert set(occ) == set(medir_cuda.CAMPOS_OCUPACION)
    assert occ["sm"] == "24" and occ["sm_usados"] == "16" and occ["sm_observados"] == "16"
    assert occ["registros_por_hilo"] == "94" and occ["ocupacion_observada"] == "0.333333"


def test_ocupacion_vacia_sin_lineas_cuda():
    assert all(v == "" for v in medir_cuda.ocupacion("n=10 k=1\n").values())


def test_rangos_de_e2_y_estado():
    por_rango, estado = medir_cpu_gpu.rangos(SALIDA_E2)
    assert estado == "OK"
    assert por_rango == {0: (5, 0), 1: (1, 62500), 2: (1, 62500), 3: (3, 175007)}
    # el maestro no simula y la suma de los trabajadores es N
    assert sum(n for r, (_, n) in por_rango.items() if r != 0) == 300007


def test_rangos_sin_verif():
    assert medir_cpu_gpu.rangos("nada") == ({}, "")
