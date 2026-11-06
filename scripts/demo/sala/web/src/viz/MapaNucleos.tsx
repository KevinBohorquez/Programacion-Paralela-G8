import { memo, useLayoutEffect, useMemo, useRef } from "react";
import { brilloCalor, dimensionesRejilla, mediaUtilizacion, nivelCalor, pesosCalor, PARADAS_CALOR, rutasSparkline } from "./calor";
import { acotar } from "./escalas";
import { formatearPorcentaje } from "./formato";
import type { MapaNucleosProps } from "./tipos";
import styles from "./MapaNucleos.module.css";

const CAPACIDAD = 60;
const SPARK_ANCHO = 600;
const SPARK_ALTO = 56;
const CAPAS = Array.from({ length: PARADAS_CALOR }, (_, k) => k);

interface CeldaProps {
  indice: number;
  /** Whole percent, so an unchanged cell skips rendering. */
  porcentaje: number;
}

/** One core: stacked ramp layers whose opacity blends the colour, so only opacity ever transitions. */
const Celda = memo(function Celda({ indice, porcentaje }: CeldaProps) {
  const u = porcentaje / 100;
  const pesos = pesosCalor(u);
  return (
    <div className={styles.celda} data-nivel={nivelCalor(u)}>
      <span className={styles.brillo} style={{ opacity: brilloCalor(u) }} />
      {CAPAS.map((k) => (
        <span key={k} className={styles.capa} style={{ background: `var(--heat-${k})`, opacity: pesos[k] }} />
      ))}
      <span className={styles.cpu}>CPU {indice}</span>
      <span className={styles.valor}>
        {porcentaje}
        <span className={styles.unidad}>%</span>
      </span>
    </div>
  );
});

/** Heat map of per-core utilisation with a legend and a 60-sample total-utilisation sparkline. */
export const MapaNucleos = memo(function MapaNucleos({ nucleos, etiqueta }: MapaNucleosProps) {
  const { columnas } = dimensionesRejilla(nucleos.length);
  const porcentajes = useMemo(() => nucleos.map((v) => Math.round(acotar(v) * 100)), [nucleos]);
  const media = useMemo(() => mediaUtilizacion(nucleos), [nucleos]);
  const maximo = porcentajes.length ? Math.max(...porcentajes) : 0;

  // The history lives in a ref and the sparkline path is written imperatively: no extra render per sample.
  const historial = useRef<number[]>([]);
  const ultimoVisto = useRef<readonly number[] | null>(null);
  const linea = useRef<SVGPathElement>(null);
  const area = useRef<SVGPathElement>(null);
  useLayoutEffect(() => {
    if (ultimoVisto.current === nucleos) return;
    ultimoVisto.current = nucleos;
    const h = historial.current;
    h.push(media);
    if (h.length > CAPACIDAD) h.shift();
    const rutas = rutasSparkline(h, SPARK_ANCHO, SPARK_ALTO, CAPACIDAD);
    linea.current?.setAttribute("d", rutas.linea);
    area.current?.setAttribute("d", rutas.area);
  }, [nucleos, media]);

  const resumen = `Utilización por núcleo, ${nucleos.length} CPU: media ${formatearPorcentaje(media)}, máxima ${maximo} %`;

  return (
    <figure className={styles.mapa} role="img" aria-label={etiqueta ? `${etiqueta}. ${resumen}` : resumen}>
      <div className={styles.cabecera} aria-hidden="true">
        {etiqueta ? <span className={styles.etiqueta}>{etiqueta}</span> : null}
        <span className={styles.media}>
          media <strong>{formatearPorcentaje(media)}</strong>
        </span>
      </div>
      <div className={styles.rejilla} style={{ gridTemplateColumns: `repeat(${columnas}, minmax(0, 1fr))` }} aria-hidden="true">
        {porcentajes.map((p, i) => (
          <Celda key={i} indice={i} porcentaje={p} />
        ))}
      </div>
      <div className={styles.pie} aria-hidden="true">
        <div className={styles.leyenda}>
          <span>0 %</span>
          <span className={styles.gradiente} />
          <span>100 %</span>
        </div>
        <div className={styles.spark}>
          <span className={styles.sparkTitulo}>total · últimos {CAPACIDAD}</span>
          <svg className={styles.sparkSvg} viewBox={`0 0 ${SPARK_ANCHO} ${SPARK_ALTO}`} preserveAspectRatio="none">
            <line className={styles.sparkGuia} x1={0} x2={SPARK_ANCHO} y1={SPARK_ALTO / 2} y2={SPARK_ALTO / 2} />
            <path ref={area} className={styles.sparkArea} />
            <path ref={linea} className={styles.sparkLinea} />
          </svg>
        </div>
      </div>
    </figure>
  );
});
