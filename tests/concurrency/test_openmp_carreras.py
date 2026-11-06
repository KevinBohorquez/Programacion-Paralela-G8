# T17 | Responsable: Lita (borrador preparado junto con T15; revisión: Ashley) | V5: ausencia de carreras en OpenMP.
#
# V5 exige "cero reportes" de ThreadSanitizer + Archer. Archer es el detector de carreras de LLVM que
# entiende la sincronización del runtime LLVM OpenMP (libomp). Con GCC/libgomp ThreadSanitizer NO es
# fiable: marca como carreras las escrituras previas a GOMP_parallel (falsos positivos del runtime no
# instrumentado). Por eso esta prueba compila con clang++ + libomp y exige reportes == 0.
#
# Requisitos: clang++, libomp-dev (Ubuntu: apt-get install clang libomp-dev), cmake.
# Deja el diagnóstico en build/v5_archer.log (el CI lo sube como evidencia).
import os
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CONFIG = RAIZ / "config" / "sintetico.yaml"
DIR_BUILD = RAIZ / "build" / "v5_archer"
LOG = RAIZ / "build" / "v5_archer.log"

CONFIGURACIONES = [(2, "static"), (4, "dynamic:16"), (8, "guided"), (16, "static")]

requiere_clang = pytest.mark.skipif(
    shutil.which("clang++") is None or shutil.which("cmake") is None,
    reason="V5 necesita clang++ con libomp (Archer) y cmake; instale clang y libomp-dev. NO es un 'sin carreras'.",
)


@pytest.fixture(scope="module")
def binario():
    DIR_BUILD.mkdir(parents=True, exist_ok=True)
    cfg = ["cmake", "-S", str(RAIZ), "-B", str(DIR_BUILD), "-DCMAKE_CXX_COMPILER=clang++",
           "-DCMAKE_BUILD_TYPE=RelWithDebInfo", "-DPP_SANITIZE=thread"]
    subprocess.run(cfg, check=True, capture_output=True, text=True)
    subprocess.run(["cmake", "--build", str(DIR_BUILD), "--target", "pp_openmp", "--parallel"],
                   check=True, capture_output=True, text=True)
    return DIR_BUILD / "src" / "backends" / "openmp" / "pp_openmp"


def ruta_de_clang(tipo, nombre):
    """Ruta absoluta que clang conoce para una biblioteca (tipo='file') o programa (tipo='prog'), o None."""
    r = subprocess.run(["clang++", f"-print-{tipo}-name={nombre}"], capture_output=True, text=True).stdout.strip()
    return r if os.path.isabs(r) and os.path.exists(r) else None


def entorno_archer():
    # libomp busca "libarcher.so" por nombre; en algunas distribuciones (Ubuntu 26.04 + LLVM 21) no está en
    # la ruta del cargador y ThreadSanitizer corre SIN Archer, dando falsos positivos en las reducciones.
    tsan = "ignore_noninstrumented_modules=1"
    simbolizador = ruta_de_clang("prog", "llvm-symbolizer")
    if simbolizador:
        tsan += f" external_symbolizer_path={simbolizador}"
    entorno = dict(os.environ, TSAN_OPTIONS=tsan, ARCHER_OPTIONS="verbose=1")
    archer = ruta_de_clang("file", "libarcher.so")
    if archer:
        entorno["OMP_TOOL_LIBRARIES"] = archer
    return entorno, archer


@requiere_clang
def test_v5_sin_carreras_con_archer(binario):
    entorno, archer = entorno_archer()
    LOG.parent.mkdir(parents=True, exist_ok=True)
    reportes_total = 0
    with open(LOG, "w") as log:
        log.write(f"# V5 ThreadSanitizer + Archer | {subprocess.run(['clang++', '--version'], capture_output=True, text=True).stdout.splitlines()[0]}\n")
        log.write(f"# OMP_TOOL_LIBRARIES={archer or '(sin definir; libomp lo busca por nombre)'}\n")
        for hilos, schedule in CONFIGURACIONES:
            r = subprocess.run([str(binario), "--config", str(CONFIG), "--n", "4000", "--hilos", str(hilos),
                                "--schedule", schedule, "--silencioso"],
                               capture_output=True, text=True, env=entorno, timeout=600)
            archer_activo = "Archer detected OpenMP application with TSan" in r.stdout + r.stderr  # Archer usa stdout
            reportes = r.stderr.count("WARNING: ThreadSanitizer")
            reportes_total += reportes
            log.write(f"hilos={hilos} schedule={schedule} archer={'activo' if archer_activo else 'NO cargado'} "
                      f"rc={r.returncode} reportes={reportes}\n")
            if reportes:
                log.write(r.stderr + "\n")
            assert archer_activo, f"Archer no se cargó: sin él ThreadSanitizer no entiende las barreras de OpenMP; ver {LOG}"
            assert r.returncode == 0, r.stderr[-2000:]
    assert reportes_total == 0, f"ThreadSanitizer/Archer reportó {reportes_total} carrera(s); ver {LOG}"


@requiere_clang
def test_v5_control_negativo_detecta_una_carrera_deliberada(tmp_path):
    """Si la herramienta no detectara una carrera conocida, un 'cero reportes' no valdría nada."""
    fuente = tmp_path / "carrera.cpp"
    fuente.write_text("#include <cstdio>\nint main(){ long c=0;\n#pragma omp parallel for\n"
                      " for(int i=0;i<100000;++i) c+=i;\n std::printf(\"%ld\\n\",c); }\n")
    exe = tmp_path / "carrera"
    subprocess.run(["clang++", "-fopenmp", "-fsanitize=thread", "-g", "-O1", str(fuente), "-o", str(exe)],
                   check=True, capture_output=True, text=True)
    entorno, _ = entorno_archer()  # el mismo entorno que V5: Archer no debe ocultar una carrera real
    r = subprocess.run([str(exe)], capture_output=True, text=True, timeout=120, env=dict(entorno, OMP_NUM_THREADS="4"))
    assert "WARNING: ThreadSanitizer: data race" in r.stderr
