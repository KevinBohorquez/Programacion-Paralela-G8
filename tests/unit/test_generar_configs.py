"""Pruebas de scripts/run/generar_configs.py (T10): selección de estaciones y YAML por estación/régimen.

Uso:  python3 -m pytest -q tests/unit/test_generar_configs.py
"""
import csv
import importlib.util
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def gen():
    spec = importlib.util.spec_from_file_location("generar_configs", RAIZ / "scripts" / "run" / "generar_configs.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def resumen(elegibles, auditados, pct):
    return {"auditados": auditados, "elegibles": elegibles, "pct_faltantes": pct,
            "estacion_elegible": elegibles >= 0.9 * auditados}


def test_dias_temporada_por_zona(gen):
    assert gen.dias_temporada((1, 2, 3, 4)) == 120
    assert gen.dias_temporada((6, 7, 8, 9)) == 122


def test_resumir_auditoria(gen):
    filas = [dict(estacion="a", elegible="True", pct_faltantes="0.0"),
             dict(estacion="a", elegible="False", pct_faltantes="0.2")]
    r = gen.resumir_auditoria(filas)["a"]
    assert r["auditados"] == 2 and r["elegibles"] == 1
    assert r["pct_faltantes"] == pytest.approx(10.0) and r["estacion_elegible"] is False


def test_seleccion_prioriza_elegibles_y_menor_faltante(gen):
    res = {"n1": resumen(40, 43, 3.5), "n2": resumen(45, 51, 2.0), "n3": resumen(47, 50, 4.5),
           "l1": resumen(23, 25, 3.9), "corta": resumen(10, 10, 0.0)}
    zonas = {"n1": "costa_norte", "n2": "costa_norte", "n3": "costa_norte", "l1": "lima", "corta": "lima"}
    elegidas = [e for e, _ in gen.seleccionar(res, zonas, n=4)]
    # n2 tiene menos faltantes pero no es elegible como estación completa (45/51 < 90 %): va al final.
    assert elegidas == ["n1", "l1", "n3", "n2"]
    assert "corta" not in elegidas  # menos de 20 años elegibles


def test_seleccion_garantiza_una_estacion_de_lima(gen):
    res = {"n1": resumen(40, 40, 1.0), "n2": resumen(40, 40, 2.0), "l1": resumen(30, 40, 9.0)}
    zonas = {"n1": "costa_norte", "n2": "costa_norte", "l1": "lima"}
    elegidas = [e for e, _ in gen.seleccionar(res, zonas, n=2)]
    assert elegidas == ["n1", "l1"]


def test_escribir_configs_contrato_y_omite_invalidas(gen, tmp_path):
    filas = [
        dict(estacion="est_a", regimen="normal", n_anios="30", p01="0.1", p11="0.4", alfa="0.7", theta="9.0",
             estado_validacion="OK"),
        dict(estacion="est_a", regimen="el_nino", n_anios="2", p01="0.3", p11="0.6", alfa="0.6", theta="20.0",
             estado_validacion="OK"),
        dict(estacion="est_b", regimen="normal", n_anios="30", p01="nan", p11="0.4", alfa="0.7", theta="9.0",
             estado_validacion="OK"),
        dict(estacion="est_b", regimen="el_nino", n_anios="30", p01="0.1", p11="1.4", alfa="0.7", theta="9.0",
             estado_validacion="FALLA"),
        dict(estacion="fuera", regimen="normal", n_anios="30", p01="0.1", p11="0.4", alfa="0.7", theta="9.0",
             estado_validacion="OK"),
    ]
    plantilla = {"semilla": "1", "n": "1000", "dias": "120", "capacidad": "6", "umbral": "50", "salida": "x.csv"}
    escritos = gen.escribir_configs(filas, ["est_a", "est_b"], {"est_a": 122, "est_b": 120}, plantilla,
                                    "plantilla.yaml", "parametros.csv", tmp_path, "abc123")
    assert [p.name for p in escritos] == ["est_a_el_nino.yaml", "est_a_normal.yaml"]
    texto = (tmp_path / "est_a_el_nino.yaml").read_text(encoding="utf-8")
    assert "ADVERTENCIA: muestra pequeña" in texto and "commit abc123" in texto
    pares = dict(l.split(": ", 1) for l in texto.splitlines() if l and not l.startswith("#"))
    assert set(pares) <= gen.CLAVES_CONTRATO and "salida" not in pares
    assert pares["config_id"] == "0" and pares["dias"] == "122" and pares["p11"] == "0.6"
    assert (tmp_path / "est_a_normal.yaml").read_text(encoding="utf-8").count("config_id: 1") == 1


def test_configs_versionadas_cumplen_el_contrato(gen):
    """Los YAML generados que están en config/ solo usan claves del contrato y coinciden con la selección."""
    seleccion = RAIZ / "data" / "processed" / "estaciones_seleccionadas.csv"
    if not seleccion.exists():
        pytest.skip("aún no se generó data/processed/estaciones_seleccionadas.csv")
    with open(seleccion, newline="", encoding="utf-8") as f:
        estaciones = {fila["estacion"] for fila in csv.DictReader(f)}
    configs = [p for p in (RAIZ / "config").glob("*.yaml") if p.read_text(encoding="utf-8").startswith("# T10")]
    assert configs, "no hay configuraciones T10 en config/"
    ids = set()
    for p in configs:
        pares = gen.leer_plantilla(p)
        assert pares["estacion"] in estaciones
        ids.add(pares["config_id"])
    assert len(ids) == len(configs)  # config_id único entre configuraciones
