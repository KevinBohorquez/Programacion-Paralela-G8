import { memo, useId, useMemo } from "react";
import { disponerBloques } from "./bloques";
import { decimalesPaso, escalaLineal, idSeguro, redondear } from "./escalas";
import { formatearCompacto, formatearNumero, formatearPorcentaje } from "./formato";
import type { LineaBloquesProps } from "./tipos";
import { useAncho } from "./useAncho";
import ejes from "./ejes.module.css";
import styles from "./LineaBloques.module.css";

const ANCHO = { izq: 200, der: 200, sup: 64, inf: 44 } as const;
/** A race lane is ~500px wide: short rank labels and counts so the plot keeps most of the width. */
const ESTRECHO = { izq: 92, der: 96, sup: 56, inf: 40 } as const;
const UMBRAL_ESTRECHO = 760;
const COBERTURA_Y = 30;
const COBERTURA_ALTO = 10;

/** Row height per rank: 24 ranks must fit in a lane without a nested scroll. */
function altoFila(filas: number): number {
  if (filas > 16) return 13;
  if (filas > 12) return 20;
  return 36;
}

/** Gantt-style timeline of the E2 dynamic master–worker scheduling, one row per MPI rank. */
export const LineaBloques = memo(function LineaBloques({ rangos, bloques, total, t0, t1 }: LineaBloquesProps) {
  const { ref, ancho } = useAncho<HTMLDivElement>(1200, 320);
  const trama = idSeguro(useId());
  const filas = Math.max(1, rangos);
  const fila = altoFila(filas);
  const estrecho = ancho < UMBRAL_ESTRECHO;
  const denso = fila < 24;
  const M = estrecho ? ESTRECHO : ANCHO;
  const alto = M.sup + filas * fila + M.inf;
  const plotW = ancho - M.izq - M.der;
  const hueco = denso ? 2 : 5;

  const disposicion = useMemo(() => disponerBloques(bloques, rangos, total, t0, t1), [bloques, rangos, total, t0, t1]);
  const escala = useMemo(() => escalaLineal(0, Math.max(t1 - t0, 1e-3), plotW > 700 ? 8 : 5), [t0, t1, plotW]);
  const decT = decimalesPaso(escala.paso);
  const sx = (s: number) => M.izq + (s / escala.max) * plotW;
  const sn = (i: number) => M.izq + (total > 0 ? i / total : 0) * plotW;

  // The block rects are the heavy part (~320); rebuild them only when the layout or width changes.
  const rects = useMemo(
    () =>
      disposicion.bloques.map((b) => {
        const x = sx(b.inicio);
        const w = Math.max(2, sx(b.fin) - x - 1);
        return (
          <rect
            key={`${b.rango}-${b.i0}`}
            className={b.sombra ? styles.bloqueB : styles.bloqueA}
            x={redondear(x)}
            y={M.sup + b.rango * fila + hueco}
            width={redondear(w)}
            height={fila - 2 * hueco}
            rx={2}
          />
        );
      }),
    // sx depends only on escala.max, plotW and the left margin.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [disposicion, escala.max, plotW, fila, M.izq],
  );

  const esclavos = Math.max(0, rangos - 1);
  const resumen = `Planificación dinámica: ${bloques.length} bloques asignados a ${esclavos} procesos trabajadores; ${formatearPorcentaje(disposicion.cobertura)} de N = ${formatearNumero(total, 0)} asignado`;

  return (
    <div ref={ref} className={ejes.caja}>
      <svg className={ejes.svg} viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={resumen}>
        <title>{resumen}</title>
        <defs>
          <pattern id={trama} width={8} height={8} patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line className={styles.trama} x1={0} x2={0} y1={0} y2={8} />
          </pattern>
        </defs>

        <text className={ejes.tituloEje} x={M.izq} y={COBERTURA_Y - 10}>
          N asignado
        </text>
        <text className={styles.cobertura} x={M.izq + plotW} y={COBERTURA_Y - 10} textAnchor="end">
          {formatearPorcentaje(disposicion.cobertura)}
          <tspan className={styles.coberturaN} dx={8}>
            de {formatearNumero(total, 0)}
          </tspan>
        </text>
        <rect className={styles.pista} x={M.izq} y={COBERTURA_Y} width={plotW} height={COBERTURA_ALTO} rx={COBERTURA_ALTO / 2} />
        {disposicion.cubierto.map((t) => (
          <rect
            key={t.i0}
            className={styles.cubierto}
            x={redondear(sn(t.i0))}
            y={COBERTURA_Y}
            width={redondear(Math.max(1, sn(t.i1) - sn(t.i0)))}
            height={COBERTURA_ALTO}
          />
        ))}

        {escala.ticks.map((t) => (
          <g key={t}>
            <line className={ejes.rejilla} x1={redondear(sx(t))} x2={redondear(sx(t))} y1={M.sup} y2={alto - M.inf} />
            <text className={ejes.eje} x={redondear(sx(t))} y={alto - M.inf + 22} textAnchor="middle">
              {formatearNumero(t, decT)}
            </text>
          </g>
        ))}
        <text className={ejes.tituloEje} x={M.izq + plotW} y={alto - 4} textAnchor="end">
          tiempo desde el inicio (s)
        </text>

        {Array.from({ length: filas }, (_, r) => {
          const y = M.sup + r * fila;
          const resumenRango = disposicion.porRango[r];
          return (
            <g key={r}>
              {r > 0 ? <line className={ejes.rejilla} x1={M.izq} x2={M.izq + plotW} y1={y} y2={y} /> : null}
              <text className={denso ? styles.rangoDenso : styles.rango} x={estrecho ? 4 : 16} y={y + fila / 2 + (denso ? 4 : 5)}>
                R{r}
                {r === 0 || !estrecho ? (
                  <tspan className={styles.rol} dx={denso ? 6 : 10}>
                    {r === 0 ? (estrecho ? "maestro" : "maestro (no simula)") : "trabajador"}
                  </tspan>
                ) : null}
              </text>
              {r === 0 ? (
                <rect className={styles.maestro} x={M.izq} y={y + hueco} width={plotW} height={fila - 2 * hueco} rx={3} fill={`url(#${trama})`} />
              ) : (
                <text className={denso ? styles.conteoDenso : styles.conteo} x={M.izq + plotW + (estrecho ? 10 : 16)} y={y + fila / 2 + (denso ? 4 : 5)}>
                  {resumenRango?.bloques ?? 0}
                  <tspan className={styles.conteoMuted}> bl · {formatearCompacto(resumenRango?.escenarios ?? 0)}</tspan>
                </text>
              )}
            </g>
          );
        })}
        <g>{rects}</g>
      </svg>
    </div>
  );
});
