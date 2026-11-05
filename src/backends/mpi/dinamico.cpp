// T20 | Responsable: David | Protocolo REQ, WORK y STOP (E2, maestro-trabajador dinámico).
#include "mpi_dinamico.hpp"

#include <algorithm>
#include <vector>

#include "progreso.hpp"

namespace mpi_pi {

namespace {

// Rango [i0, i1) asignado a un trabajador, anotado por el maestro para comprobar la cobertura.
struct Asignacion {
    std::uint64_t i0;
    std::uint64_t i1;
};

// Los rangos asignados deben cubrir [0, N) sin solape ni huecos.
bool cobertura_exacta(std::vector<Asignacion>& a, std::uint64_t n) {
    std::sort(a.begin(), a.end(), [](const Asignacion& x, const Asignacion& y) { return x.i0 < y.i0; });
    std::uint64_t esperado = 0;
    for (const auto& r : a) {
        if (r.i0 != esperado || r.i1 <= r.i0) return false;
        esperado = r.i1;
    }
    return esperado == n;
}

ResumenRango maestro(MPI_Comm comm, int procesos, const pp::Configuracion& cfg) {
    ResumenRango res;
    std::vector<Asignacion> asignadas;
    std::uint64_t siguiente = 0;
    int activos = procesos - 1;

    while (activos > 0) {
        std::uint64_t basura = 0;
        MPI_Status st;
        MPI_Recv(&basura, 1, MPI_UINT64_T, MPI_ANY_SOURCE, ETIQUETA_REQ, comm, &st);
        if (siguiente < cfg.n) {
            const std::uint64_t i1 = std::min(cfg.n, siguiente + cfg.lote);
            const std::uint64_t rango[2] = {siguiente, i1};
            MPI_Send(rango, 2, MPI_UINT64_T, st.MPI_SOURCE, ETIQUETA_WORK, comm);
            if (pp::progreso_activo()) pp::reportar_bloque(st.MPI_SOURCE, siguiente, i1);
            asignadas.push_back({siguiente, i1});
            siguiente = i1;
        } else {
            const std::uint64_t vacio[2] = {0, 0};
            MPI_Send(vacio, 2, MPI_UINT64_T, st.MPI_SOURCE, ETIQUETA_STOP, comm);
            --activos;  // un STOP por trabajador
        }
    }
    res.bloques = asignadas.size();
    res.coherente = cobertura_exacta(asignadas, cfg.n);
    return res;
}

ResumenRango trabajador(MPI_Comm comm, const FuncionEscenario& escenario, pp::Acumulador& local) {
    ResumenRango res;
    for (;;) {
        const std::uint64_t pedido = 0;
        MPI_Send(&pedido, 1, MPI_UINT64_T, 0, ETIQUETA_REQ, comm);
        std::uint64_t rango[2] = {0, 0};
        MPI_Status st;
        MPI_Recv(rango, 2, MPI_UINT64_T, 0, MPI_ANY_TAG, comm, &st);
        if (st.MPI_TAG == ETIQUETA_STOP) break;
        for (std::uint64_t i = rango[0]; i < rango[1]; ++i) escenario(i, local);
        ++res.bloques;
    }
    return res;
}

}  // namespace

ResumenRango esquema_dinamico(MPI_Comm comm, const pp::Configuracion& cfg, const FuncionEscenario& escenario, pp::Acumulador& local) {
    int rango = 0, procesos = 1;
    MPI_Comm_rank(comm, &rango);
    MPI_Comm_size(comm, &procesos);

    ResumenRango res;
    if (procesos == 1) {  // sin trabajadores, el rango 0 procesa todo
        if (pp::progreso_activo()) pp::reportar_bloque(0, 0, cfg.n);
        for (std::uint64_t i = 0; i < cfg.n; ++i) escenario(i, local);
        res.bloques = 1;
    } else if (rango == 0) {
        res = maestro(comm, procesos, cfg);
    } else {
        res = trabajador(comm, escenario, local);
    }
    res.n_local = local.n;
    return res;
}

}  // namespace mpi_pi
