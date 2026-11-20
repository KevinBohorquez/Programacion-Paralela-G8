// T11 | Responsable: Ashley | Ocurrencia Markov y monto gamma (Marsaglia–Tsang). · H5: factor de intensidad por temporada (Lita).
#include <cmath>

#include "simulacion.hpp"

namespace pp {

namespace {
constexpr double DOS_PI = 6.283185307179586476925286766559;
constexpr int MAX_INTENTOS = 10000;  // salvaguarda; la aceptación de Marsaglia–Tsang es > 95 %

// Contador = {idx_bajo, idx_alto, día, sub}; clave = 64 bits derivados de (semilla, config).
inline Bloque4 bloque(uint64_t clave, uint64_t idx, uint32_t dia, uint32_t sub) {
    const Bloque4 ctr = {{static_cast<uint32_t>(idx), static_cast<uint32_t>(idx >> 32), dia, sub}};
    return philox4x32_10(ctr, static_cast<uint32_t>(clave), static_cast<uint32_t>(clave >> 32));
}

// Gamma(forma, escala) con Marsaglia–Tsang sobre el contador {idx, dia, 1 + intento}. Mismo algoritmo y
// mismo orden de operaciones que tenía monto_gamma, para conservar los resultados bit a bit.
double gamma_contador(double forma, double escala, uint64_t clave, uint64_t idx, uint32_t dia) {
    // gamma(a) con a < 1: gamma(a + 1) * U^(1/a). U sale de la 4.ª palabra del primer intento
    // (independiente de las palabras que deciden la aceptación).
    const bool potenciar = forma < 1.0;
    const double a = potenciar ? forma + 1.0 : forma;
    const double d = a - 1.0 / 3.0;
    const double c = 1.0 / std::sqrt(9.0 * d);

    double factor = 1.0;
    for (int intento = 0; intento < MAX_INTENTOS; ++intento) {
        const Bloque4 b = bloque(clave, idx, dia, 1u + static_cast<uint32_t>(intento));
        if (intento == 0 && potenciar) factor = std::pow(uniforme32(b.v[3]), 1.0 / forma);

        const double u1 = uniforme32(b.v[0]);
        const double u2 = uniforme32(b.v[1]);
        const double x = std::sqrt(-2.0 * std::log(u1)) * std::cos(DOS_PI * u2);  // N(0,1), Box–Muller
        double v = 1.0 + c * x;
        if (v <= 0.0) continue;
        v = v * v * v;
        const double u = uniforme32(b.v[2]);
        if (std::log(u) < 0.5 * x * x + d - d * v + d * std::log(v)) {
            // Si potenciar y el primer intento fue rechazado, `factor` ya se fijó en el intento 0.
            return d * v * escala * factor;
        }
    }
    return d * escala * factor;  // inalcanzable en la práctica
}
}  // namespace

bool ocurre_lluvia(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia, bool llovio_ayer) {
    const Bloque4 b = bloque(clave, idx, dia, 0);
    const double u = uniforme32(b.v[0]);
    return u < (llovio_ayer ? p.p11 : p.p01);
}

double monto_gamma(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia) {
    return gamma_contador(p.alfa, p.theta, clave, idx, dia);
}

double factor_temporada(const Parametros& p, uint64_t clave, uint64_t idx) {
    if (!std::isfinite(p.kappa)) return 1.0;  // H5 desactivada: no consume números aleatorios
    return gamma_contador(p.kappa, 1.0 / p.kappa, clave, idx, DIA_TEMPORADA);
}

}  // namespace pp
