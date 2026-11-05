// Pure helpers for the core heat map: ramp weights, buckets, grid shape and the utilisation sparkline.
import { acotar, redondear } from "./escalas";

/** Number of stops on the `--heat-0` … `--heat-4` ramp. */
export const PARADAS_CALOR = 5;

/**
 * Opacity of each stacked ramp layer for a utilisation 0–1: layers up to the nearest stop are opaque and
 * the rest transparent, so the cell shows exactly one ramp colour and a change crossfades on opacity only.
 * (Blending neighbouring stops continuously muddies hue jumps such as indigo → amber.)
 */
export function pesosCalor(utilizacion: number): number[] {
  const nivel = nivelCalor(utilizacion);
  return Array.from({ length: PARADAS_CALOR }, (_, k) => (k <= nivel ? 1 : 0));
}

/** The ramp stop closest to a utilisation 0–1, used to pick a legible ink. */
export function nivelCalor(utilizacion: number): number {
  return Math.round(acotar(utilizacion) * (PARADAS_CALOR - 1));
}

/** Glow strength: 0 below 75 % utilisation, rising to 1 at 100 %. */
export function brilloCalor(utilizacion: number): number {
  return redondear(acotar((acotar(utilizacion) - 0.75) / 0.25), 2);
}

/** Columns × rows for n cells, preferring full rows and a landscape ratio near 1.6 (24 → 6 × 4). */
export function dimensionesRejilla(n: number): { columnas: number; filas: number } {
  if (n <= 0) return { columnas: 1, filas: 1 };
  let mejor = { columnas: n, filas: 1 };
  let mejorCosto = Infinity;
  for (let columnas = 1; columnas <= n; columnas += 1) {
    const filas = Math.ceil(n / columnas);
    const vacias = columnas * filas - n;
    const costo = vacias * 2 + Math.abs(columnas / filas - 1.6);
    if (costo < mejorCosto - 1e-9) {
      mejorCosto = costo;
      mejor = { columnas, filas };
    }
  }
  return mejor;
}

/** Mean of the utilisations, 0 when empty. */
export function mediaUtilizacion(nucleos: readonly number[]): number {
  if (nucleos.length === 0) return 0;
  let suma = 0;
  for (const v of nucleos) suma += acotar(v);
  return suma / nucleos.length;
}

/**
 * Sparkline paths (line and filled area) for values 0–1 in a `ancho × alto` box. The newest sample sits
 * on the right edge and the spacing assumes `capacidad` samples, so the line grows in from the right.
 */
export function rutasSparkline(
  valores: readonly number[],
  ancho: number,
  alto: number,
  capacidad: number,
): { linea: string; area: string } {
  if (valores.length === 0) return { linea: "", area: "" };
  const paso = ancho / Math.max(1, capacidad - 1);
  const ultimo = valores.length - 1;
  let linea = "";
  for (let i = 0; i <= ultimo; i += 1) {
    const x = redondear(ancho - (ultimo - i) * paso);
    const y = redondear(alto - acotar(valores[i]!) * alto);
    linea += `${i === 0 ? "M" : "L"}${x} ${y}`;
  }
  if (ultimo === 0) linea += `L${redondear(ancho)} ${redondear(alto - acotar(valores[0]!) * alto)}`;
  const xInicio = redondear(ancho - ultimo * paso);
  const area = `${linea}L${redondear(ancho)} ${redondear(alto)}L${xInicio} ${redondear(alto)}Z`;
  return { linea, area };
}
