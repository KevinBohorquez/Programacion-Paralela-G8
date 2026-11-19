// T38 | Responsable: Lita | Kernel CUDA (EXT1): un hilo por escenario, Philox en la GPU y reducción
// del conteo y del histograma en memoria compartida.
//
// Cada hilo recorre escenarios con paso de grilla (grid-stride) dentro de un lote [inicio, fin) y llama
// a pp::hd::simular_escenario, el mismo código de los backends de CPU (include/nucleo_hd.hpp). La
// reducción de k y del histograma (memoria compartida y luego global) está en reduccion.cuh (T39).
// Se compila con -fmad=false (contrato V2).
#include <cuda_runtime.h>

#include <algorithm>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "cuda.hpp"
#include "nucleo_hd.hpp"
#include "reduccion.cuh"

namespace pp {

namespace {

void comprobar(cudaError_t e, const char* que) {
    if (e != cudaSuccess) throw std::runtime_error(std::string("CUDA (") + que + "): " + cudaGetErrorString(e));
}

__global__ void kernel_escenarios(Parametros p, uint64_t clave, uint64_t base, uint64_t inicio, uint64_t fin,
                                  unsigned long long* hist_global, unsigned long long* k_global) {
    __shared__ cuda::ReduccionBloque red;
    cuda::iniciar(red);
    __syncthreads();

    const uint64_t paso = static_cast<uint64_t>(gridDim.x) * blockDim.x;
    for (uint64_t j = inicio + static_cast<uint64_t>(blockIdx.x) * blockDim.x + threadIdx.x; j < fin; j += paso) {
        const Resultado r = hd::simular_escenario(p, clave, base + j);
        cuda::sumar(red, hd::clase_histograma(r.amax), r.inundacion);
    }
    __syncthreads();
    cuda::volcar(red, hist_global, k_global);
}

// Mismo trabajo que kernel_escenarios, más la marca de SM, inicio y fin de cada bloque (diagnóstico T40).
__global__ void kernel_instrumentado(Parametros p, uint64_t clave, uint64_t base, uint64_t inicio, uint64_t fin,
                                     unsigned long long* hist_global, unsigned long long* k_global,
                                     unsigned int* sm_de, unsigned long long* t_ini, unsigned long long* t_fin) {
    __shared__ cuda::ReduccionBloque red;
    if (threadIdx.x == 0) {
        unsigned int smid;
        unsigned long long t;
        asm volatile("mov.u32 %0, %%smid;" : "=r"(smid));
        asm volatile("mov.u64 %0, %%globaltimer;" : "=l"(t));
        sm_de[blockIdx.x] = smid;
        t_ini[blockIdx.x] = t;
    }
    cuda::iniciar(red);
    __syncthreads();
    const uint64_t paso = static_cast<uint64_t>(gridDim.x) * blockDim.x;
    for (uint64_t j = inicio + static_cast<uint64_t>(blockIdx.x) * blockDim.x + threadIdx.x; j < fin; j += paso) {
        const Resultado r = hd::simular_escenario(p, clave, base + j);
        cuda::sumar(red, hd::clase_histograma(r.amax), r.inundacion);
    }
    __syncthreads();
    cuda::volcar(red, hist_global, k_global);
    if (threadIdx.x == 0) {
        unsigned long long t;
        asm volatile("mov.u64 %0, %%globaltimer;" : "=l"(t));
        t_fin[blockIdx.x] = t;
    }
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

int max_hilos_por_bloque() {
    cudaFuncAttributes a{};
    comprobar(cudaFuncGetAttributes(&a, kernel_escenarios), "cudaFuncGetAttributes");
    return a.maxThreadsPerBlock / 32 * 32;
}

int registros_por_hilo() {
    cudaFuncAttributes a{};
    comprobar(cudaFuncGetAttributes(&a, kernel_escenarios), "cudaFuncGetAttributes");
    return a.numRegs;
}

OcupacionCuda ocupacion_cuda(int bloques, int hilos_por_bloque) {
    cudaDeviceProp prop{};
    comprobar(cudaGetDeviceProperties(&prop, 0), "cudaGetDeviceProperties");
    OcupacionCuda o;
    o.sm = prop.multiProcessorCount;
    o.hilos_por_sm_max = prop.maxThreadsPerMultiProcessor;
    o.registros_por_hilo = registros_por_hilo();
    comprobar(cudaOccupancyMaxActiveBlocksPerMultiprocessor(&o.bloques_por_sm_max, kernel_escenarios, hilos_por_bloque, 0),
              "cudaOccupancyMaxActiveBlocksPerMultiprocessor");
    const int b = bloques > 0 ? bloques : std::max(1, o.bloques_por_sm_max) * o.sm;
    const int capacidad = std::max(1, o.bloques_por_sm_max) * o.sm;
    o.sm_usados = std::min(b, o.sm);
    o.bloques_por_sm = std::min((b + o.sm - 1) / o.sm, std::max(1, o.bloques_por_sm_max));
    o.olas = (b + capacidad - 1) / capacidad;
    o.ocupacion_sm = static_cast<double>(o.bloques_por_sm * hilos_por_bloque) / o.hilos_por_sm_max;
    o.ocupacion_gpu = o.ocupacion_sm * o.sm_usados / o.sm;
    return o;
}

MotorCuda::MotorCuda(int bloques, int hilos_por_bloque) : hilos_por_bloque_(hilos_por_bloque) {
    if (hilos_por_bloque > max_hilos_por_bloque())
        throw std::runtime_error("hilos_por_bloque=" + std::to_string(hilos_por_bloque) +
                                 " supera el máximo del kernel en esta GPU (" + std::to_string(max_hilos_por_bloque()) +
                                 "; el kernel usa " + std::to_string(registros_por_hilo()) + " registros por hilo)");
    bloques_ = bloques > 0 ? bloques : bloques_residentes(hilos_por_bloque);
    comprobar(cudaMalloc(&d_hist_, NBINS * sizeof(unsigned long long)), "cudaMalloc hist");
    if (cudaMalloc(&d_k_, sizeof(unsigned long long)) != cudaSuccess) {
        cudaFree(d_hist_);
        throw std::runtime_error("CUDA (cudaMalloc k): sin memoria");
    }
}

MotorCuda::~MotorCuda() {
    cudaFree(d_hist_);
    cudaFree(d_k_);
}

Acumulador MotorCuda::simular(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n,
                              const std::function<void(uint64_t)>& avance) {
    comprobar(cudaMemset(d_hist_, 0, NBINS * sizeof(unsigned long long)), "cudaMemset hist");
    comprobar(cudaMemset(d_k_, 0, sizeof(unsigned long long)), "cudaMemset k");
    const uint64_t lote = lote_gpu(bloques_, hilos_por_bloque_);
    for (uint64_t inicio = 0; inicio < n; inicio += lote) {
        const uint64_t fin = std::min(n, inicio + lote);
        kernel_escenarios<<<bloques_, hilos_por_bloque_>>>(p, clave, base, inicio, fin, d_hist_, d_k_);
        comprobar(cudaGetLastError(), "lanzamiento del kernel");
        ++lanzamientos_;
        if (avance) {
            comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
            avance(fin - inicio);
        }
    }
    comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
    unsigned long long hist[NBINS];
    unsigned long long k = 0;
    comprobar(cudaMemcpy(hist, d_hist_, sizeof hist, cudaMemcpyDeviceToHost), "cudaMemcpy hist");
    comprobar(cudaMemcpy(&k, d_k_, sizeof k, cudaMemcpyDeviceToHost), "cudaMemcpy k");
    Acumulador acc;
    acc.k = k;
    acc.n = n;
    for (int i = 0; i < NBINS; ++i) acc.hist[static_cast<size_t>(i)] = hist[i];
    return acc;
}

OcupacionObservada observar_ocupacion(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                                      int hilos_por_bloque) {
    const OcupacionCuda teorica = ocupacion_cuda(bloques, hilos_por_bloque);
    MotorCuda motor(bloques, hilos_por_bloque);  // valida hilos_por_bloque y resuelve bloques = 0
    const int b = motor.bloques();
    const uint64_t m = std::min(n, lote_gpu(b, hilos_por_bloque));  // un solo lanzamiento
    unsigned long long *d_hist = nullptr, *d_k = nullptr, *d_ini = nullptr, *d_fin = nullptr;
    unsigned int* d_sm = nullptr;
    comprobar(cudaMalloc(&d_hist, NBINS * sizeof(unsigned long long)), "cudaMalloc");
    comprobar(cudaMalloc(&d_k, sizeof(unsigned long long)), "cudaMalloc");
    comprobar(cudaMalloc(&d_ini, b * sizeof(unsigned long long)), "cudaMalloc");
    comprobar(cudaMalloc(&d_fin, b * sizeof(unsigned long long)), "cudaMalloc");
    comprobar(cudaMalloc(&d_sm, b * sizeof(unsigned int)), "cudaMalloc");
    std::vector<unsigned int> sm(b);
    std::vector<unsigned long long> ini(b), fin(b);
    try {
        comprobar(cudaMemset(d_hist, 0, NBINS * sizeof(unsigned long long)), "cudaMemset");
        comprobar(cudaMemset(d_k, 0, sizeof(unsigned long long)), "cudaMemset");
        kernel_instrumentado<<<b, hilos_por_bloque>>>(p, clave, base, 0, m, d_hist, d_k, d_sm, d_ini, d_fin);
        comprobar(cudaGetLastError(), "lanzamiento de kernel_instrumentado");
        comprobar(cudaDeviceSynchronize(), "cudaDeviceSynchronize");
        comprobar(cudaMemcpy(sm.data(), d_sm, b * sizeof(unsigned int), cudaMemcpyDeviceToHost), "cudaMemcpy");
        comprobar(cudaMemcpy(ini.data(), d_ini, b * sizeof(unsigned long long), cudaMemcpyDeviceToHost), "cudaMemcpy");
        comprobar(cudaMemcpy(fin.data(), d_fin, b * sizeof(unsigned long long), cudaMemcpyDeviceToHost), "cudaMemcpy");
    } catch (...) {
        cudaFree(d_hist); cudaFree(d_k); cudaFree(d_ini); cudaFree(d_fin); cudaFree(d_sm);
        throw;
    }
    cudaFree(d_hist); cudaFree(d_k); cudaFree(d_ini); cudaFree(d_fin); cudaFree(d_sm);

    // Por SM: barrido de eventos (inicio +1, fin −1) para el máximo de bloques simultáneos.
    std::vector<std::vector<std::pair<unsigned long long, int>>> eventos(256);
    for (int i = 0; i < b; ++i) {
        const unsigned int s = sm[i] % 256u;
        eventos[s].push_back({ini[i], +1});
        eventos[s].push_back({fin[i], -1});
    }
    OcupacionObservada o;
    double suma = 0.0;
    for (auto& ev : eventos) {
        if (ev.empty()) continue;
        std::sort(ev.begin(), ev.end());  // a igual instante, el fin (−1) antes que el inicio (+1)
        int vivos = 0, maximo = 0;
        for (const auto& e : ev) maximo = std::max(maximo, vivos += e.second);
        ++o.sm_observados;
        o.max_bloques_por_sm = std::max(o.max_bloques_por_sm, maximo);
        suma += maximo;
    }
    o.media_bloques_por_sm = o.sm_observados ? suma / o.sm_observados : 0.0;
    o.ocupacion_observada = o.media_bloques_por_sm * hilos_por_bloque / teorica.hilos_por_sm_max;
    o.ocupacion_gpu_observada = o.ocupacion_observada * o.sm_observados / teorica.sm;
    return o;
}

EjecucionCuda simular_cuda(const Parametros& p, uint64_t clave, uint64_t base, uint64_t n, int bloques,
                           int hilos_por_bloque, const std::function<void(uint64_t)>& avance) {
    MotorCuda motor(bloques, hilos_por_bloque);
    EjecucionCuda r;
    r.acc = motor.simular(p, clave, base, n, avance);
    r.bloques = motor.bloques();
    r.hilos_por_bloque = motor.hilos_por_bloque();
    r.lanzamientos = motor.lanzamientos();
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
