import { memo, useEffect, useMemo, useRef } from "react";
import {
  nombreCorrida,
  progreso,
  speedupDe,
  tasa,
  terminada,
  type Corrida,
  type EstadoSala,
} from "../dominio/estado";
import { fmtCompacto, fmtEntero, fmtP, fmtSegundos, fmtSpeedup } from "../dominio/formato";
import { useSala } from "../sala/instancia";
import { Dialogo } from "../ui/Dialogo";
import { Pestanas } from "../ui/Pestanas";
import { Plegable } from "../ui/Plegable";
import { IconoMaximizar } from "../ui/iconos";
import t from "../ui/Tarjeta.module.css";
import { GraficoSpeedup } from "../viz/GraficoSpeedup";
import { LineaBloques } from "../viz/LineaBloques";
import { colorBackend, type BarraSpeedup } from "../viz/tipos";
import { useControles } from "./controles";
import s from "./PanelCarrera.module.css";

const selCorridas = (e: EstadoSala) => e.corridas;
const selOcupado = (e: EstadoSala) => e.ocupado;
const selModo = (e: EstadoSala) => e.modo;

export function configuracion(c: Corrida): string {
  const partes: string[] = [];
  if (c.procesos > 1) partes.push(`${c.procesos} procesos`);
  if (c.hilos > 1) partes.push(`${c.hilos} hilos`);
  if (c.afinidad && c.afinidad !== "-") partes.push(`bind ${c.afinidad}`);
  partes.push(`N ${fmtCompacto(c.n)}`);
  return partes.join(" · ");
}

function estadoTexto(c: Corrida): string {
  if (c.error) return "error";
  if (c.fin) return "terminado";
  return `${c.estimado ? "estimado " : ""}${Math.round(progreso(c) * 100)} %`;
}

/** Elapsed seconds: final time when done, otherwise "now" minus start. Only running lanes read "now". */
function useTranscurrido(c: Corrida): number | null {
  const enCurso = !terminada(c);
  const ahora = useSala((e) => (enCurso ? e.ahora : 0));
  if (c.fin) return c.fin.segundos;
  if (c.error) return c.ts - c.ts0;
  return Math.max(0, ahora - c.ts0);
}

function TrabajoRangos({ trabajo }: { trabajo: number[] }) {
  const max = Math.max(...trabajo, 1);
  return (
    <figure className={s.trabajo}>
      <div className={s.trabajoBarras} role="img" aria-label={`Escenarios simulados por cada uno de ${trabajo.length} rangos`}>
        {trabajo.map((w, i) => (
          <i
            key={i}
            className={s.trabajoBarra}
            style={{ transform: `scaleY(${Math.max(0.03, w / max)})` }}
            title={`rango ${i}: ${fmtEntero(w)} escenarios`}
          />
        ))}
      </div>
      <figcaption className={`${s.nota} tnum`}>
        Trabajo por rango ({trabajo.length} rangos): mín {fmtCompacto(Math.min(...trabajo))}, máx {fmtCompacto(max)}{" "}
        escenarios
      </figcaption>
    </figure>
  );
}

function Detalle({ c }: { c: Corrida }) {
  const ahora = useSala((e) => (terminada(c) ? 0 : e.ahora));
  const rangos = Object.entries(c.rangos);
  return (
    <div className={s.detalle}>
      {c.backend === "mpi_dinamico" ? (
        <div className={s.linea}>
          <LineaBloques rangos={c.procesos} bloques={c.bloques} total={c.n} t0={c.ts0} t1={terminada(c) ? c.ts : Math.max(ahora, c.ts)} />
          <p className={`${s.nota} tnum`}>
            {fmtEntero(c.bloques.length)} bloques asignados por el maestro (rango 0, no simula)
          </p>
        </div>
      ) : null}
      {c.fin?.trabajo_rangos?.length ? <TrabajoRangos trabajo={c.fin.trabajo_rangos} /> : null}
      {!c.fin && rangos.length ? (
        <p className={`${s.nota} tnum`}>
          {rangos.length} rangos informando avance:{" "}
          {rangos.map(([r, v]) => `r${r} ${Math.round((v.hecho / Math.max(v.total, 1)) * 100)} %`).join(" · ")}
        </p>
      ) : null}
      {c.error ? <p className={s.error}>{c.error}</p> : null}
      <DialogoCarril c={c} />
    </div>
  );
}

function DialogoCarril({ c }: { c: Corrida }) {
  const f = c.fin;
  const filas: [string, string][] = [
    ["Identificador", c.id],
    ["Backend", c.backend],
    ["Procesos × hilos", `${c.procesos} × ${c.hilos}`],
    ["Afinidad", c.afinidad],
    ["N escenarios", fmtEntero(c.n)],
    ["Avance", estadoTexto(c)],
    ["Escenarios/s", fmtCompacto(tasa(c))],
  ];
  if (f) {
    filas.push(
      ["k (escenarios con Amax > U)", fmtEntero(f.k)],
      ["p̂", fmtP(f.p)],
      ["Wilson 95 %", `[${fmtP(f.wilson[0])}, ${fmtP(f.wilson[1])}]`],
      ["Huella hist512", f.huella],
      ["Tiempo de simulación", fmtSegundos(f.segundos)],
      ["Tiempo de pared", fmtSegundos(f.segundos_pared)],
      ["Speedup", fmtSpeedup(f.speedup)],
    );
  }
  if (c.bloques.length) filas.push(["Bloques E2", fmtEntero(c.bloques.length)]);
  return (
    <Dialogo.Root>
      <Dialogo.Trigger variante="fantasma" className={s.verDetalle}>
        <IconoMaximizar />
        Ver métricas y comando
      </Dialogo.Trigger>
      <Dialogo.Content>
        <Dialogo.Header>
          <Dialogo.Title>{nombreCorrida(c)}</Dialogo.Title>
          <Dialogo.Close />
        </Dialogo.Header>
        <Pestanas.Root porDefecto="metricas" className={s.pestanas}>
          <Pestanas.List aria-label="Detalle de la corrida">
            <Pestanas.Trigger valor="metricas">Métricas</Pestanas.Trigger>
            <Pestanas.Trigger valor="comando">Comando</Pestanas.Trigger>
          </Pestanas.List>
          <Pestanas.Panel valor="metricas">
            <dl className={`${s.metricas} tnum`}>
              {filas.map(([k, v]) => (
                <div key={k} className={s.metrica}>
                  <dt>{k}</dt>
                  <dd className={k.startsWith("Huella") || k === "Identificador" ? s.mono : undefined}>{v}</dd>
                </div>
              ))}
            </dl>
          </Pestanas.Panel>
          <Pestanas.Panel valor="comando">
            <pre className={s.comando}>{c.comando || "El servidor no informó la línea de comando."}</pre>
          </Pestanas.Panel>
        </Pestanas.Root>
      </Dialogo.Content>
    </Dialogo.Root>
  );
}

interface CarrilProps {
  c: Corrida;
  speedup: number | null;
  derivado: boolean;
}

const Carril = memo(function Carril({ c, speedup, derivado }: CarrilProps) {
  const pr = progreso(c);
  const segundos = useTranscurrido(c);
  const ts = tasa(c);
  const estado = c.error ? "error" : c.fin ? "hecho" : c.estimado ? "estimado" : "curso";
  return (
    <Plegable.Root className={s.carril} data-id={c.id} data-estado={estado} style={{ "--color": colorBackend[c.backend] } as React.CSSProperties}>
      <Plegable.Trigger className={s.carrilCabecera}>
        <span className={s.carrilNombre}>
          <i className={s.muestra} aria-hidden="true" />
          {nombreCorrida(c)}
        </span>
        <span className={s.carrilConf}>{configuracion(c)}</span>
        <span className={`${s.carrilEstado} tnum`}>{estadoTexto(c)}</span>
      </Plegable.Trigger>
      <div
        className={s.pista}
        role="progressbar"
        aria-label={`Avance de ${nombreCorrida(c)}`}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pr * 100)}
      >
        <div className={s.relleno} style={{ transform: `scaleX(${pr})` }} />
      </div>
      <div className={`${s.datos} tnum`}>
        <span className={s.dato}>
          <b>{fmtCompacto(ts)}</b> escenarios/s
        </span>
        <span className={s.dato}>
          <b>{fmtSegundos(segundos)}</b> tiempo
        </span>
        <span className={s.dato} title={derivado ? "Calculado frente al serial de la carrera anterior" : undefined}>
          <b>{fmtSpeedup(speedup)}</b> speedup{derivado ? "*" : ""}
        </span>
      </div>
      <Plegable.Content>
        <Detalle c={c} />
      </Plegable.Content>
    </Plegable.Root>
  );
});

function barras(corridas: readonly Corrida[]): BarraSpeedup[] {
  return corridas.map((c) => {
    const sp = speedupDe(c, corridas);
    return {
      id: c.id,
      etiqueta: nombreCorrida(c),
      backend: c.backend,
      speedup: sp.valor,
      segundos: c.fin?.segundos ?? null,
      enCurso: !terminada(c),
    };
  });
}

export function PanelCarrera() {
  const corridas = useSala(selCorridas);
  const ocupado = useSala(selOcupado);
  const modo = useSala(selModo);
  const { controles } = useControles();
  const lista = useRef<HTMLDivElement>(null);
  const enCurso = corridas.find((c) => !terminada(c))?.id ?? null;
  const ultimaTerminada = [...corridas].reverse().find((c) => c.fin)?.id ?? null;
  const datosBarras = useMemo(() => barras(corridas), [corridas]);

  // Keep the running lane (or the one that just finished) on screen as the list grows.
  useEffect(() => {
    const id = enCurso ?? ultimaTerminada;
    if (!id || !lista.current) return;
    const nodo = lista.current.querySelector<HTMLElement>(`[data-id="${CSS.escape(id)}"]`);
    nodo?.scrollIntoView({ block: "nearest", behavior: "smooth" });
  }, [enCurso, ultimaTerminada]);

  const hayDerivado = datosBarras.some((b, i) => b.speedup !== null && corridas[i].fin && typeof corridas[i].fin!.speedup !== "number");

  return (
    <section className={`${t.tarjeta} ${s.panel}`} aria-labelledby="titulo-carrera">
      <header className={t.cabecera}>
        <h2 id="titulo-carrera" className={t.titulo}>
          Carrera
        </h2>
        <span className={s.sub}>{modo === "replay" ? "reproduciendo una grabación" : "uno tras otro, mismo N"}</span>
      </header>
      <div className={s.carriles} ref={lista}>
        {corridas.length === 0 ? (
          <div className={s.vacio}>
            {ocupado ? (
              <p>
                Te uniste con una corrida en curso: sus carriles aparecen con la próxima corrida. El uso de núcleos ya
                es en vivo.
              </p>
            ) : (
              <p>Pulsa «Carrera» para lanzar los backends uno tras otro.</p>
            )}
          </div>
        ) : (
          corridas.map((c) => {
            const sp = speedupDe(c, corridas);
            return <Carril key={c.id} c={c} speedup={sp.valor} derivado={sp.derivado} />;
          })
        )}
      </div>
      <div className={s.speedup}>
        <div className={s.speedupGrafico}>
          <GraficoSpeedup barras={datosBarras} ideal={controles.nucleos} />
        </div>
        {hayDerivado ? <p className={s.nota}>* speedup frente al serial de la carrera, calculado en la interfaz.</p> : null}
      </div>
    </section>
  );
}
