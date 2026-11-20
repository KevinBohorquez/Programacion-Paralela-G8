"""T13 | Diagnostico de V6 frente a lo observado (por que fallan las colas).

Reproduce, para cada grupo estacion x regimen de data/processed/parametros.csv, los montos de los
dias lluviosos con la MISMA ventana, umbral y anios que calibrar.py y test_estadistico.py, y compara
varias explicaciones de la cola ligera del modelo:

  H1  error de implementacion: umbral distinto, unidades, dias secos en los momentos, regimenes
      mezclados -> se comprueba que n_dias_lluvia y la media cuadran con parametros.csv, y cuanta
      masa pone la gamma calibrada por debajo del umbral de 0,1 mm.
  H2  estimador: Thom frente a maxima verosimilitud exacta (scipy, loc=0).
  H3  forma de la distribucion: gamma frente a exponencial mixta (3 parametros, EM) y gamma con
      cola de Pareto generalizada (GPD) por encima del percentil 90.
  H4  heterogeneidad: una gamma por mes de la temporada y una gamma por anio (mezcla ponderada por
      el numero de dias lluviosos), frente a una sola gamma por temporada.
  H5  escala aleatoria por temporada: los montos de cada temporada se multiplican por
      M ~ Gamma(kappa, 1/kappa) (media 1), con kappa en forma cerrada para igualar el CV observado.
      "escala_temporada" conserva (alfa, theta) de Thom (solo agrega kappa); "escala_temporada_z"
      toma alfa de Thom sobre los montos divididos por la media de su temporada.
  H6  gamma truncada: el pluviometro no registra montos < 0,1 mm, asi que (alfa, theta) se estiman por
      maxima verosimilitud de la gamma condicionada a X >= 0,1 mm y se simula esa misma gamma truncada.
      "gamma_truncada+escala" le suma la escala por temporada de H5.

Ademas de la regla del 10 %, cada candidato se evalua con el criterio de la prueba V6
(tests/unit/test_estadistico.py): IC bootstrap por temporadas, KS de montos registrados a 0,1 mm con
valor p por bootstrap parametrico (--b-ks replicas) y Bonferroni por grupo.

Para cada candidato se simula la cadena de Markov calibrada (p01, p11) con el monto candidato en
numpy y se calculan los mismos estadisticos que V6 (frecuencia, media, desviacion, p95, p99, racha
media, maximo diario medio por temporada) mas KS de dos muestras frente a lo observado. Ademas se
reporta KS con lo simulado redondeado a 0,1 mm y truncado en 0,1 mm (resolucion del pluviometro).

Uso (imagen pp-g8):  python3 scripts/run/diagnostico_v6.py [--n 20000] [--salida results/validacion/diagnostico_v6.csv]
"""

from __future__ import annotations

import argparse
import calendar
import csv
import datetime
import importlib.util
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import optimize, stats

RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "data" / "raw"
PARAMETROS = RAIZ / "data" / "processed" / "parametros.csv"
REGIMENES = RAIZ / "data" / "processed" / "regimenes.csv"
UMBRAL = 0.1
SEMILLA = 20261015
CAPACIDAD = 6.0          # C de config/*.yaml (mm/dia)
UMBRALES_X6 = (30.0, 50.0, 80.0)  # U de X6/X7 (mm)
ESTADISTICOS = ("frecuencia_lluvia", "media_monto", "desviacion_monto", "p95_monto", "p99_monto",
                "racha_media", "max_diario_temporada_medio")


def cargar_calibrar():
    spec = importlib.util.spec_from_file_location("calibrar_t10", RAIZ / "scripts" / "run" / "calibrar.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def leer_grupo(estacion, regimen, meses):
    """Igual que estadisticos_observados de test_estadistico.py, pero conserva anio y mes."""
    with REGIMENES.open(newline="", encoding="utf-8") as f:
        anios = {int(r["anio"]) for r in csv.DictReader(f) if r["estacion"] == estacion and r["regimen"] == regimen}
    dias = rachas = dias_en_rachas = racha = 0
    montos, anio_m, mes_m, max_anio, previa = [], [], [], defaultdict(float), None
    with (RAW / f"{estacion}.csv").open(newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = datetime.date.fromisoformat(fila["fecha"])
            if fecha.year not in anios or fecha.month not in meses:
                previa, racha = None, 0
                continue
            if previa is None or (fecha - previa).days != 1:
                racha = 0
            previa = fecha
            texto = fila["precipitacion_mm"]
            if texto == "" or float(texto) < 0:
                racha = 0
                continue
            v = float(texto)
            dias += 1
            max_anio[fecha.year] = max(max_anio[fecha.year], v)
            if v >= UMBRAL:
                montos.append(v)
                anio_m.append(fecha.year)
                mes_m.append(fecha.month)
                racha += 1
            elif racha:
                rachas, dias_en_rachas, racha = rachas + 1, dias_en_rachas + racha, 0
    m = np.array(montos)
    amax = amax_observado(estacion, anios, meses)
    obs = {
        "frecuencia_lluvia": len(m) / dias,
        "media_monto": m.mean(),
        "desviacion_monto": m.std(ddof=1),
        "p95_monto": float(np.percentile(m, 95)),
        "p99_monto": float(np.percentile(m, 99)),
        "racha_media": dias_en_rachas / rachas,
        "max_diario_temporada_medio": float(np.mean(list(max_anio.values()))),
    }
    return obs, m, np.array(anio_m), np.array(mes_m), max_anio, amax


def lindley_amax(montos):
    """Amax de balance_hidrico.cpp: A_d = max(0, A_{d-1} + r_d - C), Amax = max_d A_d (por fila)."""
    a = np.zeros(montos.shape[0])
    amax = np.zeros(montos.shape[0])
    for d in range(montos.shape[1]):
        a = np.maximum(0.0, a + montos[:, d] - CAPACIDAD)
        amax = np.maximum(amax, a)
    return amax


def amax_observado(estacion, anios, meses):
    """Amax de cada temporada observada (un faltante cuenta como 0 mm: cota inferior)."""
    por_anio = defaultdict(list)
    with (RAW / f"{estacion}.csv").open(newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = datetime.date.fromisoformat(fila["fecha"])
            if fecha.year in anios and fecha.month in meses:
                t = fila["precipitacion_mm"]
                por_anio[fecha.year].append(max(0.0, float(t)) if t != "" else 0.0)
    largo = max(len(v) for v in por_anio.values())
    mat = np.array([v + [0.0] * (largo - len(v)) for v in por_anio.values()])
    return lindley_amax(mat)


# ---------------- muestreadores de montos (rng, k) -> k montos ----------------

def gamma_sampler(a, th):
    return lambda rng, k: rng.gamma(a, th, k)


def mezcla_sampler(pesos, samplers):
    pesos = np.asarray(pesos, float) / np.sum(pesos)

    def f(rng, k):
        idx = rng.choice(len(pesos), size=k, p=pesos)
        out = np.empty(k)
        for i, s in enumerate(samplers):
            sel = idx == i
            if sel.any():
                out[sel] = s(rng, int(sel.sum()))
        return out
    return f


def ajustar_mixexp(x, iters=2000):
    """Exponencial mixta w*Exp(b1) + (1-w)*Exp(b2) por EM (Woolhiser y Roldan, 1982)."""
    w, b1, b2 = 0.7, 0.5 * x.mean(), 3.0 * x.mean()
    for _ in range(iters):
        f1 = w / b1 * np.exp(-x / b1)
        f2 = (1 - w) / b2 * np.exp(-x / b2)
        r = f1 / (f1 + f2)
        w_n, b1_n, b2_n = r.mean(), (r * x).sum() / r.sum(), ((1 - r) * x).sum() / (1 - r).sum()
        if abs(w_n - w) + abs(b1_n - b1) + abs(b2_n - b2) < 1e-12:
            w, b1, b2 = w_n, b1_n, b2_n
            break
        w, b1, b2 = w_n, b1_n, b2_n
    ll = np.log(w / b1 * np.exp(-x / b1) + (1 - w) / b2 * np.exp(-x / b2)).sum()
    return (w, b1, b2), ll


def gamma_gpd(x, a, th, q=0.90):
    """Cuerpo gamma (Thom) por debajo de u = percentil q empirico; por encima, u + GPD ajustada por
    maxima verosimilitud a los excesos. P(X > u) = 1 - q (se respeta la frecuencia empirica)."""
    u = float(np.quantile(x, q))
    exc = x[x > u] - u
    xi, _, sigma = stats.genpareto.fit(exc, floc=0)
    g = stats.gamma(a, scale=th)
    fu = g.cdf(u)

    def f(rng, k):
        cola = rng.random(k) > q
        out = np.empty(k)
        nc = int((~cola).sum())
        out[~cola] = g.ppf(rng.random(nc) * fu)  # gamma truncada a (0, u]
        out[cola] = u + stats.genpareto.rvs(xi, scale=sigma, size=int(cola.sum()), random_state=rng)
        return out
    return f, (u, xi, sigma)


def kappa_desde_cv(cv, cv_dentro):
    """H5: kappa de la escala por temporada M ~ Gamma(kappa, 1/kappa) (media 1) que, con montos de CV
    'cv_dentro' dentro de la temporada, iguala el CV total observado:
        CV^2 = (1 + 1/kappa)(1 + cv_dentro^2) - 1.
    Si el CV observado no supera el de los montos, no hay heterogeneidad que modelar (kappa = inf)."""
    inv = (cv ** 2 + 1.0) / (1.0 + cv_dentro ** 2) - 1.0
    return 1.0 / inv if inv > 1e-12 else math.inf


def kappa_escala(cv, alfa):
    """kappa para montos Gamma(alfa, theta), cuyo CV^2 es 1/alfa."""
    return kappa_desde_cv(cv, math.sqrt(1.0 / alfa))


# ---------------- H6: gamma truncada en el umbral del pluviometro ----------------

def momentos_gamma_truncada(a, th, u=UMBRAL):
    """Media y CV exactos de Gamma(a, th) condicionada a X >= u:
    E[X^k | X >= u] = th^k * Gamma(a+k)/Gamma(a) * S(u; a+k, th) / S(u; a, th)."""
    s0 = stats.gamma.sf(u, a, scale=th)
    m1 = a * th * stats.gamma.sf(u, a + 1, scale=th) / s0
    m2 = a * (a + 1) * th ** 2 * stats.gamma.sf(u, a + 2, scale=th) / s0
    return m1, math.sqrt(max(m2 - m1 ** 2, 0.0)) / m1


def ajustar_gamma_truncada(x, a0, th0, u=UMBRAL):
    """Maxima verosimilitud de (alfa, theta) sabiendo que solo se registran montos >= u:
    log L = sum log f(x; a, th) - n log S(u; a, th). Parte de Thom (a0, th0)."""
    def nll(par):
        a, th = np.exp(par)
        return -(stats.gamma.logpdf(x, a, scale=th).sum() - len(x) * stats.gamma.logsf(u, a, scale=th))
    r = optimize.minimize(nll, np.log([a0, th0]), method="Nelder-Mead",
                          options={"maxiter": 4000, "xatol": 1e-8, "fatol": 1e-8})
    a, th = np.exp(r.x)
    return float(a), float(th), float(r.fun)


def gamma_truncada_sampler(a, th, u=UMBRAL):
    """Montos de Gamma(a, th) condicionados a X >= u, por inversion de la CDF."""
    f0 = stats.gamma.cdf(u, a, scale=th)
    return lambda rng, k: stats.gamma.ppf(f0 + rng.random(k) * (1.0 - f0), a, scale=th)


def simular(p01, p11, dias, sampler, n, rng, kappa=math.inf):
    """Cadena de Markov con el dia previo seco (como simular_escenario) y montos del sampler. Con
    kappa finito (H5), todos los montos de una temporada se multiplican por M ~ Gamma(kappa, 1/kappa)."""
    estado = np.zeros(n, bool)
    lluvia = np.zeros((n, dias), bool)
    for d in range(dias):
        u = rng.random(n)
        estado = u < np.where(estado, p11, p01)
        lluvia[:, d] = estado
    nl = int(lluvia.sum())
    montos = np.zeros((n, dias))
    montos[lluvia] = sampler(rng, nl)
    if math.isfinite(kappa):
        montos *= rng.gamma(kappa, 1.0 / kappa, n)[:, None]
    m = montos[lluvia]
    # rachas cerradas por un dia seco dentro de la temporada
    fin = lluvia[:, :-1] & ~lluvia[:, 1:]
    rachas = int(fin.sum())
    abiertas_final = lluvia[:, -1]
    # dias en rachas cerradas = lluviosos - dias de la racha abierta al final
    largo_final = np.zeros(n, int)
    vivo = abiertas_final.copy()
    for d in range(dias - 1, -1, -1):
        largo_final += vivo & lluvia[:, d]
        vivo &= lluvia[:, d]
    return {
        "frecuencia_lluvia": nl / (n * dias),
        "media_monto": m.mean(),
        "desviacion_monto": m.std(ddof=1),
        "p95_monto": float(np.percentile(m, 95)),
        "p99_monto": float(np.percentile(m, 99)),
        "racha_media": (nl - largo_final.sum()) / rachas,
        "max_diario_temporada_medio": montos.max(axis=1).mean(),
    }, m, lindley_amax(montos)


def ks(obs, sim, rng, k=5000):
    s = rng.choice(sim, size=min(k, len(sim)), replace=False)
    d1 = stats.ks_2samp(obs, s)
    sr = np.round(s, 1)
    sr = sr[sr >= UMBRAL]  # lo que un pluviometro de 0,1 mm registraria como dia lluvioso
    d2 = stats.ks_2samp(obs, sr)
    return d1.statistic, d1.pvalue, d2.statistic, d2.pvalue


def ajustar_por_clave(x, claves, minimo=5):
    """Una gamma (Thom) por valor de la clave (mes o anio); las claves con pocos dias van juntas."""
    cal = CAL
    pesos, samplers, poco = [], [], []
    for c in np.unique(claves):
        xc = x[claves == c]
        if len(xc) < minimo:
            poco.append(xc)
            continue
        a, th = cal.estimar_gamma(list(xc))
        pesos.append(len(xc))
        samplers.append(gamma_sampler(a, th))
    if poco:
        xc = np.concatenate(poco)
        if len(xc) >= 2:
            a, th = cal.estimar_gamma(list(xc))
            pesos.append(len(xc))
            samplers.append(gamma_sampler(a, th))
    return mezcla_sampler(pesos, samplers), len(pesos)


CAL = cargar_calibrar()


def cargar_prueba_v6():
    """Funciones del criterio de V6 (tests/unit/test_estadistico.py): el diagnostico evalua cada
    candidato con la misma regla que la prueba, sin copiarla."""
    spec = importlib.util.spec_from_file_location("test_estadistico_v6", RAIZ / "tests" / "unit" / "test_estadistico.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


V6 = cargar_prueba_v6()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=20000, help="temporadas simuladas por grupo y candidato")
    ap.add_argument("--b-ks", type=int, default=199,
                    help="replicas del bootstrap parametrico de KS con el criterio de V6 (la prueba usa 999)")
    ap.add_argument("--salida", default=str(RAIZ / "results" / "validacion" / "diagnostico_v6.csv"))
    args = ap.parse_args()

    zonas = CAL.cargar_zonas()
    with PARAMETROS.open(newline="", encoding="utf-8") as f:
        grupos = list(csv.DictReader(f))

    filas = []
    for g in grupos:
        est, reg = g["estacion"], g["regimen"]
        p01, p11, a0, th0 = (float(g[k]) for k in ("p01", "p11", "alfa", "theta"))
        meses = CAL.meses_temporada_de(est, zonas.get(est, "costa_norte"))
        dias = sum(calendar.monthrange(2001, m)[1] for m in meses)
        obs, x, anio_m, mes_m, max_anio, amax_obs = leer_grupo(est, reg, meses)

        # ---- H1: consistencia con la calibracion ----
        assert len(x) == int(g["n_dias_lluvia"]), (est, reg, len(x), g["n_dias_lluvia"])
        a_t, th_t = CAL.estimar_gamma(list(x))
        assert abs(a_t - a0) < 1e-5 * max(1, a0) and abs(th_t - th0) < 1e-4 * max(1, th0), (est, reg)
        masa_bajo_umbral = stats.gamma.cdf(UMBRAL, a0, scale=th0)
        frac_01 = float(np.mean(np.isclose(x, 0.1)))
        resol = float(np.mean(np.isclose(x * 10, np.round(x * 10))))
        cv_obs = obs["desviacion_monto"] / obs["media_monto"]
        alfa_momentos = 1.0 / cv_obs ** 2

        # ---- H2: MLE exacta ----
        a_m, _, th_m = stats.gamma.fit(x, floc=0)
        ll_gamma = stats.gamma.logpdf(x, a_m, scale=th_m).sum()

        # ---- H3: forma ----
        (w, b1, b2), ll_mix = ajustar_mixexp(x)
        s_gpd, (u, xi, sig) = gamma_gpd(x, a0, th0)

        # ---- H4: heterogeneidad ----
        s_mes, k_mes = ajustar_por_clave(x, mes_m)
        s_anio, k_anio = ajustar_por_clave(x, anio_m)

        # Peso de los anios extremos en la cola observada
        orden = sorted(((float(x[anio_m == y].sum()), y) for y in np.unique(anio_m)), reverse=True)
        top = x >= np.percentile(x, 99)
        anios_p99 = sorted({int(y) for y in anio_m[top]})

        # ---- H5: escala aleatoria por temporada ----
        medias_anio = {y: x[anio_m == y].mean() for y in np.unique(anio_m)}
        a_z, _ = CAL.estimar_gamma(list(x / np.array([medias_anio[y] for y in anio_m])))
        kap_t, kap_z = kappa_escala(cv_obs, a0), kappa_escala(cv_obs, a_z)

        # ---- H6: gamma truncada en 0,1 mm (lo que registra el pluviometro) ----
        a_tr, th_tr, nll_tr = ajustar_gamma_truncada(x, a0, th0)
        _, cv_tr = momentos_gamma_truncada(a_tr, th_tr)
        kap_tr = kappa_desde_cv(cv_obs, cv_tr)

        candidatos = {  # nombre -> (muestreador de montos, kappa de la escala por temporada)
            "gamma_thom (actual)": (gamma_sampler(a0, th0), math.inf),
            "gamma_mle": (gamma_sampler(a_m, th_m), math.inf),
            "exp_mixta": (mezcla_sampler([w, 1 - w], [lambda r, k, b=b1: r.exponential(b, k),
                                                      lambda r, k, b=b2: r.exponential(b, k)]), math.inf),
            "gamma+gpd_q90": (s_gpd, math.inf),
            f"gamma_por_mes(k={k_mes})": (s_mes, math.inf),
            f"gamma_por_anio(k={k_anio})": (s_anio, math.inf),
            "escala_temporada": (gamma_sampler(a0, obs["media_monto"] / a0), kap_t),
            "escala_temporada_z": (gamma_sampler(a_z, obs["media_monto"] / a_z), kap_z),
            "gamma_truncada": (gamma_truncada_sampler(a_tr, th_tr), math.inf),
            "gamma_truncada+escala": (gamma_truncada_sampler(a_tr, th_tr), kap_tr),
        }
        # Criterio de la prueba V6 (tests/unit/test_estadistico.py): IC bootstrap por temporadas y KS de
        # montos registrados con p por bootstrap parametrico, Bonferroni por grupo.
        temporadas = V6.temporadas_observadas(est, reg, UMBRAL, meses)
        ic = V6.ic_bootstrap(temporadas, V6.ALFA_CONTRASTE)
        x_reg = V6.registrar(x)
        print(f"\n=== {est}/{reg} anios={len(max_anio)} n_lluvia={len(x)} D={dias} ===")
        print(f"H1 n_dias_lluvia y Thom reproducen parametros.csv: OK | resolucion 0,1 mm: {resol:.1%} | "
              f"fraccion = 0,1 mm: {frac_01:.1%} | P_gamma(X<0,1)={masa_bajo_umbral:.1%}")
        print(f"H2 alfa Thom={a0:.4f} MLE={a_m:.4f} momentos(1/CV^2)={alfa_momentos:.4f} | theta Thom={th0:.4f} MLE={th_m:.4f}")
        print(f"H3 exp_mixta w={w:.3f} b1={b1:.3f} b2={b2:.3f} | AIC gamma={2*2-2*ll_gamma:.1f} mixexp={2*3-2*ll_mix:.1f} | "
              f"GPD u={u:.2f} xi={xi:.3f} sigma={sig:.3f}")
        print(f"H4 anios con dias >= p99: {anios_p99} | 3 anios mas lluviosos (mm): "
              + ", ".join(f"{y}={s:.0f}" for s, y in orden[:3]) + f" de {sum(s for s, _ in orden):.0f}")
        print(f"H5 kappa escala_temporada={kap_t:.3f} | alfa_z={a_z:.4f} kappa escala_temporada_z={kap_z:.3f}")
        print(f"H6 gamma truncada en 0,1 mm: alfa={a_tr:.4f} theta={th_tr:.4f} | AIC={2*2+2*nll_tr:.1f} | "
              f"CV dentro={cv_tr:.3f} kappa={kap_tr:.3f}")
        print(f"   {'candidato':26s} " + " ".join(f"{k[:10]:>10s}" for k in ESTADISTICOS)
              + "   KS_p  KS_p(0,1mm)  n_fallos | criterio V6: est KS_D  KS_p  pasa")
        print(f"   {'observado':26s} " + " ".join(f"{obs[k]:10.4f}" for k in ESTADISTICOS)
              + "   P(Amax>U) U=" + "/".join(f"{u:.0f}" for u in UMBRALES_X6) + ": "
              + "/".join(f"{np.mean(amax_obs > u):.3f}" for u in UMBRALES_X6) + f" (n={len(amax_obs)} temporadas)")
        for nombre, (s, kap) in candidatos.items():
            rng = np.random.default_rng(SEMILLA)
            sim, m, amax_sim = simular(p01, p11, dias, s, args.n, rng, kappa=kap)
            riesgo = [float(np.mean(amax_sim > u)) for u in UMBRALES_X6]
            d1, p1, d2, p2 = ks(x, m, rng)
            errores = {k: (sim[k] - obs[k]) / obs[k] for k in ESTADISTICOS}
            fallos = sum(abs(e) > 0.10 for e in errores.values()) + int(p1 < 0.05)
            # criterio V6: 10 % o dentro del IC; KS registrado con nulo de len(temporadas) temporadas
            fallos_v6 = sum(not (abs(errores[k]) <= 0.10 or ic[k][0] <= sim[k] <= ic[k][1]) for k in ESTADISTICOS)
            ref = V6.registrar(m[:20000])
            d_v6 = stats.ks_2samp(x_reg, ref).statistic
            rng_ks = np.random.default_rng(SEMILLA + 1)
            mayores = 0
            for _ in range(args.b_ks):
                _, m_nulo, _ = simular(p01, p11, dias, s, len(temporadas), rng_ks, kappa=kap)
                nulo = V6.registrar(m_nulo)
                mayores += len(nulo) == 0 or stats.ks_2samp(nulo, ref).statistic >= d_v6
            p_v6 = (mayores + 1) / (args.b_ks + 1)
            pasa_v6 = fallos_v6 == 0 and p_v6 >= V6.ALFA_CONTRASTE
            print(f"   {nombre:26s} " + " ".join(f"{100*errores[k]:+9.1f}%" for k in ESTADISTICOS)
                  + f" {p1:7.1e} {p2:9.1e} {fallos:6d} | {fallos_v6:3d} {d_v6:.3f} {p_v6:6.3f} {'si' if pasa_v6 else 'no'}"
                  + "   P(Amax>U): " + "/".join(f"{r:.3f}" for r in riesgo))
            filas.append({"estacion": est, "regimen": reg, "candidato": nombre,
                          **{f"obs_{k}": round(obs[k], 5) for k in ESTADISTICOS},
                          **{f"sim_{k}": round(sim[k], 5) for k in ESTADISTICOS},
                          **{f"err_{k}": round(errores[k], 5) for k in ESTADISTICOS},
                          "ks_D": round(d1, 5), "ks_p": f"{p1:.3g}", "ks_D_01mm": round(d2, 5), "ks_p_01mm": f"{p2:.3g}",
                          "n_fallos": fallos, "alfa_thom": a0, "alfa_mle": round(a_m, 6),
                          "alfa_momentos": round(alfa_momentos, 6), "p_gamma_bajo_umbral": round(masa_bajo_umbral, 5),
                          "aic_gamma": round(2 * 2 - 2 * ll_gamma, 2), "aic_mixexp": round(2 * 3 - 2 * ll_mix, 2),
                          "gpd_xi": round(xi, 4),
                          "kappa": round(kap, 4) if math.isfinite(kap) else "inf",
                          "alfa_truncada": round(a_tr, 6), "theta_truncada": round(th_tr, 6),
                          "v6_fallos_estadisticos": fallos_v6, "v6_ks_D_registrado": round(d_v6, 5),
                          "v6_ks_p_bootstrap": round(p_v6, 5), "v6_pasa": int(pasa_v6),
                          **{f"obs_p_amax_gt_{u:.0f}": round(float(np.mean(amax_obs > u)), 5) for u in UMBRALES_X6},
                          **{f"sim_p_amax_gt_{u:.0f}": round(r, 5) for u, r in zip(UMBRALES_X6, riesgo)},
                          "n_temporadas_obs": len(amax_obs)})

    print("\n=== Resumen por candidato (16 grupos): grupos que pasan V6 completo | fallos por estadistico ===")
    for nombre in dict.fromkeys(f["candidato"].split("(k=")[0] for f in filas):
        sel = [f for f in filas if f["candidato"].split("(k=")[0] == nombre]
        por_est = {k: sum(abs(f[f"err_{k}"]) > 0.10 for f in sel) for k in ESTADISTICOS}
        ks_f = sum(float(f["ks_p"]) < 0.05 for f in sel)
        print(f"   {nombre:22s} pasan={sum(f['n_fallos'] == 0 for f in sel):2d}/{len(sel)} | "
              + " ".join(f"{k[:8]}={v}" for k, v in por_est.items()) + f" KS={ks_f}")

    print("\n=== Resumen con el criterio de la prueba V6 (IC bootstrap, KS registrado, Bonferroni) "
          "y error medio |P(Amax>U) simulado - observado| ===")
    for nombre in dict.fromkeys(f["candidato"].split("(k=")[0] for f in filas):
        sel = [f for f in filas if f["candidato"].split("(k=")[0] == nombre]
        est_ok = sum(f["v6_fallos_estadisticos"] == 0 for f in sel)
        ks_ok = sum(f["v6_ks_p_bootstrap"] >= V6.ALFA_CONTRASTE for f in sel)
        err = " ".join(f"U{u:.0f}={np.mean([abs(f[f'sim_p_amax_gt_{u:.0f}'] - f[f'obs_p_amax_gt_{u:.0f}']) for f in sel]):.3f}"
                       for u in UMBRALES_X6)
        print(f"   {nombre:22s} estadisticos={est_ok:2d}/{len(sel)} KS={ks_ok:2d}/{len(sel)} "
              f"ambos={sum(f['v6_pasa'] for f in sel):2d}/{len(sel)} | {err}")

    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    with salida.open("w", newline="", encoding="utf-8") as f:
        w_ = csv.DictWriter(f, fieldnames=list(filas[0]))
        w_.writeheader()
        w_.writerows(filas)
    print(f"\n{salida.relative_to(RAIZ)}: {len(filas)} filas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
