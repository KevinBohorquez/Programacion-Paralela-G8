"""Comprueba el agregado y las figuras de graficar_openmp_ashley.py (T18) con un CSV sintético pequeño."""

import csv
import importlib.util
import statistics
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "bench" / "graficar_openmp_ashley.py"

CAMPOS = ["backend", "hilos", "hilos_efectivos", "schedule", "n", "semilla", "config_id", "afinidad",
          "nucleos_fisicos", "nucleos_logicos", "sobresuscrito", "excede_logicos", "t_calentamiento",
          "t1", "t2", "t3", "t4", "t5", "media", "desviacion", "k", "equivalente_serial", "cpu", "ram_gb",
          "compilador", "tipo_build", "commit", "fecha", "so"]

# Tiempos por punto: serial y OpenMP static con 2/4/8/16 hilos (8 núcleos físicos: 16 está sobresuscrito).
SERIAL = [10.0, 10.0, 10.0, 10.0, 10.0]
OPENMP = {2: [4.0, 5.0, 6.0, 5.0, 5.0], 4: [2.5] * 5, 8: [1.25] * 5, 16: [1.0] * 5}


def cargar_modulo():
    spec = importlib.util.spec_from_file_location("graficar_openmp_ashley", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def fila(backend, hilos, schedule, ts, equivalente="1"):
    f = dict(backend=backend, hilos=hilos, hilos_efectivos=hilos, schedule=schedule, n=1000, semilla=20261015,
             config_id=0, afinidad="OMP_PROC_BIND=close;OMP_PLACES=cores", nucleos_fisicos=8, nucleos_logicos=8,
             sobresuscrito=int(hilos > 8), excede_logicos=int(hilos > 8), t_calentamiento=ts[0],
             media=statistics.mean(ts), desviacion=statistics.stdev(ts), k=42, equivalente_serial=equivalente,
             cpu="CPU de prueba", ram_gb=8, compilador="g++ 13.3", tipo_build="Release", commit="prueba",
             fecha="2026-10-26T00:00:00+00:00", so="Linux")
    f.update({f"t{i}": t for i, t in enumerate(ts, 1)})
    return f


def filas_sinteticas():
    return [fila("serial", 1, "-", SERIAL)] + [fila("openmp", h, "static", ts) for h, ts in OPENMP.items()]


def escribir(ruta, filas):
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(filas)


def como_texto(filas):
    """Simula csv.DictReader: el script recibe todos los valores como cadenas."""
    return [{k: str(v) for k, v in f.items()} for f in filas]


def test_agregar_calcula_speedup_eficiencia_y_sobresuscripcion():
    modulo = cargar_modulo()
    agr, cab = modulo.agregar(como_texto(filas_sinteticas()), None)

    assert [r["hilos"] for r in agr] == [2, 4, 8, 16]
    assert cab["backend"] == "serial"
    por_hilos = {r["hilos"]: r for r in agr}
    for p, ts in OPENMP.items():
        r = por_hilos[p]
        assert r["t1_media"] == pytest.approx(10.0)
        assert r["tp_media"] == pytest.approx(statistics.mean(ts))
        assert r["speedup"] == pytest.approx(10.0 / statistics.mean(ts))
        assert r["eficiencia"] == pytest.approx(10.0 / statistics.mean(ts) / p)
        assert r["muestras"] == 5
        assert r["fuente_t1"] == "fila serial de T16"
    assert por_hilos[2]["speedup"] == pytest.approx(2.0)
    assert por_hilos[2]["eficiencia"] == pytest.approx(1.0)
    assert por_hilos[2]["tp_desv"] == pytest.approx(statistics.stdev(OPENMP[2]))
    assert por_hilos[16]["speedup"] == pytest.approx(10.0)
    assert por_hilos[16]["eficiencia"] == pytest.approx(0.625)
    assert [r["sobresuscrito"] for r in agr] == [0, 0, 0, 1]


def test_agregar_usa_t1_externo_si_se_pasa():
    modulo = cargar_modulo()
    agr, _ = modulo.agregar(como_texto(filas_sinteticas()), (20.0, 0.5))
    assert agr[0]["t1_media"] == pytest.approx(20.0)
    assert agr[0]["speedup"] == pytest.approx(4.0)
    assert agr[0]["fuente_t1"] == "T14 (--t1-csv)"


def test_agregar_rechaza_v1_fallida():
    modulo = cargar_modulo()
    filas = filas_sinteticas()
    filas[2]["equivalente_serial"] = "0"
    with pytest.raises(SystemExit, match="V1 fallida"):
        modulo.agregar(como_texto(filas), None)


def test_agregar_rechaza_carga_distinta():
    modulo = cargar_modulo()
    filas = filas_sinteticas()
    filas[1]["semilla"] = 99
    with pytest.raises(SystemExit, match="semilla"):
        modulo.agregar(como_texto(filas), None)


def test_cli_escribe_agregado_y_figuras(tmp_path):
    entrada = tmp_path / "openmp.csv"
    agregado = tmp_path / "bench" / "openmp_agregado.csv"
    figuras = tmp_path / "figures"
    escribir(entrada, filas_sinteticas())

    run = subprocess.run([sys.executable, str(SCRIPT), "--entrada", str(entrada), "--agregado", str(agregado),
                          "--figuras", str(figuras), "--svg"], capture_output=True, text=True, check=False)

    assert run.returncode == 0, run.stderr
    with agregado.open(encoding="utf-8", newline="") as f:
        filas = list(csv.DictReader(f))
    assert [f["hilos"] for f in filas] == ["2", "4", "8", "16"]
    assert float(filas[0]["speedup"]) == pytest.approx(2.0)
    assert float(filas[3]["eficiencia"]) == pytest.approx(0.625)
    assert filas[3]["sobresuscrito"] == "1"
    for nombre in ("openmp_tiempo", "openmp_speedup", "openmp_eficiencia"):
        for ext in ("png", "svg"):
            ruta = figuras / f"{nombre}.{ext}"
            assert ruta.is_file() and ruta.stat().st_size > 0, ruta


def test_cli_sin_entrada_termina_con_error(tmp_path):
    run = subprocess.run([sys.executable, str(SCRIPT), "--entrada", str(tmp_path / "no_existe.csv"),
                          "--agregado", str(tmp_path / "a.csv"), "--figuras", str(tmp_path / "f")],
                         capture_output=True, text=True, check=False)
    assert run.returncode != 0
    assert "No existe" in run.stderr
    assert not (tmp_path / "f").exists()
