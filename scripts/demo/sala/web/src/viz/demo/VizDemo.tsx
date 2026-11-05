// Dev harness: renders the five charts with illustrative sample props, ticking at about 8 Hz.
import { useEffect, useMemo, useState } from "react";
import { CurvaRiesgo } from "../CurvaRiesgo";
import { GraficoConvergencia } from "../GraficoConvergencia";
import { GraficoSpeedup } from "../GraficoSpeedup";
import { LineaBloques } from "../LineaBloques";
import { MapaNucleos } from "../MapaNucleos";
import { barrasMuestra, bloquesMuestra, convergenciaMuestra, curvaMuestra, nucleosMuestra } from "./datosMuestra";

const RANGOS = 8;
const TOTAL = 10_000_000;
const TODOS = bloquesMuestra(RANGOS, TOTAL, 320);
const T0 = 100;
const DURACION = TODOS[TODOS.length - 1]!.ts - T0 + 0.2;
const CURVA = curvaMuestra();
const PUNTOS = convergenciaMuestra();

export function VizDemo() {
  const [t, setT] = useState(0);
  const [umbral, setUmbral] = useState(80);
  useEffect(() => {
    const id = window.setInterval(() => setT((v) => v + 0.125), 125);
    return () => window.clearInterval(id);
  }, []);

  // The schedule replays from the start and then holds at ~85 % so the timeline looks mid-run.
  const ahora = Math.min(DURACION * 0.85, 1 + t * 0.9);
  const nucleos = useMemo(() => nucleosMuestra(t), [t]);
  const visibles = useMemo(() => TODOS.filter((b) => b.ts <= T0 + ahora), [ahora]);

  return (
    <main className="harness">
      <header className="harness-cabecera">
        <h1>Sala de control · arnés de gráficos</h1>
        <p className="harness-aviso">Datos de muestra ilustrativos, sintéticos: no son resultados del simulador.</p>
        <label className="harness-control">
          Umbral U <input type="range" min={0} max={200} step={5} value={umbral} onChange={(e) => setUmbral(Number(e.target.value))} /> {umbral} mm
        </label>
      </header>
      <section className="harness-panel">
        <h2>Núcleos</h2>
        <MapaNucleos nucleos={nucleos} etiqueta="MPI dinámico · 24 procesos" />
      </section>
      <section className="harness-panel">
        <h2>Curva de riesgo</h2>
        <CurvaRiesgo {...CURVA} umbral={umbral} />
      </section>
      <section className="harness-panel">
        <h2>Speedup</h2>
        <GraficoSpeedup barras={barrasMuestra} ideal={24} />
      </section>
      <section className="harness-panel">
        <h2>Convergencia</h2>
        <GraficoConvergencia puntos={PUNTOS} />
      </section>
      <section className="harness-panel harness-ancho">
        <h2>Planificación dinámica E2</h2>
        <LineaBloques rangos={RANGOS} bloques={visibles} total={TOTAL} t0={T0} t1={T0 + ahora} />
      </section>
    </main>
  );
}
