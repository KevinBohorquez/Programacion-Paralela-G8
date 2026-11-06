// Pure axis helpers shared by the charts: nice linear scales, log decades, interpolation and SVG precision.

export interface EscalaLineal {
  readonly min: number;
  readonly max: number;
  readonly paso: number;
  readonly ticks: readonly number[];
}

const MULTIPLICADORES = [1, 2, 2.5, 5] as const;

/** Rounds an SVG coordinate to `decimales` places so the markup stays short and stable. */
export function redondear(valor: number, decimales = 1): number {
  const factor = 10 ** decimales;
  const r = Math.round(valor * factor) / factor;
  return Object.is(r, -0) ? 0 : r;
}

/** Clamps a value into [min, max]; NaN collapses to min. */
export function acotar(valor: number, min = 0, max = 1): number {
  if (!(valor > min)) return min;
  return valor > max ? max : valor;
}

/**
 * A linear scale with a round step (1, 2, 2.5 or 5 × 10^k), at most `maxIntervalos` intervals,
 * whose limits are the data limits rounded outwards to that step.
 */
export function escalaLineal(min: number, max: number, maxIntervalos = 5): EscalaLineal {
  let bajo = Number.isFinite(min) ? min : 0;
  let alto = Number.isFinite(max) ? max : 1;
  if (alto < bajo) [bajo, alto] = [alto, bajo];
  if (alto - bajo <= 0) {
    const holgura = bajo === 0 ? 1 : Math.abs(bajo) * 0.1;
    bajo -= holgura;
    alto += holgura;
    if (min >= 0 && bajo < 0) bajo = 0;
  }
  const amplitud = alto - bajo;
  for (let exponente = Math.floor(Math.log10(amplitud)) - 2; ; exponente += 1) {
    for (const multiplicador of MULTIPLICADORES) {
      const paso = multiplicador * 10 ** exponente;
      const inicio = Math.floor(bajo / paso + 1e-9);
      const fin = Math.ceil(alto / paso - 1e-9);
      if (fin - inicio <= maxIntervalos) {
        const ticks = Array.from({ length: fin - inicio + 1 }, (_, i) => Number(((inicio + i) * paso).toFixed(12)));
        return { min: ticks[0] ?? bajo, max: ticks[ticks.length - 1] ?? alto, paso, ticks };
      }
    }
  }
}

/** Smallest number of decimals that writes `paso` exactly (0.25 → 2, 5 → 0). */
export function decimalesPaso(paso: number): number {
  for (let d = 0; d <= 10; d += 1) {
    const escalado = paso * 10 ** d;
    if (Math.abs(escalado - Math.round(escalado)) < 1e-6) return d;
  }
  return 10;
}

export interface EscalaLog {
  readonly eMin: number;
  readonly eMax: number;
  /** Decade exponents with a tick, eMin..eMax. */
  readonly decadas: readonly number[];
}

/** Whole decades that cover [min, max], widened to at least [10^eMinimo, 10^eMaximo]. */
export function escalaLog(min: number, max: number, eMinimo = 3, eMaximo = 7): EscalaLog {
  const eMin = Math.min(eMinimo, min > 0 ? Math.floor(Math.log10(min) + 1e-9) : eMinimo);
  const eMax = Math.max(eMaximo, max > 0 ? Math.ceil(Math.log10(max) - 1e-9) : eMaximo);
  return { eMin, eMax, decadas: Array.from({ length: eMax - eMin + 1 }, (_, i) => eMin + i) };
}

/** Linear interpolation of y at x over ascending xs; clamps outside the range. */
export function interpolar(xs: readonly number[], ys: readonly number[], x: number): number | null {
  const n = Math.min(xs.length, ys.length);
  if (n === 0) return null;
  if (x <= xs[0]!) return ys[0]!;
  if (x >= xs[n - 1]!) return ys[n - 1]!;
  for (let i = 1; i < n; i += 1) {
    const x1 = xs[i]!;
    if (x <= x1) {
      const x0 = xs[i - 1]!;
      const t = x1 === x0 ? 0 : (x - x0) / (x1 - x0);
      return ys[i - 1]! + t * (ys[i]! - ys[i - 1]!);
    }
  }
  return ys[n - 1]!;
}

/** Minimum and maximum of a list, or null when it is empty. */
export function extremos(valores: readonly number[]): [number, number] | null {
  let min = Infinity;
  let max = -Infinity;
  for (const v of valores) {
    if (!Number.isFinite(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return min <= max ? [min, max] : null;
}

/** An SVG path through the points, coordinates rounded. */
export function rutaPolilinea(puntos: readonly (readonly [number, number])[]): string {
  let d = "";
  for (let i = 0; i < puntos.length; i += 1) {
    const [x, y] = puntos[i]!;
    d += `${i === 0 ? "M" : "L"}${redondear(x)} ${redondear(y)}`;
  }
  return d;
}

/** Strips characters that would break a `url(#id)` reference from a React `useId` value. */
export function idSeguro(id: string): string {
  return `v${id.replace(/[^a-zA-Z0-9_-]/g, "")}`;
}
