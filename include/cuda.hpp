// T38 | Responsable: Lita | Interfaz del backend CUDA (EXT1): un hilo por escenario en la GPU.
//
// El kernel llama a pp::hd::simular_escenario (include/nucleo_hd.hpp), el mismo código que usan los
// backends de CPU, con la misma clave y el mismo contador Philox {idx, día, sub}, incluido el sorteo
// de M de H5 en el día DIA_TEMPORADA. Esta cabecera no depende de CUDA: la incluye código C++ normal.
#pragma once

#include <cstdint>
#include <functional>
#include <string>
#include <vector>

#include "resultados.hpp"
#include "simulacion.hpp"

namespace pp {

// Escenarios por lanzamiento del kernel. Dos topes:
//   - LOTE_GPU = 2^20: los contadores de 32 bits por bloque de reduccion.cuh no pueden desbordar;
//   - ESCENARIOS_POR_HILO_LOTE por hilo de la grilla: con grillas chicas (p. ej. 2 × 128 hilos) un
//     lote de 2^20 serían ~4000 escenarios por hilo y varios segundos por lanzamiento; así cada
//     lanzamiento queda en décimas de segundo, lejos del watchdog TDR de Windows (≈ 2 s,
//     docs/inventario-gpu.md §3), y la GPU del escritorio no se congela.
constexpr uint64_t LOTE_GPU = 1u << 20;
constexpr uint64_t ESCENARIOS_POR_HILO_LOTE = 64;

// Escenarios por lanzamiento para una grilla de `bloques` × `hilos_por_bloque`.
inline uint64_t lote_gpu(int bloques, int hilos_por_bloque) {
    const uint64_t por_grilla = static_cast<uint64_t>(bloques) * static_cast<uint64_t>(hilos_por_bloque) *
                                ESCENARIOS_POR_HILO_LOTE;
    return por_grilla < LOTE_GPU ? por_grilla : LOTE_GPU;
}

// Ocupación teórica de una grilla (T40), calculada con la API de ocupación de CUDA. Los bloques se
// reparten entre SM; con menos bloques que SM, cada bloque ocupa un SM distinto y el resto queda ocioso.
struct OcupacionCuda {
    int sm = 0;                   // SM del dispositivo
    int registros_por_hilo = 0;   // del kernel compilado
    int bloques_por_sm_max = 0;   // bloques residentes por SM con estos hilos por bloque
    int hilos_por_sm_max = 0;     // límite del hardware (1536 en CC 8.9)
    int sm_usados = 0;            // min(bloques, SM)
    int bloques_por_sm = 0;       // bloques residentes en un SM usado durante la primera ola
    int olas = 0;                 // ceil(bloques / (SM × bloques_por_sm_max))
    double ocupacion_sm = 0.0;    // hilos residentes / hilos_por_sm_max en un SM usado
    double ocupacion_gpu = 0.0;   // ocupacion_sm × sm_usados / SM (fracción de la GPU con hilos residentes)
};
OcupacionCuda ocupacion_cuda(int bloques, int hilos_por_bloque);

// Ocupación OBSERVADA (T40) en un lanzamiento instrumentado del mismo kernel: cada bloque anota el SM
// donde corrió (%smid) y su inicio y fin (%globaltimer). Con eso se cuentan los SM distintos usados y
// el máximo de bloques que convivieron en un mismo SM. Sustituye a Nsight Compute, que en este equipo
// no puede leer los contadores de la GPU (ERR_NVGPUCTRPERM, requiere un ajuste de administrador).
struct OcupacionObservada {
    int sm_observados = 0;            // SM distintos donde corrió algún bloque
    int max_bloques_por_sm = 0;       // máximo de bloques simultáneos en un SM
    double media_bloques_por_sm = 0;  // media, sobre los SM usados, del máximo simultáneo de cada uno
    double ocupacion_observada = 0;   // media_bloques_por_sm × hilos_por_bloque / hilos_por_sm_max
    double ocupacion_gpu_observada = 0;  // ocupacion_observada × sm_observados / SM
};
OcupacionObservada observar_ocupacion(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                                      int hilos_por_bloque);

struct EjecucionCuda {
    Acumulador acc;
    int bloques = 0;           // bloques usados (resuelve bloques = 0)
    int hilos_por_bloque = 0;
    int lanzamientos = 0;      // lanzamientos del kernel (lotes de LOTE_GPU)
};

// Inicializa el contexto CUDA (fuera del tiempo medido). Lanza std::runtime_error si no hay GPU.
void inicializar_cuda();

// "gpu=<nombre>;cc=<x.y>;sm=<n>;cuda_rt=<x.y>;driver=<x.y>" del dispositivo 0.
std::string descripcion_gpu();

// Bloques que caben a la vez en la GPU (SM × bloques activos por SM) con `hilos_por_bloque`.
int bloques_residentes(int hilos_por_bloque);

// Máximo de hilos por bloque con que se puede lanzar el kernel en esta GPU (lo limitan los registros
// por hilo; con 94 registros en CC 8.9 queda por debajo de 1024) y registros por hilo del kernel.
int max_hilos_por_bloque();
int registros_por_hilo();

// Grilla fija y buffers de reducción reservados una sola vez. Lo usa el trabajador GPU de MPI (T41),
// que procesa cientos de bloques de la cola E2 sin volver a reservar memoria en cada uno.
class MotorCuda {
public:
    MotorCuda(int bloques, int hilos_por_bloque);  // bloques = 0: los que caben a la vez en la GPU
    ~MotorCuda();
    MotorCuda(const MotorCuda&) = delete;
    MotorCuda& operator=(const MotorCuda&) = delete;

    int bloques() const { return bloques_; }
    int hilos_por_bloque() const { return hilos_por_bloque_; }
    int lanzamientos() const { return lanzamientos_; }  // acumulados desde la construcción

    // Escenarios globales [base, base + n); `avance(hechos)` tras cada lote, si se pasa.
    Acumulador simular(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n,
                       const std::function<void(uint64_t)>& avance = {});

private:
    int bloques_ = 0;
    int hilos_por_bloque_ = 0;
    int lanzamientos_ = 0;
    unsigned long long* d_hist_ = nullptr;
    unsigned long long* d_k_ = nullptr;
};

// Simula los escenarios globales [base, base + n) en la GPU y devuelve k, n e histograma.
// `avance(hechos)` se llama tras cada lote, si se pasa (sala de control).
EjecucionCuda simular_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                           int hilos_por_bloque, const std::function<void(uint64_t)>& avance = {});

// Diagnóstico de V2: amax de cada escenario de [base, base + n) calculado en la GPU.
std::vector<double> amax_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n);

}  // namespace pp
