# Avance de Angela — T34, T56 y T61

Fecha: 26/11/2026. Rama: `angela`, actualizada por fast-forward con `origin/master`
(`a2a8b84`). Este avance prepara y prueba herramientas; no declara terminadas las
campañas. El reparto y los estados administrativos del corte del 20/11 siguen en
[el plan de S15](plan-desarrollo-semana-15.md#angela-r2--datos-riesgo-y-campañas-x3-x6-y-x8)
y en `cronograma/cronograma-interno.xlsx`.

## T34 — Evidencia e integridad

`scripts/run/auditar_campana.py` comprueba `n`, `k`, las 512 clases del histograma,
la suma del histograma y el conteo de puntos exitosos de los manifiestos. Añade
SHA-256 del CSV y sus logs a los cuatro manifiestos X6/bootstrap y genera
`results/cientifico/t34_integridad.json`, con hashes de CSV, logs, tablas y
manifiestos de la carpeta científica. Los finales de línea de esos archivos se
fijan a LF en `.gitattributes` para que el sello sea reproducible en Windows y Linux.

| Modelo | X6 | Bootstrap | Total contabilizado | Diferencia frente a 13.000 millones |
| --- | ---: | ---: | ---: | ---: |
| Sin H5 | 170 × 10⁷ = 1.700 millones | 8.000 × 10⁶ = 8.000 millones | 9.700 millones | 3.300 millones |
| Con H5 | 170 × 10⁷ = 1.700 millones | 8.000 × 10⁶ = 8.000 millones | 9.700 millones | 3.300 millones |

Las campañas de ambos modelos **no se suman para alcanzar la meta**. En cada
bootstrap hay 72 filas que repiten una configuración de parámetros: el inventario
las distingue del número de configuraciones distintas. El total es trabajo
contabilizado, no una afirmación de independencia estadística.

Desde la raíz, en la imagen `pp-g8`:

```bash
python3 scripts/run/auditar_campana.py --actualizar-manifiestos
python3 scripts/run/auditar_campana.py --verificar
```

Pendiente para cerrar T34: completar el total mediante un plan de corridas
aprobado por el equipo o justificar y ajustar formalmente la meta; copiar la
carpeta científica a dos PC y registrar las ubicaciones. No se añadieron escenarios
ni se alteraron probabilidades, tiempos o semillas. El estado de validación del
modelo debe interpretarse con `docs/validacion-v6.md`, incluida su limitación
dentro de muestra para H5.

Para comprobar copias ya realizadas, cada ruta debe ser la raíz que contiene
`results/cientifico/`, no la carpeta científica directamente:

```bash
python3 scripts/run/auditar_campana.py \
  --respaldo 'PC_A=/mnt/respaldo-a/proyecto' \
  --respaldo 'PC_B=/mnt/respaldo-b/proyecto'
```

El programa **lee** las copias y compara hashes; no copia archivos. El nombre
del equipo es una declaración del operador y no una detección remota de su
identidad. Dos carpetas de una sola PC no satisfacen el criterio de dos equipos.
Una copia incompleta queda con `integridad_verificada=false`. Aquí no se dispone
de esas dos PC: `dos_respaldos_verificados` permanece en `false`.

## T56 — Medidor X8

La entrada se amplía sin cambiar el protocolo EXT2 de Lita:

```bash
python3 scripts/bench/medir_cpu_gpu.py --experimento x8 \
  --hostfile /ruta/hostfile --build-cpu-dir build/docker --build-dir build/cuda \
  --cargas 1e7,2e7,5e7,1e8 --procesos 4 --hilos 2 --dry-run
```

El plan compara MPI dinámico, MPI + OpenMP y MPI + OpenMP + GPU en el clúster y
repite las tres configuraciones en una sola PC: seis puntos por N. Cada punto
incluye calentamiento y cinco repeticiones. Se usa el mismo número de procesos,
semilla, configuración y lote; MPI puro utiliza un hilo por trabajador. No se
presenta esto como una comparación a igual presupuesto de núcleos entre niveles.

La ejecución oficial usa el mismo comando sin `--dry-run` y con
`--host-en-reposo`, después de comprobar `docker ps` y el reposo de **todas** las
PC, coordinar el turno y completar las dependencias. La bandera registra la
declaración del operador, no mide por sí sola la ausencia de interferencia.

Requisitos que el medidor comprueba o cuyo incumplimiento provoca un fallo:

- T25: hostfile de dos o tres PC. El primer host debe ser la PC que ejecuta el
  script, para que el rango 0 escriba su CSV temporal localmente. Debe haber slots
  suficientes para `--procesos`, sin sobresuscribir el lanzador MPI.
- Rutas absolutas iguales del repositorio, YAML, Python 3 y binarios en cada PC.
  `_lanzador_x8.py` recoge hostname, CPU, núcleos, RAM, GPU y SHA-256 del binario y
  del YAML en cada rango, antes de `MPI_Init`; se comprueba que los hashes coincidan.
- T54: `pp_mpi_omp_cuda` compilado **sin CUDA** en `--build-cpu-dir`; MPI puro usa
  `pp_mpi_dinamico` del mismo build. El build también debe contener `pp_serial`.
- T54/T55: `pp_mpi_omp_cuda` compilado **con CUDA** en `--build-dir`.
  No se sustituye por `pp_mpi_dinamico_gpu`, que corresponde a EXT2.
- Ambos builds en Release y T59 de la misma PC, commit, semilla y `config_id`,
  con cinco tiempos. Para cada N se corre además una referencia serial de
  equivalencia; no se extrapola el tiempo T1 a otros N.
- Contrato de salida pendiente de T54/T55: `[verif] rango=R bloques=B n_local=N`
  para todos los rangos, maestro 0 sin escenarios, y verificación global
  `estado=OK`. El rango GPU debe identificarse con `[gpu] rango=R ...` o
  `tipo=gpu` en su línea `[verif]`. La suma de bloques WORK de los trabajadores
  debe ser `ceil(N/lote)`; el contador de bloques del maestro no se vuelve a sumar.

Sin esas líneas no se inventa el reparto por PC ni se acepta el fallback CPU
como ejecución con GPU. Se exige equivalencia de `k`, `n` e `hist512` en el
calentamiento y todas las repeticiones. La demanda de hilos por PC se compara
con sus núcleos físicos y queda marcada en `sobresuscrito`.

Salidas: `results/bench/x8.csv`, `x8_rangos.csv`, `x8.log` y `x8.json`; figuras
`results/figures/x8_fraccion_bloques.svg` y `.png`, por rango y por PC. Cada punto
conserva sus cinco tiempos, calentamiento, metadatos, CV y equivalencia. Si una
corrida falla, el log y los puntos anteriores se conservan y `x8.json` queda en
`estado=error`; solo una campaña completa y graficada queda como `completada`.
No se sobrescriben salidas existentes.

**No hay mediciones X8 nuevas.** T25 y T54/T55 siguen pendientes en `master`.
El medidor está probado contra dobles de prueba y deberá comprobarse contra el
ejecutable real cuando esos entregables estén integrados.

## T61 — X3 listo para ejecutar

El plan oficial completo puede revisarse sin medir:

```bash
python3 scripts/bench/ejecutar_barridos.py --experimento x3 \
  --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido \
  --build-dir build/docker --recursos 8 --cargas 1e6,1e7,1e8,1e9 \
  --reps 5 --nucleos 24 --dry-run
```

`--nucleos 24` describe la PC de referencia; no convierte otra PC en equivalente.
Antes de medir, Ashley debe completar T59 y Miguel coordinar el turno de esa PC.
Compilar el commit vigente en Release con MPI, registrar `PP_COMMIT` y
`GIT_COMMIT`, comprobar el host en reposo y ejecutar los pasos en secuencia,
según `AGENTS.md`. Quitar `--dry-run` solo en ese entorno.

Se añadió la excepción permitida por T61 para una corrida serial de 10⁹ que no
quepa en el turno. No se activa por defecto:

```bash
python3 scripts/bench/ejecutar_barridos.py --experimento x3 \
  --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido \
  --build-dir build/docker --recursos 8 --cargas 1e6,1e7,1e8,1e9 \
  --reps 5 --nucleos 24 --excluir-serial-desde 1e9 \
  --motivo-exclusion 'La corrida serial de 1e9 no cabe en el turno disponible' \
  --dry-run
```

La exclusión omite tanto el punto serial como su referencia oculta. Para ese N,
`backend_referencia` identifica el primer backend paralelo y `nota` conserva el
motivo y aclara que la equivalencia **no es una validación contra serial**.
Para los N restantes sigue comparándose con serial. El motivo también debe
incluirse en el informe. El log conserva los comandos y la salida completa de
los simuladores, además del resumen. No se generaron `x3.csv` ni `x3.log` de
medición: los planes revisados se guardan como evidencia de `dry-run`.

## Validación y límites de este equipo

La revisión se realiza en Windows, sin Docker ni distribución WSL instalada.
El equipo local es un Intel Core i5-12450HX, con 8 núcleos físicos, 12 CPU
lógicas y aproximadamente 16 GB de RAM; no es la PC de referencia de las campañas.
Se usó Python 3.12 en un entorno aislado dentro de `_build/` exclusivamente para
auditoría y pruebas de herramientas; sus paquetes y binarios no se versionan.
El log `results/evidencia/angela_validacion_20261126.log` registra las pruebas,
el validador del cronograma, la comprobación de integridad y los límites del
entorno. Esta QA no sustituye CTest ni las pruebas de integración en Docker.

Pruebas nuevas: corrupción o ausencia de archivos, respaldos, conteos por
modelo, parámetros repetidos, exclusión serial sin corrida oculta, planes X8,
hostnames observados, reparto de bloques sin duplicar al maestro, GPU ausente,
hashes distintos entre PC, figuras y flujo de campaña completa/fracasada.
Los datos sintéticos de esas pruebas se crean en carpetas temporales, nunca
en los CSV de evidencia científica.
