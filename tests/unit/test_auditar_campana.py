"""T34: integridad, conteo por modelo y verificación de copias reales."""
import csv
import importlib.util
import json
from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("auditar_campana", ROOT / "scripts/run/auditar_campana.py")
aud = importlib.util.module_from_spec(spec)
spec.loader.exec_module(aud)


@pytest.fixture
def raiz(tmp_path):
    carpeta = tmp_path / "original/results/cientifico"
    carpeta.mkdir(parents=True)
    for sufijo in ("", "_h5"):
        for experimento in ("x6", "bootstrap"):
            ruta = carpeta / f"{experimento}{sufijo}.csv"
            with ruta.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=["n", "k", "hist512"])
                w.writeheader()
                w.writerow(dict(n=10, k=2, hist512=";".join(map(str, [8, 2] + [0] * 510))))
            log = carpeta / f"{experimento}{sufijo}.log"
            log.write_text("[codigo_salida] 0\n", encoding="utf-8")
            datos = dict(puntos=[dict(estado="ok", n=10)],
                         sesiones=[dict(log=log.relative_to(tmp_path / "original").as_posix())])
            (carpeta / f"{experimento}{sufijo}_manifiesto.json").write_text(json.dumps(datos), encoding="utf-8")
    return tmp_path / "original"


def test_cuenta_modelos_separados_y_agrega_hashes(raiz):
    datos = aud.auditar(raiz, actualizar=True)
    assert datos["campanas"]["sin_h5"]["escenarios_total"] == 20
    assert datos["campanas"]["h5"]["escenarios_total"] == 20
    assert datos["campanas"]["h5"]["faltan_para_meta"] == aud.META - 20
    assert not datos["dos_respaldos_verificados"]
    m = json.loads((raiz / "results/cientifico/x6_manifiesto.json").read_text(encoding="utf-8"))
    assert len(m["integridad"]["archivos"]) == 2
    assert all(len(a["sha256"]) == 64 for a in datos["archivos"])
    assert aud.verificar(raiz, datos) == []


def test_detecta_archivo_modificado_y_archivo_ausente(raiz):
    datos = aud.auditar(raiz)
    (raiz / "results/cientifico/x6.csv").write_text("alterado", encoding="utf-8")
    (raiz / "results/cientifico/bootstrap.log").unlink()
    assert set(aud.verificar(raiz, datos)) == {"results/cientifico/x6.csv", "results/cientifico/bootstrap.log"}


def test_rechaza_histograma_roto(raiz):
    ruta = raiz / "results/cientifico/x6.csv"
    ruta.write_text(ruta.read_text().replace("8;2;", "7;2;"), encoding="utf-8")
    with pytest.raises(ValueError, match="incoherentes"):
        aud.auditar(raiz)


def test_manifiesto_incoherente_no_modifica_los_otros(raiz):
    anterior = (raiz / "results/cientifico/x6_manifiesto.json").read_bytes()
    ruta = raiz / "results/cientifico/bootstrap_h5_manifiesto.json"
    datos = json.loads(ruta.read_text())
    datos["puntos"][0]["n"] = 9
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    with pytest.raises(ValueError, match="no coinciden"):
        aud.auditar(raiz, actualizar=True)
    assert (raiz / "results/cientifico/x6_manifiesto.json").read_bytes() == anterior


def test_solo_registra_dos_respaldos_con_hashes_validos(raiz, tmp_path):
    copias = [("PC1", tmp_path / "copia1"), ("PC2", tmp_path / "copia2")]
    for _, carpeta in copias:
        shutil.copytree(raiz, carpeta)
    assert aud.auditar(raiz, respaldos=copias)["dos_respaldos_verificados"]
    (copias[1][1] / "results/cientifico/x6.log").write_text("corrupto", encoding="utf-8")
    datos = aud.auditar(raiz, respaldos=copias)
    assert not datos["dos_respaldos_verificados"]
    assert datos["respaldos"][1]["errores"] == ["results/cientifico/x6.log"]


def test_no_acepta_copia_de_trabajo_como_respaldo(raiz):
    with pytest.raises(ValueError, match="copia de trabajo"):
        aud.auditar(raiz, respaldos=[("PC1", raiz)])


def test_parametros_bootstrap_repetidos_se_reportan_sin_inventar_independencia(raiz):
    ruta = raiz / "results/cientifico/bootstrap.csv"
    with ruta.open("a", encoding="utf-8") as f:
        f.write(ruta.read_text().splitlines()[1] + "\n")
    resumen = aud.resumen_csv(ruta)
    assert resumen["escenarios"] == 20
    assert resumen["configuraciones_distintas"] == 1
    assert resumen["filas_con_parametros_repetidos"] == 1
