// HTTP API of docs/contrato-sala-control.md §3. With ?mock=1 the dev mock answers instead of fetch.
export interface Respuesta<T = unknown> {
  status: number;
  data: T | null;
}

export type Transporte = (metodo: string, ruta: string, cuerpo?: unknown) => Promise<Respuesta>;

export const MOCK = typeof location !== "undefined" && new URLSearchParams(location.search).get("mock") === "1";

const porFetch: Transporte = async (metodo, ruta, cuerpo) => {
  const init: RequestInit = { method: metodo, headers: {} };
  if (cuerpo !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(cuerpo);
  }
  const r = await fetch(ruta, init);
  let data: unknown = null;
  try {
    data = await r.json();
  } catch {
    /* empty body */
  }
  return { status: r.status, data };
};

const transporte: Promise<Transporte> = MOCK
  ? import("../mock/reproductor").then((m) => m.apiMock)
  : Promise.resolve(porFetch);

export async function llamar<T>(metodo: string, ruta: string, cuerpo?: unknown): Promise<Respuesta<T>> {
  const t = await transporte;
  return (await t(metodo, ruta, cuerpo)) as Respuesta<T>;
}

export type Avisar = (texto: string, tono?: "neutral" | "peligro" | "exito") => void;

/** Calls an endpoint from an event handler; 409 and failures become toasts, success returns data. */
export async function accion<T>(avisar: Avisar, metodo: string, ruta: string, cuerpo?: unknown): Promise<T | null> {
  try {
    const r = await llamar<T>(metodo, ruta, cuerpo);
    if (r.status === 409) {
      avisar("Hay una corrida en curso", "peligro");
      return null;
    }
    if (r.status >= 400) {
      const detalle = (r.data as { error?: string } | null)?.error;
      avisar(detalle ? `Error ${r.status}: ${detalle}` : `El servidor respondió ${r.status} en ${ruta}`, "peligro");
      return null;
    }
    return r.data;
  } catch {
    avisar(`Sin respuesta del servidor en ${ruta}`, "peligro");
    return null;
  }
}
