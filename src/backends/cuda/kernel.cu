// T38 | Responsable: Lita | Kernel CUDA (EXT1): un hilo por escenario, Philox en la GPU y reducción
// del conteo y del histograma en memoria compartida.
//
// Cada hilo recorre escenarios con paso de grilla (grid-stride) dentro de un lote [inicio, fin) y llama
// a pp::hd::simular_escenario, el mismo código de los backends de CPU (include/nucleo_hd.hpp). Cada
// bloque acumula k y las 512 clases en memoria compartida y las suma a la memoria global al final.
// Se compila con -fmad=false (contrato V2). La revisión de la reducción y V8 son T39.
#include <cuda_runtime.h>

#include <algorithm>
#include <stdexcept>
#include <string>
#include <vector>

#include "cuda.hpp"
#include "nucleo_hd.hpp"

namespace pp {

namespace {

void comprobar(cudaError_t e, const char* que) {
    if (e != cudaSuccess) throw std::runtime_error(std::string("CUDA (") + que + "): " + cudaGetErrorString(e));
}

__global__ void kernel_escenarios(Parametros p, uint64_t clave, uint64_t base, uint64_t inicio, uint64_t fin,
                                  unsigned long long* hist_global, unsigned long long* k_global) {
    __shared__ unsigned int hist[NBINS];
    __shared__ unsigned int k_bloque;
    for (int i = threadIdx.x; i < NBINS; i += blockDim.x) hist[i] = 0u;
    if (threadIdx.x == 0) k_bloque = 0u;
    __syncthreads();

    // Un lote tiene a lo sumo LOTE_GPU escenarios, así que los contadores de 32 bits no desbordan.
    const uint64_t paso = static_cast<uint64_t>(gridDim.x) * blockDim.x;
    for (uint64_t j = inicio + static_cast<uint64_t>(blockIdx.x) * blockDim.x + threadIdx.x; j < fin; j += paso) {
        const Resultado r = hd::simular_escenario(p, clave, base + j);
        atomicAdd(&hist[hd::clase_histograma(r.amax)], 1u);
        if (r.inundacion) atomicAdd(&k_bloque, 1u);
    }
    __syncthreads();

    for (int i = threadIdx.x; i < NBINS; i += blockDim.x)
        if (hist[i] != 0u) atomicAdd(&hist_global[i], static_cast<unsigned long long>(hist[i]));
    if (threadIdx.x == 0 && k_bloque != 0u) atomicAdd(k_global, static_cast<unsigned long long>(k_bloque));
}

__global__ void kernel_amax(Parametros p, uint64_t clave, uint64_t base, uint64_t n, double* amax) {
    const uint64_t paso = static_cast<uint64_t>(gridDim.x) * blockDim.x;
    for (uint64_t j = static_cast<uint64_t>(blockIdx.x) * blockDim.x + threadIdx.x; j < n; j += paso)
        amax[j] = hd::simular_escenario(p, clave, base + j).amax;
}

std::string version(int v) { return std::to_string(v / 1000) + "." + std::to_string((v % 1000) / 10); }

}  // namespace

void inicializar_cuda() {
    int n = 0;
    comprobar(cudaGetDeviceCount(&n), "cudaGetDeviceCount");
    if (n == 0) throw std::runtime_error("no hay GPU CUDA disponible");
    comprobar(cudaSetDevice(0), "cudaSetDevice");
    comprobar(cudaFree(nullptr), "creación del contexto");
}

std::string descripcion_gpu() {
    cudaDeviceProp prop{};
    comprobar(cudaGetDeviceProperties(&prop, 0), "cudaGetDeviceProperties");
    int rt = 0, drv = 0;
    cudaRuntimeGetVersion(&rt);
    cudaDriverGetVersion(&drv);
    std::string nombre = prop.name;
    std::replace(nombre.begin(), nombre.end(), ';', ' ');
    return "gpu=" + nombre + ";cc=" + std::to_string(prop.major) + "." + std::to_string(prop.minor) +
           ";sm=" + std::to_string(prop.multiProcessorCount) + ";cuda_rt=" + version(rt) + ";driver=" + version(drv);
}

int bloques_residentes(int hilos_por_bloque) {
    cudaDeviceProp prop{};
    comprobar(cudaGetDeviceProperties(&prop, 0), "cudaGetDeviceProperties");
    int por_sm = 0;
    comprobar(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&por_sm, kernel_escenarios, hilos_por_bloque, 0),
              "cudaOccupancyMaxActiveBlocksPerMultiprocessor");
    return std::max(1, por_sm) * prop.multiProcessorCount;
}

EjecucionCuda simular_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                           int hilos_por_bloque, const std::function<void(uint64_t)>& avance) {
    EjecucionCuda r;
    r.hilos_por_bloque = hilos_por_bloque;
    r.bloques = bloques > 0 ? bloques : bloques_residentes(hilos_por_bloque);

    unsigned long long* d_hist = nullptr;
    unsigned long long* d_k = nullptr;
    comprobar(cudaMalloc(&d_hist, NBINS * sizeof(unsigned long long)), "cudaMalloc hist");
    comprobar(cudaMalloc(&d_k, sizeof(unsigned long long)), "cudaMalloc k");
    try {
        comprobar(cudaMemset(d_hist, 0, NBINS * sizeof(unsigned long long)), "cudaMemset hist");
        comprobar(cudaMemset(d_k, 0, sizeof(unsigned long long)), "cudaMemset k");
        for (uint64_t inicio = 0; inicio < n; inicio += LOTE_GPU) {
            const uint64_t fin = std::min(n, inicio + LOTE_GPU);
            kernel_escenarios<<<r.bloques, hilos_por_bloque>>>(p, clave, base, inicio, fin, d_hist, d_k);
            comprobar(cudaGetLastError(), "lanzamiento del kernel");
            ++r.lanzamientos;
            if (avance) {
                comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
                avance(fin - inicio);
            }
        }
        comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
        unsigned long long hist[NBINS];
        unsigned long long k = 0;
        comprobar(cudaMemcpy(hist, d_hist, sizeof hist, cudaMemcpyDeviceToHost), "cudaMemcpy hist");
        comprobar(cudaMemcpy(&k, d_k, sizeof k, cudaMemcpyDeviceToHost), "cudaMemcpy k");
        r.acc.k = k;
        r.acc.n = n;
        for (int i = 0; i < NBINS; ++i) r.acc.hist[static_cast<size_t>(i)] = hist[i];
    } catch (...) {
        cudaFree(d_hist);
        cudaFree(d_k);
        throw;
    }
    cudaFree(d_hist);
    cudaFree(d_k);
    return r;
}

std::vector<double> amax_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n) {
    std::vector<double> out(n);
    double* d = nullptr;
    comprobar(cudaMalloc(&d, n * sizeof(double)), "cudaMalloc amax");
    try {
        const int hpb = 256;
        for (uint64_t inicio = 0; inicio < n; inicio += LOTE_GPU) {
            const uint64_t m = std::min(n - inicio, static_cast<uint64_t>(LOTE_GPU));
            const int bloques = static_cast<int>((m + hpb - 1) / hpb);
            kernel_amax<<<bloques, hpb>>>(p, clave, base + inicio, m, d + inicio);
            comprobar(cudaGetLastError(), "lanzamiento de kernel_amax");
        }
        comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
        comprobar(cudaMemcpy(out.data(), d, n * sizeof(double), cudaMemcpyDeviceToHost), "cudaMemcpy amax");
    } catch (...) {
        cudaFree(d);
        throw;
    }
    cudaFree(d);
    return out;
}

}  // namespace pp
