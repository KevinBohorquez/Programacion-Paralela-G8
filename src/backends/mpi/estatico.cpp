// T19 | Responsable: David | Reparto MPI estático (E1) y reducción.
#include "mpi_estatico.hpp"

#include <algorithm>

#include "progreso.hpp"

namespace mpi_pi {

std::pair<std::uint64_t, std::uint64_t> intervalo_estatico(std::uint64_t n, int rango, int procesos) {
    const std::uint64_t p = static_cast<std::uint64_t>(procesos);
    const std::uint64_t r = static_cast<std::uint64_t>(rango);
    const std::uint64_t base = n / p;
    const std::uint64_t resto = n % p;
    const std::uint64_t inicio = r * base + (r < resto ? r : resto);
    const std::uint64_t cuenta = base + (r < resto ? 1 : 0);
    return {inicio, inicio + cuenta};
}

ResumenRango esquema_estatico(MPI_Comm comm, const pp::Configuracion& cfg, const FuncionEscenario& escenario, pp::Acumulador& local) {
    int rango = 0, procesos = 1;
    MPI_Comm_rank(comm, &rango);
    MPI_Comm_size(comm, &procesos);

    const auto [inicio, fin] = intervalo_estatico(cfg.n, rango, procesos);
    if (!pp::progreso_activo()) {
        for (std::uint64_t i = inicio; i < fin; ++i) escenario(i, local);
    } else {  // mismo tramo, recorrido por bloques de PASO_PROGRESO para informar el avance del rango
        pp::Progreso prog(fin - inicio, rango);
        for (std::uint64_t b0 = inicio; b0 < fin; b0 += pp::PASO_PROGRESO) {
            const std::uint64_t b1 = std::min(fin, b0 + pp::PASO_PROGRESO);
            for (std::uint64_t i = b0; i < b1; ++i) escenario(i, local);
            prog.sumar(b1 - b0);
        }
        prog.terminar();
    }

    ResumenRango res;
    res.inicio = inicio;
    res.fin = fin;
    res.bloques = fin > inicio ? 1 : 0;
    res.n_local = local.n;
    return res;
}

}  // namespace mpi_pi
