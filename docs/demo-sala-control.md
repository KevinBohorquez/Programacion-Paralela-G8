# Guía del operador: sala de control de la demo en vivo

La sala de control es una página a pantalla completa que muestra, mientras corre el simulador, el uso de cada núcleo, el avance de cada backend y la prueba de que todos producen el mismo resultado. Esta guía es para quien la opera durante la exposición. Las interfaces internas (eventos SSE y API) están en [contrato-sala-control.md](contrato-sala-control.md).

| Pieza | Dónde |
|-------|-------|
| Servidor | `scripts/demo/sala_control.py`, dentro del contenedor `pp-sala` (imagen `pp-g8`), puerto 8765 |
| Lanzador | `scripts/run/demo-sala.ps1` (Windows) o `scripts/run/demo-sala.sh` (Linux y macOS) |
| Grabaciones | `results/demo/sala/<nombre>.jsonl` |

## 1. Qué muestra cada panel

| Panel | Qué se ve | Concepto de programación paralela |
|-------|-----------|-----------------------------------|
| Núcleos | Una barra por CPU lógica (24 vCPU de WSL2), actualizada cada 0,2 s | Uso real de los recursos: serial ocupa un núcleo; OpenMP, MPI e híbrido los llenan |
| Carrera y speedup | Los cinco backends corren uno tras otro sobre el mismo N; al terminar cada uno se muestran su tiempo y su speedup frente al serial | **Speedup** S = T_serial / T_paralelo y su límite (Amdahl, fracción serial, sobrecarga de comunicación) |
| Balance E1 frente a E2 | Escenarios procesados por cada rango: tramos fijos en E1 (`mpi_estatico`) y bloques asignados por el maestro en E2 (`mpi_dinamico`) | **Balance de carga**: reparto estático frente a dinámico; con núcleos P y E, el reparto fijo deja rangos esperando al más lento |
| Afinidad | El híbrido con `OMP_PROC_BIND=close` y `mpirun --bind-to none` frente a `OMP_PROC_BIND=false` | **Afinidad de hilos**: con `close` y sin enlazado de rangos, los hilos de todos los rangos se apilan en los mismos núcleos; `false` deja que el sistema los reparta |
| Reproducibilidad | `k` y la huella SHA-256 del histograma `hist512` de cada backend | **Reproducibilidad**: Philox con contador por escenario da el mismo resultado sin importar backend, procesos ni hilos |
| Riesgo y convergencia | Curva P(Amax > u) con su banda y p estimada para N creciente | **Error de Monte Carlo**: el intervalo de **Wilson** se estrecha como 1/√N; más escenarios dan más precisión, y el paralelismo los hace asequibles |

Si la interfaz muestra el distintivo **REPLAY**, los datos vienen de una grabación y no del simulador (sección 4).

## 2. Puesta a punto

Desde la raíz del repositorio. En Windows use PowerShell; en Linux y macOS, `bash scripts/run/demo-sala.sh <acción>` con las mismas acciones (`--simular` en lugar de `-Simular`).

1. Preparar la imagen y el build (la primera vez tarda varios minutos):

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion preparar
   ```

   Construye `pp-g8` si falta, compila `build/docker` en Release con `-DPP_BUILD_MPI=ON` y lista los contenedores en marcha. Si aparece alguno que no sea de la demo, deténgalo.

2. Iniciar el servidor:

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion iniciar
   ```

   Espera a que `http://localhost:8765/` responda e imprime la URL. Ábrala en el navegador y pulse F11.

3. Comprobar el estado cuando haga falta:

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion estado
   ```

4. Al terminar:

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion detener
   ```

Cualquier acción acepta `-Simular`, que imprime los comandos sin ejecutarlos. El registro del servidor se ve con `docker logs -f pp-sala`.

### Interfaz moderna y clásica

El servidor sirve por defecto la interfaz moderna (React), ya compilada y versionada en `scripts/demo/sala/static/`, así que la demo no necesita Node. La interfaz original sigue en `scripts/demo/sala/clasica/` y se elige con una opción:

```bash
python3 scripts/demo/sala_control.py --interfaz clasica   # por defecto: --interfaz moderna
```

En la interfaz moderna:

- El tema es oscuro por defecto, pensado para el proyector. El botón del sol lo cambia y se puede forzar con `?tema=claro`.
- **Parámetros** aparece plegado con un resumen; al hacer clic se despliega.
- Cada carril de la carrera también se despliega con un clic. Muestra el trabajo por rango de E1, la línea de bloques de E2 y un botón con las métricas completas y la línea de comando.
- «Híbrido con error» y «Híbrido corregido» se añaden como carriles propios junto a la carrera. El híbrido de la carrera se llama solo «Híbrido» y no se borra. Una carrera nueva sí reemplaza todos los carriles.
- Convergencia espera a que termine la corrida o el replay en curso antes de calcular.
- Si la página se abre con una corrida ya en marcha, lo indica y sus carriles aparecen con la corrida siguiente. El uso de núcleos se ve en vivo desde el primer momento.

Para cambiar la interfaz moderna, edite `scripts/demo/sala/web/` y vuelva a compilarla (necesita Node 20 o posterior):

```bash
npm --prefix scripts/demo/sala/web install
npm --prefix scripts/demo/sala/web test
npm --prefix scripts/demo/sala/web run build   # escribe scripts/demo/sala/static/
```

Para desarrollar sin simulador, ejecute `npm --prefix scripts/demo/sala/web run dev` y abra `http://localhost:5173/static/?mock=1`. Ese modo genera eventos falsos en el navegador y lleva el distintivo **MOCK · datos ilustrativos**. Sus cifras no son mediciones, así que nunca lo use en la exposición. El respaldo real es el modo replay (sección 4).

## 3. Guion de 5 minutos

| Tiempo | Acción del operador | Qué decir |
|--------|---------------------|-----------|
| 0:00–0:30 | Mostrar la sala con los núcleos en reposo | «Esta es la máquina de medición: 24 CPU lógicas, 8 núcleos P y 16 E. Cada barra es un núcleo». |
| 0:30–2:00 | Lanzar la carrera con los cinco backends y N = 2·10⁷ | «Corremos el mismo problema en serie, con OpenMP, con MPI estático, con MPI dinámico y con el híbrido, uno tras otro para que el speedup sea honesto. Fíjense cómo serial ocupa una barra y los paralelos las llenan todas». Al terminar: «El speedup no llega a 24: hay núcleos E más lentos, una parte serial y sobrecarga». |
| 2:00–2:45 | Señalar el panel de balance | «En E1 cada rango recibe un tramo fijo y los que caen en núcleos E terminan después; en E2 el maestro entrega bloques a quien queda libre y el trabajo se ajusta a la velocidad de cada núcleo». |
| 2:45–3:30 | Lanzar el híbrido con `close` y luego con `false` | «Con `--bind-to none` y `close`, los hilos de los cuatro rangos se apilan en los mismos núcleos: miren las barras. Con `false` se reparten y el tiempo baja. Este fue un error real que corregimos». |
| 3:30–4:15 | Señalar el panel de reproducibilidad | «Los cinco backends dan el mismo k y la misma huella del histograma. El generador Philox depende del índice del escenario, no del hilo ni del proceso». |
| 4:15–5:00 | Mostrar riesgo y convergencia | «Esta es la probabilidad de que el caudal supere cada umbral, con su intervalo de Wilson. Con más escenarios el intervalo se estrecha como 1/√N; el paralelismo es lo que nos deja pagar esos escenarios». |

## 4. Respaldo: modo replay

Si el simulador falla, la máquina va lenta o no hay tiempo, se reproduce la grabación del ensayo con los mismos eventos y tiempos.

1. Grabar en el ensayo (con el servidor iniciado):

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion grabar          # empieza a grabar results/demo/sala/ensayo.jsonl
   # ... recorrer el guion completo ...
   .\scripts\run\demo-sala.ps1 -Accion grabar -Parar   # termina la grabación
   ```

2. Durante la exposición, si hace falta:

   ```powershell
   .\scripts\run\demo-sala.ps1 -Accion replay                 # velocidad 1,0
   .\scripts\run\demo-sala.ps1 -Accion replay -Velocidad 1.5  # más rápido si falta tiempo
   ```

   La interfaz muestra **REPLAY**. Dígalo en voz alta: «Esta es la grabación del ensayo de ayer, con los mismos datos».

Para otro nombre de grabación use `-Nombre <nombre>` (`--nombre` en bash). Las grabaciones disponibles se listan en `GET /api/grabaciones`.

## 5. Lista de verificación antes de la demo

- [ ] Cerrar programas pesados (navegadores con muchas pestañas, IDE, videollamadas que no se usen, compilaciones).
- [ ] Detener los demás contenedores: `-Accion preparar` los lista; `docker stop <nombre>` para cada uno que no sea `pp-sala`.
- [ ] Conectar el cargador y elegir el plan de energía de máximo rendimiento (con batería la CPU baja la frecuencia y el speedup cae).
- [ ] `-Accion preparar` sin errores y `-Accion iniciar` con la URL impresa.
- [ ] Hacer una grabación de ensayo completa (`grabar`, guion, `grabar -Parar`) y comprobar que `results/demo/sala/ensayo.jsonl` existe.
- [ ] Probar `-Accion replay` una vez hasta el final de la grabación.
- [ ] Navegador en pantalla completa y zoom ajustado al proyector.
