// T11/T38 | Responsables: Ashley (núcleo) y Lita (CUDA) | Núcleo del escenario compartido por CPU y GPU.
//
// Las funciones de un escenario (Philox, Markov, gamma, escala por temporada H5, Lindley y clase del
// histograma) están aquí una sola vez, como funciones inline __host__ __device__. Los backends de CPU
// las llaman a través de src/core (mismas firmas públicas de simulacion.hpp) y el kernel CUDA las
// llama directamente, así que la GPU sigue exactamente el mismo algoritmo y el mismo contador Philox.
//
// Dentro de pp::hd las llamadas van calificadas (hd::) para que la búsqueda por argumento (ADL) no
// las confunda con las funciones homónimas de pp::.
//
// Reglas para no cambiar resultados:
// - El orden de las operaciones es el que tenía src/core antes de T38 (V1 sigue bit a bit en CPU).
// - std::max(0.0, x) se escribe como (0.0 < x) ? x : 0.0, que es su definición exacta.
// - Se compila sin contracción FMA: -ffp-contract=off en CPU y -fmad=false en CUDA (contrato V2).
// - En la GPU, log/cos/pow pueden diferir de glibc en la última cifra binaria; por eso V2 compara el
//   conteo con tolerancia relativa 1e-6 y no bit a bit (docs/decision-cuda.md).
#pragma once

#include <float.h>
#include <math.h>
#include <stdint.h>

#include "simulacion.hpp"

#if defined(__CUDACC__)
#define PP_HD __host__ __device__ inline
#else
#define PP_HD inline
#endif

namespace pp {
namespace hd {

// ---- Philox4x32-10 (Salmon et al., 2011) ----
constexpr uint32_t PHILOX_M0 = 0xD2511F53u;
constexpr uint32_t PHILOX_M1 = 0xCD9E8D57u;
constexpr uint32_t PHILOX_W0 = 0x9E3779B9u;  // parte dorada
constexpr uint32_t PHILOX_W1 = 0xBB67AE85u;  // sqrt(3) - 1

PP_HD void mulhilo32(uint32_t a, uint32_t b, uint32_t& hi, uint32_t& lo) {
    const uint64_t p = static_cast<uint64_t>(a) * static_cast<uint64_t>(b);
    hi = static_cast<uint32_t>(p >> 32);
    lo = static_cast<uint32_t>(p);
}

PP_HD Bloque4 philox4x32_10(Bloque4 c, uint32_t k0, uint32_t k1) {
    for (int ronda = 0; ronda < 10; ++ronda) {
        uint32_t hi0, lo0, hi1, lo1;
        hd::mulhilo32(PHILOX_M0, c.v[0], hi0, lo0);
        hd::mulhilo32(PHILOX_M1, c.v[2], hi1, lo1);
        const Bloque4 s = {{hi1 ^ c.v[1] ^ k0, lo1, hi0 ^ c.v[3] ^ k1, lo0}};
        c = s;
        k0 += PHILOX_W0;
        k1 += PHILOX_W1;
    }
    return c;
}

// Uniforme en (0,1) a partir de una palabra de 32 bits (nunca 0 ni 1).
PP_HD double uniforme32(uint32_t w) {
    return (static_cast<double>(w) + 0.5) * (1.0 / 4294967296.0);
}

// Contador = {idx_bajo, idx_alto, día, sub}; clave = 64 bits derivados de (semilla, config).
PP_HD Bloque4 bloque(uint64_t clave, uint64_t idx, uint32_t dia, uint32_t sub) {
    const Bloque4 ctr = {{static_cast<uint32_t>(idx), static_cast<uint32_t>(idx >> 32), dia, sub}};
    return hd::philox4x32_10(ctr, static_cast<uint32_t>(clave), static_cast<uint32_t>(clave >> 32));
}

// ---- Modelo de lluvia (Markov de dos estados + gamma, Marsaglia–Tsang) ----
constexpr double DOS_PI = 6.283185307179586476925286766559;
constexpr int MAX_INTENTOS = 10000;  // salvaguarda; la aceptación de Marsaglia–Tsang es > 95 %

// Gamma(forma, escala) con Marsaglia–Tsang sobre el contador {idx, dia, 1 + intento}.
PP_HD double gamma_contador(double forma, double escala, uint64_t clave, uint64_t idx, uint32_t dia) {
    // gamma(a) con a < 1: gamma(a + 1) * U^(1/a). U sale de la 4.ª palabra del primer intento
    // (independiente de las palabras que deciden la aceptación).
    const bool potenciar = forma < 1.0;
    const double a = potenciar ? forma + 1.0 : forma;
    const double d = a - 1.0 / 3.0;
    const double c = 1.0 / sqrt(9.0 * d);

    double factor = 1.0;
    for (int intento = 0; intento < MAX_INTENTOS; ++intento) {
        const Bloque4 b = hd::bloque(clave, idx, dia, 1u + static_cast<uint32_t>(intento));
        if (intento == 0 && potenciar) factor = pow(hd::uniforme32(b.v[3]), 1.0 / forma);

        const double u1 = hd::uniforme32(b.v[0]);
        const double u2 = hd::uniforme32(b.v[1]);
        const double x = sqrt(-2.0 * log(u1)) * cos(DOS_PI * u2);  // N(0,1), Box–Muller
        double v = 1.0 + c * x;
        if (v <= 0.0) continue;
        v = v * v * v;
        const double u = hd::uniforme32(b.v[2]);
        if (log(u) < 0.5 * x * x + d - d * v + d * log(v)) {
            // Si potenciar y el primer intento fue rechazado, `factor` ya se fijó en el intento 0.
            return d * v * escala * factor;
        }
    }
    return d * escala * factor;  // inalcanzable en la práctica
}

PP_HD bool ocurre_lluvia(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia, bool llovio_ayer) {
    const Bloque4 b = hd::bloque(clave, idx, dia, 0);
    const double u = hd::uniforme32(b.v[0]);
    return u < (llovio_ayer ? p.p11 : p.p01);
}

PP_HD double monto_gamma(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia) {
    return hd::gamma_contador(p.alfa, p.theta, clave, idx, dia);
}

// H5: factor de intensidad de la temporada; 1.0 sin consumir números aleatorios si kappa no es finito.
PP_HD double factor_temporada(const Parametros& p, uint64_t clave, uint64_t idx) {
    if (!(fabs(p.kappa) <= DBL_MAX)) return 1.0;  // equivale a !std::isfinite(kappa)
    return hd::gamma_contador(p.kappa, 1.0 / p.kappa, clave, idx, DIA_TEMPORADA);
}

// ---- Balance hídrico (recursión de Lindley) ----
PP_HD double actualizar_acumulado(double acumulado, double lluvia, double capacidad) {
    const double x = acumulado + lluvia - capacidad;
    return (0.0 < x) ? x : 0.0;  // std::max(0.0, x)
}

PP_HD Resultado simular_escenario(const Parametros& p, uint64_t clave, uint64_t idx) {
    double a = 0.0;
    double amax = 0.0;
    bool lluvioso = false;  // el día previo a la temporada se toma como seco
    // H5: intensidad de la temporada, sorteada una vez. Vale exactamente 1.0 con kappa infinito, y
    // x * 1.0 == x en punto flotante, así que el modelo sin H5 no cambia ni un bit.
    const double m = hd::factor_temporada(p, clave, idx);
    for (int d = 0; d < p.dias; ++d) {
        const uint32_t dia = static_cast<uint32_t>(d);
        lluvioso = hd::ocurre_lluvia(p, clave, idx, dia, lluvioso);
        const double r = lluvioso ? hd::monto_gamma(p, clave, idx, dia) * m : 0.0;
        a = hd::actualizar_acumulado(a, r, p.capacidad);
        amax = (amax < a) ? a : amax;  // std::max(amax, a)
    }
    Resultado res;
    res.inundacion = amax > p.umbral;
    res.amax = amax;
    return res;
}

// Clase del histograma: floor(amax) en mm; todo valor >= 511 mm cae en la clase 511.
PP_HD int clase_histograma(double amax) {
    if (!(amax > 0.0)) return 0;  // 0, negativos y NaN
    const double f = floor(amax);
    return f >= static_cast<double>(NBINS - 1) ? NBINS - 1 : static_cast<int>(f);
}

}  // namespace hd
}  // namespace pp
