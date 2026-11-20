// T38 | Responsable: Lita | V2: equivalencia GPU frente a CPU (docs/decision-cuda.md).
//
// Para cada caso simula los mismos escenarios (misma clave, mismos índices globales) en la CPU con
// pp::simular_escenario y en la GPU con el kernel de pp_cuda, y exige:
//   - n y suma del histograma iguales a N en la GPU (V3);
//   - |k_gpu - k_cpu| / max(k_cpu, 1) <= 1e-6 (criterio V2 del contrato);
//   - el mismo resultado con grillas distintas (la reducción no depende de la grilla).
// Como diagnóstico, compara amax escenario por escenario en una muestra e informa cuántos coinciden
// bit a bit y la mayor diferencia relativa (log/cos/pow de la GPU pueden diferir en la última cifra).
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <exception>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>

#include "cuda.hpp"
#include "resultados.hpp"
#include "simulacion.hpp"

namespace {

struct Caso {
    std::string nombre;
    pp::Parametros p;
};

pp::Parametros parametros(double p01, double p11, double alfa, double theta, double kappa, double c, double u) {
    pp::Parametros p;
    p.p01 = p01; p.p11 = p11; p.alfa = alfa; p.theta = theta; p.kappa = kappa;
    p.capacidad = c; p.umbral = u; p.dias = 120;
    return p;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const uint64_t n = argc > 1 ? std::stoull(argv[1]) : 1000000ull;
        const uint64_t n_amax = std::min<uint64_t>(n, 200000ull);
        const double inf = std::numeric_limits<double>::infinity();
        const std::vector<Caso> casos = {
            {"sintetico_kappa_inf", parametros(0.15, 0.60, 0.70, 9.0, inf, 6.0, 50.0)},
            {"sintetico_kappa_2", parametros(0.15, 0.60, 0.70, 9.0, 2.0, 6.0, 50.0)},
            {"alfa_mayor_1_kappa_0.7", parametros(0.25, 0.55, 2.5, 4.0, 0.7, 10.0, 30.0)},
            {"tumbes_eltigre_normal", parametros(0.194444, 0.574331, 0.55639, 12.056491, 2.513917, 6.0, 50.0)},
        };
        const int grillas[][2] = {{0, 256}, {2, 128}, {16, 512}};
        const uint64_t semilla = 20261015, config_id = 3;
        const uint64_t clave = pp::derivar_clave(semilla, config_id);
        const uint64_t base = config_id * n;

        pp::inicializar_cuda();
        std::printf("[V2] %s n=%llu\n", pp::descripcion_gpu().c_str(), static_cast<unsigned long long>(n));
        bool ok = true;
        for (const Caso& c : casos) {
            pp::Acumulador cpu;
            for (uint64_t j = 0; j < n; ++j) cpu.agregar(pp::simular_escenario(c.p, clave, base + j));

            for (const auto& g : grillas) {
                const pp::EjecucionCuda gpu = pp::simular_cuda(c.p, clave, base, n, g[0], g[1]);
                uint64_t suma = 0, clases_distintas = 0;
                for (int i = 0; i < pp::NBINS; ++i) {
                    suma += gpu.acc.hist[static_cast<size_t>(i)];
                    clases_distintas += gpu.acc.hist[static_cast<size_t>(i)] != cpu.hist[static_cast<size_t>(i)];
                }
                const double dif = std::fabs(static_cast<double>(gpu.acc.k) - static_cast<double>(cpu.k)) /
                                   std::max(1.0, static_cast<double>(cpu.k));
                const bool pasa = gpu.acc.n == n && suma == n && dif <= 1e-6;
                ok = ok && pasa;
                std::printf("[V2] caso=%s grilla=%dx%d k_cpu=%llu k_gpu=%llu dif_rel=%.3g hist_igual=%s "
                            "clases_distintas=%llu suma_hist=%llu %s\n",
                            c.nombre.c_str(), gpu.bloques, gpu.hilos_por_bloque,
                            static_cast<unsigned long long>(cpu.k), static_cast<unsigned long long>(gpu.acc.k), dif,
                            gpu.acc == cpu ? "si" : "no", static_cast<unsigned long long>(clases_distintas),
                            static_cast<unsigned long long>(suma), pasa ? "OK" : "FALLA");
            }

            const std::vector<double> amax = pp::amax_cuda(c.p, clave, base, n_amax);
            uint64_t iguales = 0;
            double max_rel = 0.0;
            for (uint64_t j = 0; j < n_amax; ++j) {
                const double a = pp::simular_escenario(c.p, clave, base + j).amax;
                if (a == amax[j]) ++iguales;
                else max_rel = std::max(max_rel, std::fabs(a - amax[j]) / std::max(std::fabs(a), 1e-300));
            }
            std::printf("[V2] caso=%s amax_bit_a_bit=%llu/%llu max_dif_rel_amax=%.3g\n", c.nombre.c_str(),
                        static_cast<unsigned long long>(iguales), static_cast<unsigned long long>(n_amax), max_rel);
        }
        // Bordes de la reducción y de los lotes (T39): más hilos que escenarios, bloques sin trabajo,
        // 32 y el máximo de hilos por bloque y cortes de lote en LOTE_GPU + 1 y 1,5 LOTE_GPU. Igualdad exacta con la CPU.
        struct Borde { uint64_t n; int bloques; int hpb; };
        // El máximo de hilos por bloque lo fijan los registros del kernel (menos de 1024 en CC 8.9).
        const int hmax = pp::max_hilos_por_bloque();
        std::printf("[V2] registros_por_hilo=%d max_hilos_por_bloque=%d\n", pp::registros_por_hilo(), hmax);
        const Borde bordes[] = {{1, 0, 256}, {1000, 64, 32}, {777, 200, hmax}, {pp::LOTE_GPU + 1, 16, hmax},
                                {3 * pp::LOTE_GPU / 2, 0, 32}};
        const pp::Parametros pb = casos[1].p;
        for (const Borde& b : bordes) {
            pp::Acumulador cpu;
            for (uint64_t j = 0; j < b.n; ++j) cpu.agregar(pp::simular_escenario(pb, clave, base + j));
            const pp::EjecucionCuda gpu = pp::simular_cuda(pb, clave, base, b.n, b.bloques, b.hpb);
            const bool pasa = gpu.acc == cpu;
            ok = ok && pasa;
            std::printf("[V2] borde n=%llu grilla=%dx%d lanzamientos=%d k_cpu=%llu k_gpu=%llu hist_igual=%s %s\n",
                        static_cast<unsigned long long>(b.n), gpu.bloques, gpu.hilos_por_bloque, gpu.lanzamientos,
                        static_cast<unsigned long long>(cpu.k), static_cast<unsigned long long>(gpu.acc.k),
                        pasa ? "si" : "no", pasa ? "OK" : "FALLA");
        }
        // Pedir más hilos por bloque de los que admite el kernel debe dar un error claro, no un fallo de lanzamiento.
        if (hmax < 1024) {
            bool error_claro = false;
            try {
                pp::simular_cuda(pb, clave, base, 1000, 0, 1024);
            } catch (const std::runtime_error& e) {
                error_claro = std::string(e.what()).find("hilos_por_bloque=1024") != std::string::npos;
            }
            ok = ok && error_claro;
            std::printf("[V2] hilos_por_bloque=1024 rechazado con mensaje claro: %s\n", error_claro ? "OK" : "FALLA");
        }
        std::printf("[V2] estado=%s\n", ok ? "OK" : "FALLA");
        return ok ? 0 : 3;
    } catch (const std::exception& e) {
        std::fprintf(stderr, "error: %s\n", e.what());
        return 2;
    }
}
