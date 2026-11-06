"""Pruebas de T14 (scripts/bench/medir_secuencial.py) sin ejecutar el binario real.

Cubre las partes puras: estadísticas, verificación de k entre repeticiones, marca del riesgo de
10 µs por temporada y formato del CSV, que debe leerse tal cual con el cargador --t1-csv de
scripts/bench/graficar_openmp_ashley.py. La ejecución de pp_serial se sustituye por un doble.

Uso:   python3 -m pytest -v tests/unit/test_medir_secuencial.py
"""
import csv
import importlib.util
import statistics
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BENCH = RAIZ / "scripts" / "bench"


def cargar(nombre, archivo):
    spec = importlib.util.spec_from_file_location(nombre, BENCH / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def ms():
    return cargar("medir_secuencial", "medir_secuencial.py")


@pytest.fixture(scope="module")
def ashley():
    return cargar("graficar_openmp_ashley", "graficar_openmp_ashley.py")


def corrida(tiempo, k="1234", n="1000", hist="1;2;3"):
    """Fila mínima con las columnas del CSV de pp_serial que usa la medición."""
    return {"backend": "serial", "n": n, "k": k, "hist512": hist, "dias": "120", "tiempo_s": str(tiempo)}


TIEMPOS = [0.0104, 0.0101, 0.0102, 0.0103, 0.0100]


def test_resumir_media_y_desviacion_muestral(ms):
    media, desviacion = ms.resumir(TIEMPOS)
    assert media == pytest.approx(statistics.mean(TIEMPOS))
    assert desviacion == pytest.approx(statistics.stdev(TIEMPOS))
    assert ms.resumir([0.5]) == (0.5, 0.0)


def test_us_por_escenario(ms):
    assert ms.us_por_escenario(2.0, 1_000_000) == pytest.approx(2.0)
    assert ms.us_por_escenario(116.0, 20_000_000) == pytest.approx(5.8)  # hipótesis de 5,8 µs (§6.3)


def test_k_identico_devuelve_k(ms):
    assert ms.verificar_k([corrida(t) for t in [0.01] + TIEMPOS]) == "1234"


@pytest.mark.parametrize("campo", ["k", "hist"])
def test_k_distinto_falla_con_mensaje(ms, campo):
    corridas = [corrida(t) for t in TIEMPOS]
    corridas[3] = corrida(TIEMPOS[3], **{campo: "999"})
    with pytest.raises(SystemExit) as e:
        ms.verificar_k(corridas)
    assert "k" in str(e.value) and "semilla" in str(e.value)


@pytest.mark.parametrize("media,esperado", [(0.0099, 0), (0.0100, 1), (0.0150, 1)])
def test_marca_riesgo_10us(ms, media, esperado):
    # n = 1000: media / n * 1e6 = 9.9, 10.0 y 15.0 µs por temporada
    fila = ms.construir_fila(cal=corrida(0.02), reps=[corrida(media)] * 5, n=1000, semilla=7, config_id=0, meta={})
    assert fila["supera_10us"] == esperado


def test_fila_completa(ms):
    meta = dict(cpu="CPU de prueba", nucleos_fisicos=8, nucleos_logicos=16, ram_gb=31.2, compilador="g++ 13",
                tipo_build="Release", commit="abc", fecha="2026-10-15T10:00:00-05:00", so="Linux")
    fila = ms.construir_fila(cal=corrida(0.02), reps=[corrida(t) for t in TIEMPOS], n=1000, semilla=7,
                             config_id=3, meta=meta)
    for col in ("n", "semilla", "config_id", "k", "cpu", "nucleos_fisicos", "nucleos_logicos", "ram_gb",
                "compilador", "tipo_build", "commit", "fecha", "so", "t_calentamiento", "t1", "t2", "t3", "t4",
                "t5", "media", "desviacion", "us_por_escenario", "supera_10us"):
        assert col in fila, col
    assert [fila[f"t{i}"] for i in range(1, 6)] == TIEMPOS
    assert fila["t_calentamiento"] == 0.02
    assert fila["k"] == "1234" and fila["config_id"] == 3 and fila["dias"] == "120"
    assert fila["us_por_escenario"] == pytest.approx(statistics.mean(TIEMPOS) / 1000 * 1e6)


def test_csv_lo_lee_t1_csv_de_ashley(ms, ashley, tmp_path):
    fila = ms.construir_fila(cal=corrida(0.02), reps=[corrida(t) for t in TIEMPOS], n=1000, semilla=7,
                             config_id=0, meta={})
    ruta = tmp_path / "sub" / "secuencial_t1.csv"
    ms.escribir_csv(ruta, fila)
    with open(ruta, newline="") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == 1
    t1, s1 = ashley.t1_desde_csv(str(ruta))
    assert t1 == pytest.approx(statistics.mean(TIEMPOS))
    assert s1 == pytest.approx(statistics.stdev(TIEMPOS))


# ---------- main() con pp_serial sustituido ----------
def preparar_build(tmp_path, tipo="Release"):
    bd = tmp_path / "build"
    exe = bd / "src" / "backends" / "serial" / "pp_serial"
    exe.parent.mkdir(parents=True)
    exe.write_text("")  # basta con que exista: correr() está sustituido
    (bd / "CMakeCache.txt").write_text(f"CMAKE_BUILD_TYPE:STRING={tipo}\n")
    return bd


@pytest.fixture
def doble(ms, monkeypatch):
    """Sustituye correr() por una cola de resultados y registra los comandos."""
    llamadas = []

    def instalar(resultados):
        cola = list(resultados)

        def correr(exe, comunes, extra, entorno):
            llamadas.append((Path(exe).name, list(comunes), list(extra)))
            return cola.pop(0)

        monkeypatch.setattr(ms, "correr", correr)
        monkeypatch.setattr(ms, "commit_git", lambda: "prueba")
        return llamadas

    return instalar


def test_main_calentamiento_mas_repeticiones(ms, ashley, doble, tmp_path, capsys):
    bd = preparar_build(tmp_path)
    salida = tmp_path / "t1.csv"
    llamadas = doble([corrida(0.02)] + [corrida(t) for t in TIEMPOS])
    ms.main(["--build-dir", str(bd), "--n", "1000", "--salida", str(salida)])
    assert len(llamadas) == 6
    assert all(nombre == "pp_serial" for nombre, _, _ in llamadas)
    comunes = llamadas[0][1]
    assert comunes[comunes.index("--n") + 1] == "1000"
    assert comunes[comunes.index("--semilla") + 1] == "20261015"
    with open(salida, newline="") as f:
        fila = next(csv.DictReader(f))
    assert fila["tipo_build"] == "Release" and fila["commit"] == "prueba" and fila["supera_10us"] == "1"
    assert ashley.t1_desde_csv(str(salida))[0] == pytest.approx(statistics.mean(TIEMPOS))
    assert "AVISO" in capsys.readouterr().err  # 10.2 µs por temporada >= 10


def test_main_k_inconsistente_no_escribe(ms, doble, tmp_path):
    bd = preparar_build(tmp_path)
    salida = tmp_path / "t1.csv"
    reps = [corrida(t) for t in TIEMPOS]
    reps[-1] = corrida(TIEMPOS[-1], k="1")
    doble([corrida(0.02)] + reps)
    with pytest.raises(SystemExit) as e:
        ms.main(["--build-dir", str(bd), "--n", "1000", "--salida", str(salida)])
    assert e.value.code not in (0, None)
    assert not salida.exists()


def test_main_rechaza_debug(ms, doble, tmp_path):
    bd = preparar_build(tmp_path, tipo="Debug")
    llamadas = doble([])
    with pytest.raises(SystemExit) as e:
        ms.main(["--build-dir", str(bd), "--salida", str(tmp_path / "t1.csv")])
    assert "Release" in str(e.value)
    assert llamadas == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
