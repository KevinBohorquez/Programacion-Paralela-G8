// T12 | Responsable: Ashley | Interfaz de resultados, estadísticas, configuración y CSV.
#pragma once

#include <array>
#include <cstdint>
#include <string>

#include "simulacion.hpp"

namespace pp {

// ---------- Acumulador (lo que se reduce entre hilos / procesos) ----------
struct Acumulador {
    uint64_t k = 0;  // escenarios con inundación
    uint64_t n = 0;  // escenarios simulados
    std::array<uint64_t, NBINS> hist{};

    void agregar(const Resultado& r);          // suma un escenario
    void combinar(const Acumulador& otro);     // suma otro acumulador
    bool operator==(const Acumulador& o) const { return k == o.k && n == o.n && hist == o.hist; }
};

// ---------- Estadísticas (src/stats) ----------
struct Intervalo {
    double inf;
    double sup;
};

// Intervalo de Wilson al 95 % (z = 1,959963984540054). n = 0 → [0, 1].
// k = 0 da inf = 0 exacto; k = n da sup = 1 exacto.
Intervalo wilson(uint64_t k, uint64_t n, double z = 1.959963984540054);

// Clase del histograma: floor(amax) en mm; todo valor >= 511 mm cae en la clase 511.
int clase_histograma(double amax);

// ---------- Configuración (src/io/configuracion.cpp) ----------
struct Configuracion {
    std::string backend = "serial";
    std::string estacion = "sintetica";
    std::string regimen = "normal";
    uint64_t config_id = 0;     // c en idx = c*N + j
    uint64_t semilla = 12345;
    uint64_t n = 1000000;       // escenarios de esta configuración
    int hilos = 1;              // solo OpenMP
    std::string schedule = "";  // vacío = respetar OMP_SCHEDULE
    std::string salida = "";    // ruta del CSV (vacío = no escribir)
    uint64_t lote = 62500;      // tamaño de bloque de la cola (solo mpi_dinamico)
    int repeticion = 1;         // 0 = calentamiento; 1..5 = medidas
    bool calentamiento = false;
    bool verificar = false;     // MPI: comparar con la referencia secuencial (V1)
    bool silencioso = false;
    Parametros params;
};

// Lee "clave: valor" (YAML plano). Lanza std::runtime_error si el archivo o un valor es inválido.
void cargar_archivo_configuracion(const std::string& ruta, Configuracion& cfg);

// Procesa argumentos CLI (--config archivo y luego banderas que sobrescriben). Valida rangos.
// Devuelve false si se pidió --ayuda (ya impresa). Lanza std::runtime_error ante errores.
bool parsear_argumentos(int argc, char** argv, Configuracion& cfg);

void validar(const Configuracion& cfg);

// ---------- CSV de resultados (src/io/resultados_csv.cpp) ----------
struct MetadatosEjecucion {
    double tiempo_s = 0.0;
    std::string commit;
    std::string cpu;
    int nucleos_fisicos = 0;
    int nucleos_logicos = 0;
    std::string afinidad;       // p. ej. "OMP_PROC_BIND=close;OMP_PLACES=cores"
    std::string schedule_usado; // p. ej. "static" (solo OpenMP)
    int hilos_usados = 1;
    int procesos = 1;           // procesos MPI (1 si no hay MPI)
    // Columnas agregadas para S15 (se escriben al final del CSV, ver docs/contratos.md §5):
    std::string hardware;       // "host=<nombre>;ram_gb=<GiB>" del nodo del rango 0
    int nodos = 1;              // nodos distintos (MPI_Get_processor_name)
    std::string distribucion;   // procesos por nodo: "<host>:<p>;<host>:<p>" en orden de rango
    int bloques = 0;            // solo CUDA: bloques de la grilla (0 = no aplica, columna vacía)
    int hilos_por_bloque = 0;   // solo CUDA: hilos por bloque (0 = no aplica, columna vacía)
};

// Nombre del nodo (gethostname); "desconocido" si no se puede leer.
std::string nombre_nodo();

MetadatosEjecucion capturar_metadatos();

struct FilaResultado {
    Configuracion cfg;
    Acumulador acc;
    MetadatosEjecucion meta;
};

std::string encabezado_csv();
std::string fila_csv(const FilaResultado& f);
// Agrega la fila (escribe el encabezado si el archivo no existe o está vacío).
void escribir_csv(const std::string& ruta, const FilaResultado& f);
// Lectura posterior para validar el formato (primera fila de datos del archivo).
FilaResultado leer_primera_fila_csv(const std::string& ruta);
// Resumen legible (clave=valor) para la terminal; lo usan todos los backends.
void imprimir_resumen(const FilaResultado& f);

}  // namespace pp
