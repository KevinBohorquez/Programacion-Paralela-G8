import { memo, useId, useMemo } from "react";
import { decimalesPaso, escalaLineal, escalaLog, idSeguro, redondear, rutaPolilinea } from "./escalas";
import { formatearNumero, potenciaDiez } from "./formato";
import type { GraficoConvergenciaProps } from "./tipos";
import { useAncho } from "./useAncho";
import ejes from "./ejes.module.css";
import styles from "./GraficoConvergencia.module.css";

const M = { izq: 76, der: 32, sup: 40, inf: 52 } as const;
const ALTO = 380;
const Z = 1.96;
const MUESTRAS_GUIA = 48;

/** Half-width of a 95 % interval for a proportion p after n trials: the 1/√N envelope. */
export function semiancho(p: number, n: number): number {
  return Z * Math.sqrt(Math.max(0, p * (1 - p)) / n);
}

/** p̂ against N on a log₁₀ axis, Wilson error bars, and a 1/√N guide centred at the latest p̂. */
export const GraficoConvergencia = memo(function GraficoConvergencia({ puntos }: GraficoConvergenciaProps) {
  const { ref, ancho } = useAncho<HTMLDivElement>(720);
  const recorte = idSeguro(useId());

  const geo = useMemo(() => {
    const datos = puntos.filter((q) => q.n > 0 && Number.isFinite(q.p)).sort((a, b) => a.n - b.n);
    const ultimo = datos[datos.length - 1];
    const ex = escalaLog(datos[0]?.n ?? 1e3, ultimo?.n ?? 1e7);
    let yMin = Infinity;
    let yMax = -Infinity;
    for (const q of datos) {
      yMin = Math.min(yMin, q.lo, q.p);
      yMax = Math.max(yMax, q.hi, q.p);
    }
    if (ultimo && datos[0]) {
      const h = semiancho(ultimo.p, datos[0].n);
      yMin = Math.min(yMin, ultimo.p - h);
      yMax = Math.max(yMax, ultimo.p + h);
    }
    if (!(yMin <= yMax)) [yMin, yMax] = [0, 1];
    const ey = escalaLineal(Math.max(0, yMin), Math.min(1, yMax), 5);
    const plotW = ancho - M.izq - M.der;
    const plotH = ALTO - M.sup - M.inf;
    const sx = (n: number) => M.izq + ((Math.log10(n) - ex.eMin) / (ex.eMax - ex.eMin)) * plotW;
    const sy = (v: number) => M.sup + (1 - (v - ey.min) / (ey.max - ey.min)) * plotH;

    let guiaArriba = "";
    let guiaAbajo = "";
    let rotulo: { x: number; y: number } | null = null;
    if (ultimo) {
      const arriba: [number, number][] = [];
      const abajo: [number, number][] = [];
      for (let k = 0; k <= MUESTRAS_GUIA; k += 1) {
        const n = 10 ** (ex.eMin + ((ex.eMax - ex.eMin) * k) / MUESTRAS_GUIA);
        const h = semiancho(ultimo.p, n);
        arriba.push([sx(n), sy(ultimo.p + h)]);
        abajo.push([sx(n), sy(ultimo.p - h)]);
        if (rotulo === null && ultimo.p + h <= ey.max) rotulo = { x: sx(n), y: sy(ultimo.p + h) };
      }
      guiaArriba = rutaPolilinea(arriba);
      guiaAbajo = rutaPolilinea(abajo);
    }
    return { datos, ultimo, ex, ey, plotW, plotH, sx, sy, guiaArriba, guiaAbajo, rotulo, decY: decimalesPaso(ey.paso) };
  }, [puntos, ancho]);

  const { ultimo, sx, sy } = geo;
  const decP = Math.max(3, geo.decY + 1);
  const resumen = ultimo
    ? `Convergencia de p̂ con N: ${geo.datos.length} puntos; último p̂ = ${formatearNumero(ultimo.p, decP)} con N = ${formatearNumero(ultimo.n, 0)}, intervalo de Wilson ${formatearNumero(ultimo.lo, decP)} a ${formatearNumero(ultimo.hi, decP)}`
    : "Convergencia de p̂: sin puntos todavía";
  const yBase = M.sup + geo.plotH;

  return (
    <div ref={ref} className={ejes.caja}>
      <svg className={ejes.svg} viewBox={`0 0 ${ancho} ${ALTO}`} role="img" aria-label={resumen}>
        <title>{resumen}</title>
        <defs>
          <clipPath id={recorte}>
            <rect x={M.izq} y={M.sup} width={geo.plotW} height={geo.plotH} />
          </clipPath>
        </defs>
        <text className={ejes.tituloEje} x={M.izq - 8} y={18}>
          p̂ = P(Amax &gt; U)
        </text>
        {geo.ey.ticks.map((t) => (
          <g key={t}>
            <line className={ejes.rejilla} x1={M.izq} x2={M.izq + geo.plotW} y1={redondear(sy(t))} y2={redondear(sy(t))} />
            <text className={ejes.eje} x={M.izq - 10} y={redondear(sy(t)) + 4} textAnchor="end">
              {formatearNumero(t, geo.decY)}
            </text>
          </g>
        ))}
        {geo.ex.decadas.map((e) => (
          <g key={e}>
            <line className={ejes.rejilla} x1={redondear(sx(10 ** e))} x2={redondear(sx(10 ** e))} y1={M.sup} y2={yBase} />
            <text className={ejes.eje} x={redondear(sx(10 ** e))} y={ALTO - M.inf + 22} textAnchor="middle">
              {potenciaDiez(e)}
            </text>
          </g>
        ))}
        <line className={ejes.base} x1={M.izq} x2={M.izq + geo.plotW} y1={yBase} y2={yBase} />
        <text className={ejes.tituloEje} x={M.izq + geo.plotW} y={ALTO - 8} textAnchor="end">
          escenarios N (escala log₁₀)
        </text>

        {ultimo ? (
          <g clipPath={`url(#${recorte})`}>
            <line className={styles.centro} x1={M.izq} x2={M.izq + geo.plotW} y1={redondear(sy(ultimo.p))} y2={redondear(sy(ultimo.p))} />
            <path className={styles.guia} d={geo.guiaArriba} />
            <path className={styles.guia} d={geo.guiaAbajo} />
          </g>
        ) : (
          <text className={ejes.vacio} x={M.izq + geo.plotW / 2} y={M.sup + geo.plotH / 2} textAnchor="middle">
            sin puntos todavía
          </text>
        )}
        {geo.rotulo ? (
          <text className={styles.textoGuia} x={redondear(geo.rotulo.x + 10)} y={redondear(Math.max(M.sup + 14, geo.rotulo.y - 6))}>
            ∝ 1/√N
          </text>
        ) : null}

        <g>
          {geo.datos.map((q) => {
            const x = redondear(sx(q.n));
            const yLo = redondear(sy(q.lo));
            const yHi = redondear(sy(q.hi));
            return (
              <g key={q.n}>
                <line className={styles.barraError} x1={x} x2={x} y1={yLo} y2={yHi} />
                <line className={styles.barraError} x1={x - 5} x2={x + 5} y1={yLo} y2={yLo} />
                <line className={styles.barraError} x1={x - 5} x2={x + 5} y1={yHi} y2={yHi} />
                <circle className={styles.punto} cx={x} cy={redondear(sy(q.p))} r={5} />
              </g>
            );
          })}
        </g>
        {ultimo ? (
          <text
            className={styles.valor}
            x={redondear(sx(ultimo.n) - 12)}
            y={redondear(Math.max(M.sup + 16, sy(ultimo.hi) - 12))}
            textAnchor="end"
          >
            p̂ = {formatearNumero(ultimo.p, decP)}
          </text>
        ) : null}
      </svg>
    </div>
  );
});
