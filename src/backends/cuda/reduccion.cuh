// T39 | Responsable: Lita | Reducción del conteo k y del histograma de 512 clases en la GPU.
//
// Dos niveles, sin carreras:
//   1. Dentro del bloque: cada hilo suma su escenario en memoria compartida con atomicAdd de 32 bits
//      (contadores privados del bloque). Un lanzamiento procesa a lo sumo LOTE_GPU = 2^20 escenarios,
//      así que un contador de 32 bits nunca desborda.
//   2. Entre bloques: tras __syncthreads(), los hilos del bloque reparten las 512 clases y suman las
//      no nulas a la memoria global con atomicAdd de 64 bits; el hilo 0 suma k. La memoria global
//      acumula todos los lotes de la corrida y se copia al anfitrión una sola vez al final.
// La suma de enteros es asociativa y conmutativa: el resultado no depende de la grilla ni del orden
// de los bloques, por eso V2 exige igualdad exacta del histograma con cualquier grilla.
// V8 (compute-sanitizer racecheck/synccheck) comprueba que no haya carreras en la memoria compartida.
#pragma once

#include "simulacion.hpp"

namespace pp {
namespace cuda {

struct ReduccionBloque {
    unsigned int hist[NBINS];
    unsigned int k;
};

// Pone a cero los contadores del bloque. Debe seguirle un __syncthreads() antes de sumar.
__device__ inline void iniciar(ReduccionBloque& r) {
    for (int i = threadIdx.x; i < NBINS; i += blockDim.x) r.hist[i] = 0u;
    if (threadIdx.x == 0) r.k = 0u;
}

// Suma un escenario (clase del histograma e indicador de inundación) a los contadores del bloque.
__device__ inline void sumar(ReduccionBloque& r, int clase, bool inundacion) {
    atomicAdd(&r.hist[clase], 1u);
    if (inundacion) atomicAdd(&r.k, 1u);
}

// Suma los contadores del bloque a la memoria global. Debe precederle un __syncthreads().
__device__ inline void volcar(const ReduccionBloque& r, unsigned long long* hist_global, unsigned long long* k_global) {
    for (int i = threadIdx.x; i < NBINS; i += blockDim.x)
        if (r.hist[i] != 0u) atomicAdd(&hist_global[i], static_cast<unsigned long long>(r.hist[i]));
    if (threadIdx.x == 0 && r.k != 0u) atomicAdd(k_global, static_cast<unsigned long long>(r.k));
}

}  // namespace cuda
}  // namespace pp
