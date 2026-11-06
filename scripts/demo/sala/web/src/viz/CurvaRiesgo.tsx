import { memo, useMemo } from "react";
import { decimalesPaso, escalaLineal, extremos, interpolar, redondear, rutaPolilinea } from "./escalas";
import { formatearNumero } from "./formato";
import type { CurvaRiesgoProps } from "./tipos";
import { useAncho } from "./useAncho";
import ejes from "./ejes.module.css";
import styles from "./CurvaRiesgo.module.css";

const M = { izq: 64, der: 32, sup: 40, inf: 52 } as const;
const TICKS_Y = [0, 0.25, 0.5, 0.75, 1] as const;

/** Exceedance curve P(Amax > u) with its Wilson band and a marker at the selected threshold. */
export const CurvaRiesgo = memo(function CurvaRiesgo({ u, p, lo, hi, umbral, alto = 320 }: CurvaRiesgoProps) {
  const { ref, ancho } = useAncho<HTMLDivElement>(720);

  const geo = useMemo(() => {
    const n = Math.min(u.length, p.length, lo.length, hi.length);
    const rango = extremos(u.slice(0, n)) ?? [0, 100];
    const ex = escalaLineal(rango[0], rango[1], ancho > 560 ? 8 : 5);
    const plotW = ancho - M.izq - M.der;
    const plotH = alto - M.sup - M.inf;
    const sx = (v: number) => M.izq + ((v - ex.min) / (ex.max - ex.min)) * plotW;
    const sy = (v: number) => M.sup + (1 - Math.min(1, Math.max(0, v))) * plotH;
    const linea: [number, number][] = [];
    const arriba: [number, number][] = [];
    const abajo: [number, number][] = [];
    for (let i = 0; i < n; i += 1) {
      linea.push([sx(u[i]!), sy(p[i]!)]);
      arriba.push([sx(u[i]!), sy(hi[i]!)]);
      abajo.push([sx(u[i]!), sy(lo[i]!)]);
    }
    abajo.reverse();
    return {
      n,
      ex,
      sx,
      sy,
      plotW,
      plotH,
      linea: rutaPolilinea(linea),
      banda: n ? `${rutaPolilinea(arriba.concat(abajo))}Z` : "",
      decX: decimalesPaso(ex.paso),
    };
  }, [u, p, lo, hi, ancho, alto]);

  const pU = geo.n ? interpolar(u.slice(0, geo.n), p.slice(0, geo.n), umbral) : null;
  const xU = redondear(geo.sx(Math.min(geo.ex.max, Math.max(geo.ex.min, umbral))));
  const yU = pU === null ? null : redondear(geo.sy(pU));
  const aLaIzquierda = xU > M.izq + geo.plotW - 220;
  const textoP = pU === null ? "" : formatearNumero(pU, 3);
  const textoU = formatearNumero(umbral, 0);
  const resumen =
    pU === null
      ? "Curva de excedencia sin datos"
      : `Curva de excedencia P(Amax > u) para u de ${formatearNumero(geo.ex.min, geo.decX)} a ${formatearNumero(geo.ex.max, geo.decX)} mm; en el umbral U = ${textoU} mm, P = ${textoP}`;

  return (
    <div ref={ref} className={ejes.caja}>
      <svg className={ejes.svg} viewBox={`0 0 ${ancho} ${alto}`} role="img" aria-label={resumen}>
        <title>{resumen}</title>
        <text className={ejes.tituloEje} x={M.izq - 8} y={18}>
          P(Amax &gt; u)
        </text>
        {TICKS_Y.map((t) => (
          <g key={t}>
            <line className={ejes.rejilla} x1={M.izq} x2={M.izq + geo.plotW} y1={redondear(geo.sy(t))} y2={redondear(geo.sy(t))} />
            <text className={ejes.eje} x={M.izq - 10} y={redondear(geo.sy(t)) + 4} textAnchor="end">
              {formatearNumero(t, 2)}
            </text>
          </g>
        ))}
        {geo.ex.ticks.map((t) => (
          <text key={t} className={ejes.eje} x={redondear(geo.sx(t))} y={alto - M.inf + 22} textAnchor="middle">
            {formatearNumero(t, geo.decX)}
          </text>
        ))}
        <line className={ejes.base} x1={M.izq} x2={M.izq + geo.plotW} y1={M.sup + geo.plotH} y2={M.sup + geo.plotH} />
        <text className={ejes.tituloEje} x={M.izq + geo.plotW} y={alto - 8} textAnchor="end">
          umbral u (mm)
        </text>
        {geo.n === 0 ? (
          <text className={ejes.vacio} x={M.izq + geo.plotW / 2} y={M.sup + geo.plotH / 2} textAnchor="middle">
            sin datos todavía
          </text>
        ) : (
          <g>
            <path className={styles.banda} d={geo.banda} />
            <path className={styles.linea} d={geo.linea} />
          </g>
        )}
        <g className={styles.marcador} style={{ transform: `translate(${xU}px, 0px)` }}>
          <line className={styles.guia} x1={0} x2={0} y1={M.sup - 4} y2={M.sup + geo.plotH} />
          <text className={styles.textoU} x={aLaIzquierda ? -8 : 8} y={M.sup + 10} textAnchor={aLaIzquierda ? "end" : "start"}>
            U = {textoU} mm
          </text>
        </g>
        {yU === null ? null : (
          <g className={styles.marcador} style={{ transform: `translate(${xU}px, ${yU}px)` }}>
            <circle className={styles.halo} r={11} />
            <circle className={styles.punto} r={5.5} />
            <text className={styles.valor} x={aLaIzquierda ? -16 : 16} y={-10} textAnchor={aLaIzquierda ? "end" : "start"}>
              P = {textoP}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
});
