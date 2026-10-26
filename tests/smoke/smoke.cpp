// T04 | Ashley | Prueba de humo que CTest ejecuta tras compilar el proyecto.
// Cubre lo mínimo que debe cumplirse siempre: Philox correcto, escenario reproducible,
// Wilson en casos límite, histograma y CSV con ida y vuelta.
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <stdexcept>
#include <string>

#include "resultados.hpp"
#include "simulacion.hpp"

static int fallos = 0;
#define VERIFICAR(cond)                                                             \
    do {                                                                            \
        if (!(cond)) {                                                              \
            std::fprintf(stderr, "FALLO %s:%d: %s\n", __FILE__, __LINE__, #cond);   \
            ++fallos;                                                               \
        }                                                                           \
    } while (0)

static bool igual4(const pp::Bloque4& b, uint32_t a, uint32_t c, uint32_t d, uint32_t e) {
    return b.v[0] == a && b.v[1] == c && b.v[2] == d && b.v[3] == e;
}

int main() {
    using namespace pp;

    // 1) Philox4x32-10: vectores de prueba oficiales de Random123 (kat_vectors).
    VERIFICAR(igual4(philox4x32_10({{0, 0, 0, 0}}, 0, 0), 0x6627e8d5u, 0xe169c58du, 0xbc57ac4cu, 0x9b00dbd8u));
    VERIFICAR(igual4(philox4x32_10({{0xffffffffu, 0xffffffffu, 0xffffffffu, 0xffffffffu}}, 0xffffffffu, 0xffffffffu),
                     0x408f276du, 0x41c83b0eu, 0xa20bc7c6u, 0x6d5451fdu));
    VERIFICAR(igual4(philox4x32_10({{0x243f6a88u, 0x85a308d3u, 0x13198a2eu, 0x03707344u}}, 0xa4093822u, 0x299f31d0u),
                     0xd16cfe09u, 0x94fdcceb, 0x5001e420u, 0x24126ea1u));

    // 2) Uniforme siempre dentro de (0,1).
    VERIFICAR(uniforme32(0) > 0.0 && uniforme32(0xffffffffu) < 1.0);

    // 3) Escenario: reproducible y dependiente solo de (parámetros, clave, idx).
    Parametros p;
    p.p01 = 0.15; p.p11 = 0.60; p.alfa = 0.7; p.theta = 9.0; p.capacidad = 6.0; p.umbral = 50.0; p.dias = 120;
    const uint64_t clave = derivar_clave(20261015, 0);
    const Resultado a = simular_escenario(p, clave, 42);
    const Resultado b = simular_escenario(p, clave, 42);
    VERIFICAR(a.inundacion == b.inundacion && a.amax == b.amax);
    VERIFICAR(derivar_clave(1, 0) != derivar_clave(2, 0) && derivar_clave(1, 0) != derivar_clave(1, 1));

    // 4) Balance: Lindley y casos extremos.
    VERIFICAR(actualizar_acumulado(0.0, 3.0, 5.0) == 0.0);
    VERIFICAR(actualizar_acumulado(4.0, 10.0, 5.0) == 9.0);
    Parametros seco = p; seco.p01 = 0.0;
    VERIFICAR(!simular_escenario(seco, clave, 7).inundacion && simular_escenario(seco, clave, 7).amax == 0.0);

    // 5) Reducción manual en dos órdenes distintos = mismo acumulador (base de V1).
    Acumulador directo, mitades_a, mitades_b;
    for (uint64_t i = 0; i < 2000; ++i) directo.agregar(simular_escenario(p, clave, i));
    for (uint64_t i = 0; i < 2000; i += 2) mitades_a.agregar(simular_escenario(p, clave, i));
    for (uint64_t i = 1; i < 2000; i += 2) mitades_b.agregar(simular_escenario(p, clave, i));
    mitades_a.combinar(mitades_b);
    VERIFICAR(directo == mitades_a);
    VERIFICAR(directo.n == 2000);
    uint64_t suma = 0;
    for (uint64_t h : directo.hist) suma += h;
    VERIFICAR(suma == directo.n);

    // 6) Wilson en casos límite.
    const Intervalo i0 = wilson(0, 100), iN = wilson(100, 100), i_nada = wilson(0, 0);
    VERIFICAR(i0.inf == 0.0 && i0.sup > 0.0 && i0.sup < 0.05);
    VERIFICAR(iN.sup == 1.0 && iN.inf > 0.95 && iN.inf < 1.0);
    VERIFICAR(i_nada.inf == 0.0 && i_nada.sup == 1.0);
    const Intervalo im = wilson(50, 100);  // valor de referencia: [0.4038, 0.5962]
    VERIFICAR(std::fabs(im.inf - 0.40383) < 1e-4 && std::fabs(im.sup - 0.59617) < 1e-4);

    // 7) Histograma: clases de 1 mm con saturación en la última.
    VERIFICAR(clase_histograma(0.0) == 0 && clase_histograma(0.99) == 0 && clase_histograma(1.0) == 1);
    VERIFICAR(clase_histograma(510.5) == 510 && clase_histograma(511.0) == 511 && clase_histograma(1e9) == 511);

    // 8) CSV: escribir, volver a leer y comparar.
    const std::string ruta = "smoke_resultado.csv";
    std::remove(ruta.c_str());
    FilaResultado f;
    f.cfg.backend = "serial"; f.cfg.estacion = "sintetica"; f.cfg.regimen = "normal";
    f.cfg.semilla = 20261015; f.cfg.n = directo.n; f.cfg.params = p;
    f.acc = directo;
    f.meta = capturar_metadatos();
    f.meta.tiempo_s = 0.125; f.meta.hilos_usados = 1;
    escribir_csv(ruta, f);
    const FilaResultado g = leer_primera_fila_csv(ruta);
    VERIFICAR(g.acc == f.acc && g.cfg.semilla == f.cfg.semilla && g.cfg.params.alfa == p.alfa);
    VERIFICAR(g.meta.tiempo_s == f.meta.tiempo_s && g.meta.commit == f.meta.commit);
    // Columnas de S15: CPU sin bloques CUDA (columnas vacías → 0), un nodo con un proceso.
    VERIFICAR(g.meta.hardware == f.meta.hardware && g.meta.hardware.rfind("host=", 0) == 0);
    VERIFICAR(g.meta.nodos == 1 && g.meta.distribucion == nombre_nodo() + ":1");
    VERIFICAR(g.meta.bloques == 0 && g.meta.hilos_por_bloque == 0);
    {  // fila CUDA: bloques e hilos por bloque viajan en el CSV
        const std::string ruta_cuda = "smoke_resultado_cuda.csv";
        std::remove(ruta_cuda.c_str());
        FilaResultado c = f;
        c.cfg.backend = "cuda"; c.meta.bloques = 160; c.meta.hilos_por_bloque = 256;
        escribir_csv(ruta_cuda, c);
        const FilaResultado d = leer_primera_fila_csv(ruta_cuda);
        VERIFICAR(d.meta.bloques == 160 && d.meta.hilos_por_bloque == 256);
        std::remove(ruta_cuda.c_str());
    }
    {  // un CSV con la cabecera anterior no se mezcla con la nueva
        const std::string ruta_vieja = "smoke_resultado_viejo.csv";
        { std::ofstream v(ruta_vieja); v << "backend,estacion\nserial,x\n"; }
        bool rechazado = false;
        try { escribir_csv(ruta_vieja, f); } catch (const std::runtime_error&) { rechazado = true; }
        VERIFICAR(rechazado);
        std::remove(ruta_vieja.c_str());
    }
    std::remove(ruta.c_str());

    if (fallos) {
        std::fprintf(stderr, "smoke: %d verificación(es) fallida(s)\n", fallos);
        return EXIT_FAILURE;
    }
    std::puts("smoke: OK");
    return EXIT_SUCCESS;
}
