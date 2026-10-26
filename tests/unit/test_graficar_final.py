"""T45: figuras finales de graficar-final.py con CSV sintéticos mínimos."""

import csv
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "scripts" / "bench"
sys.path.insert(0, str(BENCH))

spec = importlib.util.spec_from_file_location("graficar_final", BENCH / "graficar-final.py")
gf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gf)

META = dict(cpu="CPU de prueba", nucleos_fisicos=8, nucleos_logicos=8, commit="abc123")


def escribir(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    campos = []
    for f in filas:
        campos += [c for c in f if c not in campos]
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos, restval="")
        w.writeheader()
        w.writerows(filas)


def preparar(tmp_path):
    bench = tmp_path / "bench"
    escribir(bench / "secuencial_t1.csv", [dict(backend="serial", n=1000, media=8.0, desviacion=0.0, **META)])
    escribir(bench / "openmp.csv", [
        dict(backend="openmp", hilos=h, schedule="static", n=1000, media=8.0 / (0.9 * h), desviacion=0.01, **META)
        for h in (2, 4, 8)])
    escribir(bench / "mpi_resumen.csv", [
        dict(esquema=e, procesos=p, procesos_computo=(p - 1 if e == "mpi_dinamico" else p), n=1000,
             media=8.0 / (0.8 * p), desviacion=0.0, t_serial=8.0, **META)
        for e in ("mpi_estatico", "mpi_dinamico") for p in (2, 4)])
    escribir(bench / "hibrido_resumen.csv", [
        dict(nucleos_totales=4, procesos=p, hilos=4 // p, factorizacion=f"{p}x{4 // p}", n=1000,
             media=2.5 + 0.1 * p, desviacion=0.0, t_serial=8.0, **META) for p in (1, 2, 4)])
    escribir(bench / "x2.csv", [
        dict(experimento="x2", backend="openmp", n=100 * r, procesos=1, hilos=r, recursos=r,
             media=1.0 + 0.05 * r, desviacion=0.0, schedule="static", **META) for r in (1, 2, 4)])
    escribir(bench / "x3.csv", [
        dict(experimento="x3", backend="openmp", n=n, procesos=1, hilos=8, recursos=8,
             media=0.1 + 1e-6 * n, desviacion=0.0, schedule="static", **META) for n in (1000, 2000, 4000)])
    tablas = tmp_path / "cientifico" / "tablas"
    escribir(tablas / "riesgo.csv", [
        dict(estacion="lima", regimen=r, capacidad=c, umbral=50, n=1000, k=10, p_hat=0.01 * c,
             wilson_inf=0.008 * c, wilson_sup=0.012 * c) for r in ("normal", "el_nino") for c in (4, 6, 8)])
    escribir(tablas / "sensibilidad.csv", [
        dict(estacion="lima", regimen=r, capacidad=c, umbral=u, n=1000, k=10, p_hat=0.01 * c / u * 50,
             wilson_inf=0.0, wilson_sup=0.1) for r in ("normal", "el_nino") for c in (4, 6) for u in (30, 50, 80)])
    return bench, tmp_path / "cientifico", tmp_path / "figuras"


def test_genera_todas_las_figuras_png_y_svg(tmp_path):
    bench, cient, figs = preparar(tmp_path)
    r = gf.main(["--bench", str(bench), "--cientifico", str(cient), "--figuras", str(figs)])
    esperadas = ["final_speedup", "final_eficiencia", "final_karp_flatt", "final_x2_debil",
                 "final_x3_tiempo", "final_hibrido_factorizacion", "final_e1_e2",
                 "final_riesgo_lima", "final_sensibilidad"]
    for nombre in esperadas:
        assert (figs / f"{nombre}.png").stat().st_size > 0, nombre
        assert (figs / f"{nombre}.svg").exists(), nombre
    assert set(esperadas) <= set(r["escritas"])


def test_pie_lleva_commit_y_hardware(tmp_path):
    bench, cient, figs = preparar(tmp_path)
    gf.main(["--bench", str(bench), "--cientifico", str(cient), "--figuras", str(figs)])
    svg = (figs / "final_speedup.svg").read_text(encoding="utf-8")
    assert "abc123" in svg and "CPU de prueba" in svg


def test_reutiliza_figuras_cientificas_existentes(tmp_path):
    bench, cient, figs = preparar(tmp_path)
    figs.mkdir(parents=True)
    (figs / "riesgo_lima.png").write_bytes(b"png")
    (figs / "sensibilidad_lima.png").write_bytes(b"png")
    r = gf.main(["--bench", str(bench), "--cientifico", str(cient), "--figuras", str(figs)])
    assert not (figs / "final_riesgo_lima.png").exists()
    assert not (figs / "final_sensibilidad.png").exists()
    assert "riesgo_lima.png" in r["reutilizadas"] and "sensibilidad_lima.png" in r["reutilizadas"]


def test_tolera_entradas_faltantes(tmp_path, capsys):
    bench = tmp_path / "bench"
    escribir(bench / "openmp.csv", [
        dict(backend="openmp", hilos=h, schedule="static", n=1000, media=4.0 / h, desviacion=0.0, **META)
        for h in (2, 4)])
    escribir(bench / "secuencial_t1.csv", [dict(backend="serial", n=1000, media=4.0, desviacion=0.0, **META)])
    figs = tmp_path / "figuras"
    r = gf.main(["--bench", str(bench), "--cientifico", str(tmp_path / "nada"), "--figuras", str(figs)])
    assert (figs / "final_speedup.png").exists()
    assert "final_x3_tiempo" in r["omitidas"] and "final_e1_e2" in r["omitidas"]
    assert "AVISO" in capsys.readouterr().err
