// Spanish number formatting for the charts: decimal comma and narrow no-break (thin) space thousands.
// Done by hand because Intl's es-PE uses a decimal point and comma grouping.

/** Narrow no-break space (U+202F): a thin space that never wraps. */
export const ESPACIO_FINO = " ";
const MENOS = "−";

/** `1234567.891, 2` → `1 234 567,89`. */
export function formatearNumero(valor: number, decimales = 0): string {
  if (!Number.isFinite(valor)) return "—";
  const fijo = Math.abs(valor).toFixed(decimales);
  const [entero = "0", fraccion] = fijo.split(".");
  const agrupado = entero.replace(/\B(?=(\d{3})+(?!\d))/g, ESPACIO_FINO);
  const esCero = Number(fijo) === 0;
  const signo = valor < 0 && !esCero ? MENOS : "";
  return `${signo}${agrupado}${fraccion ? `,${fraccion}` : ""}`;
}

/** Utilisation 0–1 as a whole percentage: `0.724` → `72 %`. */
export function formatearPorcentaje(fraccion: number, decimales = 0): string {
  return `${formatearNumero(fraccion * 100, decimales)}${ESPACIO_FINO}%`;
}

/** `14.63` → `14,6×`. */
export function formatearSpeedup(valor: number): string {
  return `${formatearNumero(valor, 1)}×`;
}

/** Seconds with precision that shrinks as they grow: `3.421` → `3,42 s`, `128.4` → `128 s`. */
export function formatearSegundos(valor: number): string {
  const d = Math.abs(valor) < 10 ? 2 : Math.abs(valor) < 100 ? 1 : 0;
  return `${formatearNumero(valor, d)}${ESPACIO_FINO}s`;
}

/** Compact counts: `1250000` → `1,25 M`, `31250` → `31,3 k`, `950` → `950`. */
export function formatearCompacto(valor: number): string {
  const a = Math.abs(valor);
  if (a >= 1e6) return `${formatearNumero(valor / 1e6, a >= 1e8 ? 0 : 2)}${ESPACIO_FINO}M`;
  if (a >= 1e4) return `${formatearNumero(valor / 1e3, a >= 1e5 ? 0 : 1)}${ESPACIO_FINO}k`;
  return formatearNumero(valor, 0);
}

const SUPERINDICES: Record<string, string> = {
  "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴", "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹", "-": "⁻",
};

/** `4` → `10⁴`. */
export function potenciaDiez(exponente: number): string {
  return `10${String(exponente).split("").map((c) => SUPERINDICES[c] ?? c).join("")}`;
}
