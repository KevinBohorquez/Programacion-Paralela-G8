// T15 | Responsable: Ashley | Backend OpenMP como biblioteca: escenarios con índice global estable y reducción de k, n e histograma.
#include <omp.h>

#include <cstdlib>
#include <stdexcept>

#include "openmp.hpp"
#include "progreso.hpp"

namespace pp {

namespace {

// "static" | "dynamic" | "guided" con chunk opcional ("dynamic:64" o "dynamic,64").
// En el CSV se escribe con ':' porque el CSV no usa comillas.
void aplicar_schedule(const std::string& texto) {
    std::string tipo = texto;
    int chunk = 0;
    const size_t coma = texto.find_first_of(",:");
    if (coma != std::string::npos) {
        tipo = texto.substr(0, coma);
        chunk = std::atoi(texto.c_str() + coma + 1);
        if (chunk < 0) throw std::runtime_error("chunk de schedule inválido: " + texto);
    }
    omp_sched_t kind;
    if (tipo == "static") kind = omp_sched_static;
    else if (tipo == "dynamic") kind = omp_sched_dynamic;
    else if (tipo == "guided") kind = omp_sched_guided;
    else throw std::runtime_error("schedule desconocido: '" + texto + "' (use static|dynamic|guided[,chunk])");
    omp_set_schedule(kind, chunk);
}

}  // namespace

std::string schedule_actual() {
    omp_sched_t kind;
    int chunk;
    omp_get_schedule(&kind, &chunk);
    const int base = static_cast<int>(kind) & 0x7fffffff;  // el bit alto es "monotonic" (OpenMP 5)
    std::string s = base == omp_sched_static ? "static" : base == omp_sched_dynamic ? "dynamic"
                  : base == omp_sched_guided ? "guided" : "auto";
    if (chunk > 0) s += ":" + std::to_string(chunk);
    return s;
}

int hilos_efectivos() {  // tamaño real del equipo (puede ser menor que lo pedido)
    int t = 1;
#pragma omp parallel
    {
#pragma omp single
        t = omp_get_num_threads();
    }
    return t;
}

Acumulador ejecutar_openmp(const Parametros& p, uint64_t clave, uint64_t config_id, uint64_t n_total,
                           uint64_t j0, uint64_t j1, int hilos, const std::string& schedule) {
    if (hilos > 0) omp_set_num_threads(hilos);
    if (!schedule.empty()) aplicar_schedule(schedule);

    const uint64_t base = config_id * n_total;  // índice global i = c*N + j (no depende de hilo alguno)
    uint64_t k = 0, n = 0;
    uint64_t hist[NBINS] = {0};

    // Cada hilo recibe copias privadas de k, n y de UN histograma de 512 clases (4 KB);
    // OpenMP las suma al cerrar la región. No hay escrituras compartidas en el bucle.
    if (!progreso_activo()) {
#pragma omp parallel for schedule(runtime) reduction(+ : k, n) reduction(+ : hist[:NBINS])
        for (uint64_t j = j0; j < j1; ++j) {
            const Resultado r = simular_escenario(p, clave, base + j);
            k += r.inundacion ? 1u : 0u;
            n += 1u;
            hist[clase_histograma(r.amax)] += 1u;
        }
    } else {
        // Mismo reparto y misma reducción; cada hilo suma al contador atómico cada PASO_PROGRESO escenarios.
        Progreso prog(j1 - j0, rango_progreso());
#pragma omp parallel reduction(+ : k, n) reduction(+ : hist[:NBINS])
        {
            uint64_t pendiente = 0;
#pragma omp for schedule(runtime)
            for (uint64_t j = j0; j < j1; ++j) {
                const Resultado r = simular_escenario(p, clave, base + j);
                k += r.inundacion ? 1u : 0u;
                n += 1u;
                hist[clase_histograma(r.amax)] += 1u;
                if (++pendiente == PASO_PROGRESO) {
                    prog.sumar(pendiente);
                    pendiente = 0;
                }
            }
            if (pendiente > 0) prog.sumar(pendiente);
        }
        prog.terminar();
    }

    Acumulador acc;  // fuera de la región paralela: un solo hilo
    acc.k = k;
    acc.n = n;
    for (int b = 0; b < NBINS; ++b) acc.hist[static_cast<size_t>(b)] = hist[b];
    return acc;
}

}  // namespace pp
