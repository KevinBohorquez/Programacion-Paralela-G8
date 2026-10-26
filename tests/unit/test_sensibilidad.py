"""T42 (X7): plan U × régimen (× C), reanudación, tabla y figuras de sensibilidad.py, sin simular."""

import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts" / "run"


def cargar(nombre, archivo):
    sys.path.insert(0, str(RUN))
    spec = importlib.util.spec_from_file_location(nombre, RUN / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


sys.path.insert(0, str(RUN))
comun = importlib.import_module("_comun_cientifico")
x7 = cargar("sensibilidad", "sensibilidad.py")


def escribir_config(ruta, estacion, regimen, config_id, p01):
    ruta.write_text(
        f"estacion: {estacion}\nregimen: {regimen}\nconfig_id: {config_id}\nsemilla: 5\n"
        f"n: 1000\ndias: 120\np01: {p01}\np11: 0.3\nalfa: 0.7\ntheta: 5.5\n"
        f"capacidad: 6\numbral: 50\n", encoding="utf-8")
    return ruta


def prob(p):
    return min(1.0, float(p["p01"]) * 20.0 / float(p["umbral"]))


class SensibilidadTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "_build"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.cfgs = [escribir_config(self.dir / "s1_normal.yaml", "s1", "normal", 0, 0.5),
                     escribir_config(self.dir / "s1_el_nino.yaml", "s1", "el_nino", 1, 1.0)]
        self.salida = self.dir / "x7.csv"

    def args(self, *extra):
        return ["--configs", *map(str, self.cfgs), "--n", "1000", "--salida", str(self.salida),
                "--logs", str(self.dir / "logs"), "--manifiesto", str(self.dir / "m.json"),
                "--tablas", str(self.dir / "tablas"), "--figuras", str(self.dir / "figs"), *extra]

    def test_plan_umbral_por_regimen(self):
        plan = x7.generar_plan(self.cfgs, [30, 50, 80], n=100)
        self.assertEqual(len(plan), 6)
        self.assertEqual({p.capacidad for p in plan}, {6.0})
        self.assertEqual(sorted({p.umbral for p in plan}), [30.0, 50.0, 80.0])
        con_c = x7.generar_plan(self.cfgs, [30, 50, 80], n=100, capacidades=[4, 8])
        self.assertEqual(len(con_c), 12)

    def test_dry_run(self):
        self.assertEqual(x7.main(self.args("--dry-run")), 0)
        self.assertFalse(self.salida.exists())

    def test_corre_reanuda_y_grafica(self):
        self.assertEqual(x7.main(self.args("--runner-falso")), 0)
        filas = comun.leer_resultados(self.salida)
        self.assertEqual(len(filas), 6)
        self.assertEqual(x7.main(self.args("--runner-falso")), 0)  # nada pendiente
        self.assertEqual(len(comun.leer_resultados(self.salida)), 6)
        with (self.dir / "tablas" / "sensibilidad.csv").open(encoding="utf-8", newline="") as f:
            tabla = list(csv.DictReader(f))
        fila = next(t for t in tabla if t["regimen"] == "normal" and t["umbral"] == "50")
        self.assertAlmostEqual(float(fila["p_hat"]), 0.2)
        # El histograma de Amax reproduce k para U entero (chequeo de consistencia).
        self.assertTrue(all(t["p_hist"] == t["p_hat"] for t in tabla))
        self.assertTrue((self.dir / "tablas" / "sensibilidad.md").exists())
        for nombre in ("sensibilidad_s1", "sensibilidad_resumen"):
            for ext in ("png", "svg"):
                self.assertGreater((self.dir / "figs" / f"{nombre}.{ext}").stat().st_size, 0)

    def test_excedencia_desde_hist(self):
        hist = [0] * 512
        hist[0], hist[29], hist[30], hist[511] = 5, 1, 2, 2
        self.assertAlmostEqual(comun.excedencia_hist(hist, 30), 0.4)
        self.assertAlmostEqual(comun.excedencia_hist(hist, 29), 0.5)


if __name__ == "__main__":
    unittest.main()
