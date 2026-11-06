import { memo, useId, useMemo } from "react";
import { escalaLineal, idSeguro, redondear } from "./escalas";
import { formatearNumero, formatearSegundos, formatearSpeedup } from "./formato";
import { colorBackend, type GraficoSpeedupProps } from "./tipos";
import { useAncho } from "./useAncho";
import ejes from "./ejes.module.css";
import styles from "./GraficoSpeedup.module.css";

/**
 * Wide boxes put the run label beside a tall bar; narrow ones (the race column) use compact rows so
 * seven runs still fit under the lanes without overflowing the card.
 */
const LADO = { izq: 200, der: 150, sup: 36, inf: 40, fila: 52, barra: 13, alto: 26 } as const;
const COMPACTO = { izq: 168, der: 116, sup: 30, inf: 36, fila: 30, barra: 6, alto: 18 } as const;
const UMBRAL_APILADO = 900;

/** Horizontal speedup bars per run, in insertion order, with an "ideal" reference line. */
export const GraficoSpeedup = memo(function GraficoSpeedup({ barras, ideal }: GraficoSpeedupProps) {
  const { ref, ancho } = useAncho<HTMLDivElement>(720, 320);
  const gradiente = idSeguro(useId());
  const M = ancho < UMBRAL_APILADO ? COMPACTO : LADO;
  const BARRA = M.alto;
  const alto = M.sup + Math.max(1, barras.length) * M.fila + M.inf;
  const plotW = ancho - M.izq - M.der;

  const escala = useMemo(() => {
    let mayor = ideal > 0 ? ideal : 1;
    for (const b of barras) if (b.speedup !== null && b.speedup > mayor) mayor = b.speedup;
    return escalaLineal(0, mayor, plotW > 360 ? 6 : 4);
  }, [barras, ideal, plotW]);

  const sx = (v: number) => redondear(M.izq + (v / escala.max) * plotW);
  const xIdeal = sx(Math.max(0, ideal));
  const yBarra = (i: number) => M.sup + i * M.fila + M.barra;
  const resumen = barras.length
    ? `Speedup por corrida, ideal ${formatearNumero(ideal, 0)}×: ${barras
        .map((b) => `${b.etiqueta} ${b.speedup === null ? "en curso" : formatearSpeedup(b.speedup)}`)
        .join("; ")}`
    : "Speedup: aún no hay corridas";

  return (
    <div ref={ref} className={ejes.caja}>
      <svg className={ejes.svg} viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={resumen}>
        <title>{resumen}</title>
        <defs>
          <linearGradient id={gradiente} x1="0" x2="1" y1="0" y2="0">
            <stop offset="0" className={styles.paradaBorde} />
            <stop offset="0.5" className={styles.paradaCentro} />
            <stop offset="1" className={styles.paradaBorde} />
          </linearGradient>
        </defs>
        {escala.ticks.map((t) => (
          <g key={t}>
            <line className={ejes.rejilla} x1={sx(t)} x2={sx(t)} y1={M.sup} y2={alto - M.inf} />
            <text className={ejes.eje} x={sx(t)} y={alto - M.inf + 22} textAnchor="middle">
              {formatearNumero(t, 0)}×
            </text>
          </g>
        ))}
        {barras.length === 0 ? (
          <text className={ejes.vacio} x={M.izq + plotW / 2} y={M.sup + M.fila / 2 + 5} textAnchor="middle">
            esperando la primera corrida
          </text>
        ) : null}
        {barras.map((b, i) => {
          const y = yBarra(i);
          const fraccion = b.speedup === null ? 0 : Math.max(0, Math.min(1, b.speedup / escala.max));
          const color = colorBackend[b.backend];
          const yEtiqueta = y + BARRA / 2 + 5;
          return (
            <g key={b.id}>
              <circle cx={10} cy={yEtiqueta - 5} r={6} style={{ fill: color }} />
              <text className={styles.etiqueta} x={24} y={yEtiqueta}>
                {b.etiqueta}
              </text>
              <rect className={styles.pista} x={M.izq} y={y} width={plotW} height={BARRA} rx={5} />
              <rect
                className={styles.barra}
                x={M.izq}
                y={y}
                width={plotW}
                height={BARRA}
                rx={4}
                style={{ fill: color, transform: `scaleX(${redondear(fraccion, 4)})` }}
              />
              {b.enCurso ? (
                <svg x={M.izq} y={y} width={plotW} height={BARRA} className={styles.ventana}>
                  <rect
                    className={styles.brillo}
                    width={redondear(Math.max(60, plotW * 0.3))}
                    height={BARRA}
                    fill={`url(#${gradiente})`}
                    style={{ ["--recorrido" as string]: `${redondear(plotW)}px` }}
                  />
                </svg>
              ) : null}
            </g>
          );
        })}
        {ideal > 0 ? (
          <g>
            <line className={styles.ideal} x1={xIdeal} x2={xIdeal} y1={M.sup - 8} y2={alto - M.inf} />
            <text className={styles.textoIdeal} x={xIdeal} y={M.sup - 14} textAnchor="middle">
              ideal {formatearNumero(ideal, 0)}×
            </text>
          </g>
        ) : null}
        {barras.map((b, i) => {
          const valor = b.speedup === null ? 0 : Math.max(0, Math.min(escala.max, b.speedup));
          return (
            <g key={b.id} className={styles.rotulo} style={{ transform: `translate(${sx(valor) + 12}px, ${yBarra(i) + BARRA / 2 + 6}px)` }}>
              <text className={styles.valor}>
                {b.speedup === null ? "en curso…" : formatearSpeedup(b.speedup)}
                {b.segundos === null ? null : (
                  <tspan className={styles.segundos} dx={10}>
                    {formatearSegundos(b.segundos)}
                  </tspan>
                )}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
});
