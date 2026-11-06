/**
 * Escape closes the TOPMOST layer only. Every dialog pushes its close handler while open; one
 * document listener calls the last one pushed and claims the key, so nested layers close in order.
 */
type Manejador = () => void;

const capas: Manejador[] = [];

function alTeclear(e: KeyboardEvent): void {
  if (e.key !== "Escape" || e.defaultPrevented) return;
  const tope = capas[capas.length - 1];
  if (!tope) return;
  e.preventDefault();
  tope();
}

export function apilarCapaEscape(m: Manejador): () => void {
  if (capas.length === 0) document.addEventListener("keydown", alTeclear);
  capas.push(m);
  return () => {
    const i = capas.lastIndexOf(m);
    if (i !== -1) capas.splice(i, 1);
    if (capas.length === 0) document.removeEventListener("keydown", alTeclear);
  };
}
