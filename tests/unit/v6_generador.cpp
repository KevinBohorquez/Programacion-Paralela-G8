// T13 | Responsable: Lita | Auxiliar de V6: estadísticos de la lluvia diaria que produce el núcleo.
//
// Recorre N temporadas con las mismas funciones que simular_escenario (ocurre_lluvia y monto_gamma,
// clave = derivar_clave(semilla, config_id), índice global c*N + j) y escribe en stdout líneas
// "clave=valor" que lee tests/unit/test_estadistico.py. Acepta las banderas de los demás ejecutables.
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <iostream>
#include <vector>

#include "resultados.hpp"
#include "simulacion.hpp"

namespace {
constexpr double ANCHO_CLASE = 0.01;      // mm: resolución de los percentiles
constexpr size_t CLASES = 400000;         // hasta 4000 mm; el resto cae en la última clase
constexpr size_t MUESTRA_KS = 5000;       // primeros montos (i.i.d. gamma) para Kolmogorov–Smirnov

double percentil(const std::vector<uint64_t>& h, uint64_t total, double q) {
    const double objetivo = q * static_cast<double>(total);
    uint64_t acumulado = 0;
    for (size_t b = 0; b < h.size(); ++b) {
        if (static_cast<double>(acumulado + h[b]) >= objetivo) {
            const double fraccion = h[b] ? (objetivo - static_cast<double>(acumulado)) / static_cast<double>(h[b]) : 0.0;
            return (static_cast<double>(b) + fraccion) * ANCHO_CLASE;
        }
        acumulado += h[b];
    }
    return static_cast<double>(h.size()) * ANCHO_CLASE;
}
}  // namespace

int main(int argc, char** argv) {
    try {
        pp::Configuracion cfg;
        if (!pp::parsear_argumentos(argc, argv, cfg)) return 0;
        const pp::Parametros& p = cfg.params;
        const uint64_t clave = pp::derivar_clave(cfg.semilla, cfg.config_id);
        const uint64_t base = cfg.config_id * cfg.n;

        uint64_t dias = 0, lluviosos = 0, rachas = 0, dias_en_rachas = 0;
        double suma = 0.0, suma2 = 0.0, suma_max_temporada = 0.0;
        std::vector<uint64_t> hist(CLASES, 0);
        std::vector<double> muestra;
        muestra.reserve(MUESTRA_KS);

        for (uint64_t j = 0; j < cfg.n; ++j) {
            bool lluvioso = false;  // igual que simular_escenario: el día previo se toma como seco
            uint64_t racha = 0;
            double max_temporada = 0.0;
            for (int d = 0; d < p.dias; ++d) {
                const uint32_t dia = static_cast<uint32_t>(d);
                lluvioso = pp::ocurre_lluvia(p, clave, base + j, dia, lluvioso);
                ++dias;
                if (lluvioso) {
                    const double r = pp::monto_gamma(p, clave, base + j, dia);
                    ++lluviosos;
                    ++racha;
                    suma += r;
                    suma2 += r * r;
                    max_temporada = std::max(max_temporada, r);
                    hist[std::min(static_cast<size_t>(r / ANCHO_CLASE), CLASES - 1)] += 1;
                    if (muestra.size() < MUESTRA_KS) muestra.push_back(r);
                } else if (racha > 0) {  // solo rachas cerradas por un día seco: su longitud es geométrica
                    ++rachas;
                    dias_en_rachas += racha;
                    racha = 0;
                }
            }
            suma_max_temporada += max_temporada;
        }

        const double nl = static_cast<double>(lluviosos);
        const double media = lluviosos ? suma / nl : 0.0;
        const double varianza = lluviosos > 1 ? (suma2 - nl * media * media) / (nl - 1.0) : 0.0;
        std::printf("n=%llu\ndias=%llu\nlluviosos=%llu\n", static_cast<unsigned long long>(cfg.n),
                    static_cast<unsigned long long>(dias), static_cast<unsigned long long>(lluviosos));
        std::printf("frecuencia_lluvia=%.17g\n", static_cast<double>(lluviosos) / static_cast<double>(dias));
        std::printf("media_monto=%.17g\ndesviacion_monto=%.17g\n", media, std::sqrt(std::max(0.0, varianza)));
        std::printf("p95_monto=%.17g\np99_monto=%.17g\n", percentil(hist, lluviosos, 0.95), percentil(hist, lluviosos, 0.99));
        std::printf("rachas_cerradas=%llu\nracha_media=%.17g\n", static_cast<unsigned long long>(rachas),
                    rachas ? static_cast<double>(dias_en_rachas) / static_cast<double>(rachas) : 0.0);
        std::printf("max_diario_temporada_medio=%.17g\n", suma_max_temporada / static_cast<double>(cfg.n));
        std::printf("muestra=");
        for (size_t i = 0; i < muestra.size(); ++i) std::printf(i ? ";%.17g" : "%.17g", muestra[i]);
        std::printf("\n");
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 2;
    }
}
