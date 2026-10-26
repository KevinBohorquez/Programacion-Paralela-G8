"""T34 (X6): plan, reanudación, comandos y manifiesto de corrida-oficial.py, sin simular."""

import csv
import importlib.util
import json
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
x6 = cargar("corrida_oficial", "corrida-oficial.py")


def escribir_config(ruta, estacion, regimen, config_id, capacidad=6, umbral=50, p01=0.05):
    ruta.write_text(
        f"# prueba\nestacion: {estacion}\nregimen: {regimen}\nconfig_id: {config_id}\n"
        f"semilla: 777\nn: 1000\ndias: 120\np01: {p01}\np11: 0.3\nalfa: 0.7\ntheta: 5.5\n"
        f"capacidad: {capacidad}\numbral: {umbral}\n", encoding="utf-8")
    return ruta


class CorridaOficialTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "_build"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.cfg_a = escribir_config(self.dir / "a_normal.yaml", "a", "normal", 0)
        self.cfg_b = escribir_config(self.dir / "a_el_nino.yaml", "a", "el_nino", 1, capacidad=7)
        self.salida = self.dir / "x6.csv"
        self.logs = self.dir / "logs"
        self.manifiesto = self.dir / "x6_manifiesto.json"

    def ejecutar(self, plan, runner, dry_run=False, backend="openmp"):
        return comun.ejecutar_plan(
            plan, salida=self.salida, logs=self.logs, manifiesto=self.manifiesto,
            experimento="x6", backend=backend, build_dir=self.dir / "build", hilos=4,
            procesos=2, runner=runner, dry_run=dry_run)

    def test_plan_incluye_capacidad_de_la_config_y_ordena(self):
        plan = x6.generar_plan([self.cfg_a, self.cfg_b], [4, 2, 6], n=5000)
        self.assertEqual([(p.regimen, p.capacidad) for p in plan],
                         [("normal", 2.0), ("normal", 4.0), ("normal", 6.0),
                          ("el_nino", 2.0), ("el_nino", 4.0), ("el_nino", 6.0), ("el_nino", 7.0)])
        self.assertTrue(all(p.n == 5000 and p.umbral == 50.0 and p.semilla == "777" for p in plan))
        self.assertEqual({p.config_id for p in plan}, {"0", "1"})

    def test_umbral_se_puede_fijar(self):
        plan = x6.generar_plan([self.cfg_a], [6], n=10, umbral=30)
        self.assertEqual([p.umbral for p in plan], [30.0])

    def test_reanuda_omitiendo_puntos_ya_presentes(self):
        plan = x6.generar_plan([self.cfg_a, self.cfg_b], [2, 6], n=1000)
        runner = comun.RunnerFalso()
        self.ejecutar(plan[:2], runner)
        self.assertEqual(len(runner.comandos), 2)
        pendientes = comun.pendientes(plan, self.salida)
        self.assertEqual(len(pendientes), len(plan) - 2)
        # Otro N es otro punto (C = 2 y la C = 6 del YAML).
        otro_n = x6.generar_plan([self.cfg_a], [2], n=2000)
        self.assertEqual(len(comun.pendientes(otro_n, self.salida)), 2)
        runner2 = comun.RunnerFalso()
        resumen = self.ejecutar(plan, runner2)
        self.assertEqual(len(runner2.comandos), len(plan) - 2)
        self.assertEqual(resumen["omitidos"], 2)
        with self.salida.open(encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual(len(filas), len(plan))
        self.assertEqual(comun.pendientes(plan, self.salida), [])

    def test_manifiesto_registra_semillas_duraciones_y_sesiones(self):
        plan = x6.generar_plan([self.cfg_a, self.cfg_b], [6], n=1000)
        self.ejecutar(plan, comun.RunnerFalso())
        self.ejecutar(plan, comun.RunnerFalso())  # reanudación: nada pendiente
        datos = json.loads(self.manifiesto.read_text(encoding="utf-8"))
        self.assertEqual(datos["semillas"]["a/normal"], {"semilla": "777", "config_id": "0"})
        self.assertEqual(len(datos["puntos"]), len(plan))
        self.assertTrue(all(p["estado"] == "ok" and p["duracion_s"] >= 0 for p in datos["puntos"]))
        self.assertEqual(len(datos["sesiones"]), 2)
        self.assertIn("commit", datos["sesiones"][0])
        self.assertIn("cpu", datos["sesiones"][0]["hardware"])
        self.assertIn("V6", datos["nota"])

    def test_dry_run_no_ejecuta_ni_escribe(self):
        plan = x6.generar_plan([self.cfg_a], [2, 6], n=1000)
        runner = comun.RunnerFalso()
        resumen = self.ejecutar(plan, runner, dry_run=True)
        self.assertEqual(runner.comandos, [])
        self.assertEqual(len(resumen["comandos"]), 2)
        self.assertFalse(self.salida.exists())
        self.assertFalse(self.manifiesto.exists())

    def test_comandos_openmp_e_hibrido(self):
        punto = x6.generar_plan([self.cfg_a], [3.5], n=1000)[0]
        omp = comun.comando(punto, "openmp", Path("b"), hilos=16, procesos=1, salida=Path("o.csv"))
        self.assertEqual(Path(omp[0]).as_posix(), "b/src/backends/openmp/pp_openmp")
        self.assertEqual(omp[omp.index("--capacidad") + 1], "3.5")
        self.assertEqual(omp[omp.index("--hilos") + 1], "16")
        hib = comun.comando(punto, "hibrido", Path("b"), hilos=8, procesos=2, salida=Path("o.csv"))
        self.assertEqual(hib[:5], ["mpirun", "-np", "2", "--bind-to", "none"])
        self.assertEqual(Path(hib[5]).as_posix(), "b/src/backends/hybrid/pp_hibrido")

    def test_fallo_del_simulador_queda_registrado(self):
        plan = x6.generar_plan([self.cfg_a], [2, 6], n=1000)
        resumen = self.ejecutar(plan, comun.RunnerFalso(falla_en={2.0}))
        self.assertEqual(resumen["errores"], 1)
        datos = json.loads(self.manifiesto.read_text(encoding="utf-8"))
        self.assertEqual(sorted(p["estado"] for p in datos["puntos"]), ["error", "ok"])
        self.assertEqual(len(comun.pendientes(plan, self.salida)), 1)

    def test_main_dry_run_por_cli(self):
        codigo = x6.main(["--configs", str(self.cfg_a), "--capacidades", "2,3", "--n", "1e3",
                          "--salida", str(self.salida), "--logs", str(self.logs),
                          "--manifiesto", str(self.manifiesto), "--dry-run"])
        self.assertEqual(codigo, 0)
        self.assertFalse(self.salida.exists())


if __name__ == "__main__":
    unittest.main()
