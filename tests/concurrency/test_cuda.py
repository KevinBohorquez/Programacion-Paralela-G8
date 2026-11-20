# T39 | Responsable: Lita | V2 a nivel de ejecutables: pp_cuda frente a pp_serial (docs/decision-cuda.md).
#
# Corre pp_cuda y pp_serial con las mismas opciones y compara las filas del CSV de resultados:
# n, k e hist512 iguales (V2 exige |dk|/k <= 1e-6; con el núcleo compartido sale exacto), hilos = 1,
# grilla en bloques/hilos_por_bloque (vacías en serial) y datos de la GPU en `hardware`. Además, que
# --progreso no cambie el resultado y que los argumentos inválidos terminen con código 2.
#
# La igualdad exacta de hist512 es empírica, no garantizada: log/cos/pow de la GPU pueden diferir de
# glibc en la última cifra (≈ 15 % de los amax en results/validacion/t38_v2_cuda.txt), y un amax junto
# al borde de una clase la rompería. El criterio formal es la tolerancia de V2 (include/nucleo_hd.hpp).
# Si solo falla hist512 con k dentro de 1e-6, es una diferencia de redondeo, no un error del kernel.
#
# Necesita una GPU NVIDIA y pp_cuda compilado (-DPP_BUILD_CUDA=ON, scripts/cuda/compilar_wsl.sh).
# PP_CUDA_BIN_DIR apunta a <build>/src/backends (por defecto build/cuda/src/backends). Sin GPU o sin
# pp_cuda se omite: en el CI de GitHub no hay GPU. Corre con pytest o directamente con python3
# (WSL Ubuntu-24.04 no tiene pytest; CTest la lanza así con la etiqueta «cuda»).
import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import pytest
except ImportError:  # sin pytest: el bloque __main__ ejecuta las pruebas
    pytest = None

RAIZ = Path(__file__).resolve().parents[2]
BIN = Path(os.environ.get("PP_CUDA_BIN_DIR", RAIZ / "build" / "cuda" / "src" / "backends"))
CUDA = BIN / "cuda" / "pp_cuda"
SERIAL = BIN / "serial" / "pp_serial"

# (configuración, opciones extra): sin H5, con H5 calibrado, con kappa forzado y con grillas distintas.
CASOS = [
    ("config/sintetico.yaml", ["--n", "300000"]),
    ("config/sintetico.yaml", ["--n", "300000", "--kappa", "2", "--config-id", "5"]),
    ("config/tumbes_eltigre_normal.yaml", ["--n", "500000"]),
    ("config/piura_bernal_el_nino.yaml", ["--n", "200000", "--capacidad", "15", "--umbral", "30"]),
]
GRILLAS = [[], ["--bloques", "2", "--hilos-por-bloque", "128"], ["--bloques", "16", "--hilos-por-bloque", "512"]]


def _hay_gpu():
    if not CUDA.exists() or not SERIAL.exists():
        return False, f"falta pp_cuda o pp_serial en {BIN}"
    if shutil.which("nvidia-smi") is None and not Path("/usr/lib/wsl/lib/nvidia-smi").exists():
        return False, "no hay GPU NVIDIA (nvidia-smi)"
    return True, ""


def _correr(binario, config, extra, salida):
    cmd = [str(binario), "--config", str(RAIZ / config), *extra, "--salida", str(salida), "--silencioso"]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, f"{' '.join(cmd)} -> {r.returncode}: {r.stderr}"
    with open(salida, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))[-1]


def test_cuda_igual_a_serial():
    with tempfile.TemporaryDirectory() as d:
        for i, (config, extra) in enumerate(CASOS):
            ref = _correr(SERIAL, config, extra, Path(d) / f"s{i}.csv")
            assert ref["bloques"] == "" and ref["hilos_por_bloque"] == ""
            for j, grilla in enumerate(GRILLAS):
                fila = _correr(CUDA, config, extra + grilla, Path(d) / f"c{i}_{j}.csv")
                k_ref, k = int(ref["k"]), int(fila["k"])
                assert fila["backend"] == "cuda" and fila["n"] == ref["n"]
                assert abs(k - k_ref) / max(k_ref, 1) <= 1e-6, f"{config} {grilla}: k={k} frente a {k_ref}"
                assert fila["hist512"] == ref["hist512"], f"{config} {grilla}: hist512 distinto"
                assert fila["kappa"] == ref["kappa"] and fila["hilos"] == "1"
                assert int(fila["bloques"]) > 0 and int(fila["hilos_por_bloque"]) % 32 == 0
                assert ";gpu=" in fila["hardware"] and ";cc=" in fila["hardware"]
                if grilla:
                    assert [fila["bloques"], fila["hilos_por_bloque"]] == [grilla[1], grilla[3]]
                print(f"[V2-exe] {config} {' '.join(extra + grilla)} k={k} hist512=igual OK")


def test_progreso_no_cambia_el_resultado():
    with tempfile.TemporaryDirectory() as d:
        a = _correr(CUDA, "config/sintetico.yaml", ["--n", "1500000"], Path(d) / "a.csv")
        b = _correr(CUDA, "config/sintetico.yaml", ["--n", "1500000", "--progreso"], Path(d) / "b.csv")
        assert (a["k"], a["hist512"]) == (b["k"], b["hist512"])


def test_argumentos_invalidos():
    for extra in (["--hilos-por-bloque", "100"], ["--hilos-por-bloque", "2048"], ["--kappa", "0"]):
        r = subprocess.run([str(CUDA), "--config", str(RAIZ / "config/sintetico.yaml"), "--n", "10", *extra],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 2, f"{extra}: código {r.returncode}"
    # 1024 hilos por bloque es válido para la configuración, pero el kernel usa demasiados registros por
    # hilo para lanzarse así en CC 8.9: debe terminar con código 2 y un mensaje claro, no con un fallo CUDA.
    r = subprocess.run([str(CUDA), "--config", str(RAIZ / "config/sintetico.yaml"), "--n", "10",
                        "--hilos-por-bloque", "1024"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 or (r.returncode == 2 and "supera el máximo del kernel" in r.stderr), r.stderr


if pytest is not None:
    _ok, _motivo = _hay_gpu()
    pytestmark = pytest.mark.skipif(not _ok, reason=f"V2 de CUDA omitida: {_motivo}")


if __name__ == "__main__":
    ok, motivo = _hay_gpu()
    if not ok:
        print(f"omitida: {motivo}")
        sys.exit(0)
    fallos = 0
    for nombre, prueba in [(n, f) for n, f in dict(globals()).items() if n.startswith("test_") and callable(f)]:
        try:
            prueba()
            print(f"{nombre}: OK")
        except AssertionError as e:
            fallos += 1
            print(f"{nombre}: FALLA: {e}")
    sys.exit(1 if fallos else 0)
