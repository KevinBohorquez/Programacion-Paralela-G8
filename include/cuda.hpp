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

// Escenarios por lanzamiento del kernel: acota cada lanzamiento por debajo del watchdog TDR de
// Windows (≈ 2 s en una GPU que también maneja el escritorio, docs/inventario-gpu.md §3).
constexpr uint64_t LOTE_GPU = 1u << 20;

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

// Simula los escenarios globales [base, base + n) en la GPU y devuelve k, n e histograma.
// `avance(hechos)` se llama tras cada lote, si se pasa (sala de control).
EjecucionCuda simular_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                           int hilos_por_bloque, const std::function<void(uint64_t)>& avance = {});

// Diagnóstico de V2: amax de cada escenario de [base, base + n) calculado en la GPU.
std::vector<double> amax_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n);

}  // namespace pp
