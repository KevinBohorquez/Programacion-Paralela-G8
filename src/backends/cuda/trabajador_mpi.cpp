// T41 | Responsable: Lita (revisión: R1) | EXT2: la GPU como trabajador MPI del esquema dinámico E2.
//
// pp_mpi_dinamico_gpu es pp_mpi_dinamico con un cambio: el ÚLTIMO rango (si hay al menos dos procesos)
// procesa cada bloque WORK [i0, i1) en la GPU, con un lanzamiento del kernel de EXT1 por bloque
// (pp::MotorCuda: grilla fija y buffers reservados una vez). El maestro (rango 0), los mensajes
// REQ/WORK/STOP y los demás trabajadores de CPU no cambian. Como la cola es dinámica, la GPU pide
// bloques a su propio ritmo y el reparto se ajusta solo a la diferencia de velocidad CPU/GPU.
//
// Equivalencia: el kernel usa el mismo núcleo y el mismo contador Philox que la CPU (include/nucleo_hd.hpp),
// y la GPU da el mismo k y el mismo histograma (V2), así que --verificar (V1, bit a bit frente a la
// referencia secuencial) y las comprobaciones de V3 de ejecutar_mpi siguen valiendo con la GPU.
//
// El trabajador GPU espera al kernel con cudaDeviceScheduleBlockingSync: su hilo duerme y deja libre
// el núcleo de CPU mientras la GPU calcula. La grilla se elige con --bloques y --hilos-por-bloque.
//
// El contexto CUDA (≈ décimas de segundo) se crea ANTES de MPI_Init, fuera del tiempo medido, como en
// cualquier aplicación MPI + GPU: el rango se lee de las variables del lanzador (Open MPI o PMI). Si
// no están, se crea dentro del esquema y su costo queda dentro del tiempo (se avisa en stderr).
#include <chrono>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <memory>
#include <string>

#include "cuda.hpp"
#include "mpi_dinamico.hpp"
#include "simulacion.hpp"

namespace {

bool contexto_previo = false;  // el contexto CUDA ya se creó en main, antes de MPI_Init
double t_contexto_s = 0.0;

int entero_entorno(const char* a, const char* b) {
    for (const char* nombre : {a, b}) {
        const char* v = std::getenv(nombre);
        if (v && *v) return std::atoi(v);
    }
    return -1;
}

mpi_pi::ResumenRango esquema_cpu_gpu(MPI_Comm comm, const pp::Configuracion& cfg,
                                     const mpi_pi::FuncionEscenario& escenario, pp::Acumulador& local) {
    int rango = 0, procesos = 1;
    MPI_Comm_rank(comm, &rango);
    MPI_Comm_size(comm, &procesos);

    const bool es_gpu = procesos >= 2 && rango == procesos - 1;
    std::unique_ptr<pp::MotorCuda> motor;
    mpi_pi::FuncionBloque bloque;
    if (es_gpu) {
        if (!contexto_previo) {
            std::cerr << "aviso: rango GPU sin variables del lanzador; el contexto CUDA entra en el tiempo medido\n";
            pp::inicializar_cuda(/*espera_bloqueante=*/true);
        }
        motor = std::make_unique<pp::MotorCuda>(cfg.bloques, cfg.hilos_por_bloque);
        const pp::Parametros params = cfg.params;
        const std::uint64_t clave = pp::derivar_clave(cfg.semilla, cfg.config_id);
        const std::uint64_t base = cfg.config_id * cfg.n;  // índice global i = c*N + j
        pp::MotorCuda* m = motor.get();
        bloque = [m, params, clave, base](std::uint64_t i0, std::uint64_t i1, pp::Acumulador& acc) {
            acc.combinar(m->simular(params, clave, base + i0, i1 - i0));
        };
    } else {
        bloque = [&escenario](std::uint64_t i0, std::uint64_t i1, pp::Acumulador& acc) {
            for (std::uint64_t i = i0; i < i1; ++i) escenario(i, acc);
        };
    }
    mpi_pi::ResumenRango res = mpi_pi::esquema_dinamico_bloques(comm, cfg, bloque, local);
    if (es_gpu && !cfg.silencioso)
        std::cerr << "[gpu] rango=" << rango << " bloques_cola=" << res.bloques << " n_local=" << res.n_local
                  << " grilla=" << motor->bloques() << "x" << motor->hilos_por_bloque()
                  << " lanzamientos=" << motor->lanzamientos() << " t_contexto_s=" << t_contexto_s
                  << " contexto_fuera_del_tiempo=" << (contexto_previo ? 1 : 0) << " " << pp::descripcion_gpu() << "\n";
    return res;
}

}  // namespace

int main(int argc, char** argv) {
    const int rango = entero_entorno("OMPI_COMM_WORLD_RANK", "PMI_RANK");
    const int procesos = entero_entorno("OMPI_COMM_WORLD_SIZE", "PMI_SIZE");
    if (procesos >= 2 && rango == procesos - 1) {
        const auto t0 = std::chrono::steady_clock::now();
        try {
            pp::inicializar_cuda(/*espera_bloqueante=*/true);
        } catch (const std::exception& e) {
            std::cerr << "error: rango " << rango << ": " << e.what() << "\n";
            return 2;
        }
        t_contexto_s = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        contexto_previo = true;
    }
    return mpi_pi::ejecutar_mpi(argc, argv, "mpi_dinamico_gpu", esquema_cpu_gpu);
}
