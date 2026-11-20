// T11 | Responsable: Ashley | Interfaz del escenario y parámetros compartidos.
//
// Contrato del núcleo (plan S08): una función recibe parámetros, clave e
// índice global de escenario y devuelve inundación y máximo acumulado.
// El resultado depende SOLO de (parámetros, clave, idx): no hay estado
// compartido, por lo que cualquier reparto entre hilos/procesos da lo mismo (V1).
#pragma once

#include <cstdint>
#include <limits>

namespace pp {

constexpr int NBINS = 512;  // clases de 1 mm del histograma del máximo acumulado

// Parámetros de UNA configuración (zona, régimen, capacidad, conjunto bootstrap).
struct Parametros {
    double p01 = 0.0;       // P(lluvia hoy | ayer seco)
    double p11 = 0.0;       // P(lluvia hoy | ayer lluvioso)
    double alfa = 1.0;      // forma de la gamma de montos diarios
    double theta = 1.0;     // escala de la gamma (mm)
    double capacidad = 0.0; // C: drenaje evacuable por día (mm/día)
    double umbral = 0.0;    // U: umbral crítico de acumulación (mm)
    int dias = 120;         // D: días de la temporada
    // H5: escala aleatoria por temporada M ~ Gamma(kappa, 1/kappa) (media 1) que multiplica todos los
    // montos de la temporada. Infinito = desactivada: no se sortea M y el modelo es el de antes.
    double kappa = std::numeric_limits<double>::infinity();
};

struct Resultado {
    bool inundacion;  // max_t A_t > U
    double amax;      // máximo agua acumulada de la temporada (mm)
};

// ---- Philox4x32-10 (Salmon et al., 2011): generador basado en contador ----
struct Bloque4 {
    uint32_t v[4];
};

// Función pura philox(contador, clave). Coincide con Random123 (vectores de prueba en tests/smoke).
Bloque4 philox4x32_10(Bloque4 contador, uint32_t k0, uint32_t k1);

// Clave de 64 bits a partir de la semilla global y del identificador de configuración.
uint64_t derivar_clave(uint64_t semilla, uint64_t config_id);

// Uniforme en (0,1) a partir de una palabra de 32 bits (nunca 0 ni 1).
double uniforme32(uint32_t w);

// ---- Modelo de lluvia (Markov de dos estados + gamma, Marsaglia–Tsang) ----
// Subíndice `sub` del contador: 0 = ocurrencia; 1.. = intentos del muestreo gamma.
// Devuelve true si llueve en el día `dia` dado el estado de ayer.
bool ocurre_lluvia(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia, bool llovio_ayer);

// Lámina de un día lluvioso ~ gamma(alfa, theta).
double monto_gamma(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia);

// "Día" del contador Philox reservado para el sorteo de M (H5): ningún día real llega a este valor,
// así que no comparte números con la ocurrencia ni con los montos diarios. CUDA usa el mismo contador.
constexpr uint32_t DIA_TEMPORADA = 0xFFFFFFFFu;

// Factor de intensidad M de la temporada del escenario `idx`: 1.0 si kappa es infinito.
double factor_temporada(const Parametros& p, uint64_t clave, uint64_t idx);

// ---- Balance hídrico (recursión de Lindley) ----
// A_t = max(0, A_{t-1} + R_t - C)
double actualizar_acumulado(double acumulado, double lluvia, double capacidad);

// Simula una temporada completa del escenario con índice global `idx`.
Resultado simular_escenario(const Parametros& p, uint64_t clave, uint64_t idx);

}  // namespace pp
