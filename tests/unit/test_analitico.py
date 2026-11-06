# T13 | Responsable: Lita | Revisión: Ashley | V7: caso analítico D = 1.
#
# Con un solo día y el día previo seco: llueve con probabilidad p01 y la lámina es R ~ gamma(alfa, theta).
# El balance da Amax = max(0, R - C), así que
#     P(inundación) = P(Amax > U) = p01 · P(R > C + U)
# y el histograma de Amax (clases de 1 mm, la 511 acumula la cola) también es exacto:
#     clase 0:   (1 - p01) + p01 · F(C + 1)
#     clase b:   p01 · [F(C + b + 1) - F(C + b)]        para 1 <= b <= 510
#     clase 511: p01 · (1 - F(C + 511))
# Aceptación: la probabilidad exacta cae dentro del IC de Wilson al 95 % que escribe pp_serial y el
# histograma no se rechaza con chi-cuadrado al 0,1 %.
#
# Uso (tras compilar):  python3 -m pytest -v -s tests/unit/test_analitico.py
# Variable opcional:    PP_BIN_DIR=<carpeta con serial/pp_serial>  (por defecto build/src/backends)
import csv
import os
import subprocess
from pathlib import Path

import pytest
from scipy import stats

RAIZ = Path(__file__).resolve().parents[2]
SERIAL = Path(os.environ.get("PP_BIN_DIR", RAIZ / "build" / "src" / "backends")) / "serial" / "pp_serial"
N = 1_000_000
SEMILLA = 20261015
NBINS = 512
ALFA_CHI2 = 0.001

CASOS = {
    # Parámetros de config/sintetico.yaml: probabilidad pequeña (~1e-4), donde Wald falla y Wilson no.
    "sintetico_cola": dict(p01=0.15, alfa=0.7, theta=9.0, capacidad=6.0, umbral=50.0),
    "alfa_mayor_1": dict(p01=0.40, alfa=2.0, theta=10.0, capacidad=5.0, umbral=20.0),
    "alfa_menor_1_sin_drenaje": dict(p01=0.70, alfa=0.5, theta=20.0, capacidad=0.0, umbral=10.0),
    # alfa = 1 (exponencial): cola cerrada P = p01 · exp(-(C + U) / theta).
    "alfa_igual_1": dict(p01=0.20, alfa=1.0, theta=8.0, capacidad=5.0, umbral=15.0),
}

pytestmark = pytest.mark.skipif(not SERIAL.exists(), reason=f"compile primero (cmake --build build); no existe {SERIAL}")


def ejecutar(tmp_path, nombre, params, n=N, semilla=SEMILLA):
    salida = tmp_path / f"{nombre}.csv"
    cmd = [str(SERIAL), "--dias", "1", "--p11", "0.5", "--n", str(n), "--semilla", str(semilla),
           "--silencioso", "--salida", str(salida)]
    for clave, valor in params.items():
        cmd += [f"--{clave}", str(valor)]
    subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=600)
    with open(salida, newline="") as f:
        return next(csv.DictReader(f))


def prob_exacta(p01, alfa, theta, capacidad, umbral):
    return p01 * stats.gamma.sf(capacidad + umbral, alfa, scale=theta)


def hist_exacto(p01, alfa, theta, capacidad, umbral):
    F = stats.gamma(alfa, scale=theta).cdf
    probs = [(1 - p01) + p01 * F(capacidad + 1)]
    probs += [p01 * (F(capacidad + b + 1) - F(capacidad + b)) for b in range(1, NBINS - 1)]
    probs.append(p01 * (1 - F(capacidad + NBINS - 1)))
    return probs


@pytest.mark.parametrize("nombre", list(CASOS))
def test_v7_probabilidad_exacta_dentro_de_wilson(tmp_path, nombre):
    params = CASOS[nombre]
    fila = ejecutar(tmp_path, nombre, params)
    p = prob_exacta(**params)
    k, n = int(fila["k"]), int(fila["n"])
    inf, sup = float(fila["wilson_inf"]), float(fila["wilson_sup"])
    print(f"\n[V7] caso={nombre} N={n} semilla={SEMILLA} params={params}")
    print(f"[V7] esperado p={p:.8g}  observado k={k} p_hat={k / n:.8g}  Wilson95=[{inf:.8g}, {sup:.8g}]")
    assert n == N and int(fila["dias"]) == 1
    assert inf <= p <= sup, f"{nombre}: p exacta {p:.6g} fuera de Wilson [{inf:.6g}, {sup:.6g}]"


@pytest.mark.parametrize("nombre", ["alfa_mayor_1", "alfa_menor_1_sin_drenaje"])
def test_v7_histograma_exacto_chi_cuadrado(tmp_path, nombre):
    params = CASOS[nombre]
    fila = ejecutar(tmp_path, nombre, params)
    observados = [int(x) for x in fila["hist512"].split(";")]
    esperados = [N * q for q in hist_exacto(**params)]
    assert sum(observados) == N

    # Agrupa clases consecutivas hasta tener >= 5 esperados por grupo (condición de la prueba chi-cuadrado).
    obs_g, esp_g, o_acc, e_acc = [], [], 0, 0.0
    for o, e in zip(observados, esperados):
        o_acc, e_acc = o_acc + o, e_acc + e
        if e_acc >= 5:
            obs_g.append(o_acc)
            esp_g.append(e_acc)
            o_acc, e_acc = 0, 0.0
    obs_g[-1] += o_acc
    esp_g[-1] += e_acc
    esp_g = [e * N / sum(esp_g) for e in esp_g]  # corrige el redondeo de la suma de probabilidades
    chi2 = stats.chisquare(obs_g, esp_g)
    print(f"\n[V7] caso={nombre} histograma: {len(obs_g)} grupos chi2={chi2.statistic:.2f} p={chi2.pvalue:.4f}")
    assert chi2.pvalue >= ALFA_CHI2, f"{nombre}: el histograma difiere del exacto (p={chi2.pvalue:.3g})"


def test_v7_extremo_sin_lluvia_k_cero(tmp_path):
    fila = ejecutar(tmp_path, "p01_cero", dict(p01=0.0, alfa=1.0, theta=5.0, capacidad=0.0, umbral=0.0), n=10_000)
    assert int(fila["k"]) == 0 and float(fila["wilson_inf"]) == 0.0
    assert int(fila["hist512"].split(";")[0]) == 10_000


def test_v7_extremo_siempre_inunda_k_igual_n(tmp_path):
    """p01 = 1, C = 0, U = 0: toda lámina gamma es > 0, así que todo escenario inunda."""
    fila = ejecutar(tmp_path, "p01_uno", dict(p01=1.0, alfa=1.0, theta=5.0, capacidad=0.0, umbral=0.0), n=10_000)
    assert int(fila["k"]) == 10_000 and float(fila["wilson_sup"]) == 1.0
