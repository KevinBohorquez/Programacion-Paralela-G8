/*
 * DEVELOPMENT MOCK, loaded only with ?mock=1 and badged MOCK in the UI. It is never the default and
 * never the demo fallback (that is the server's REPLAY mode). Every number here is ILLUSTRATIVE:
 * round durations, k = 123456, huella 0123456789ab, a made-up risk curve. They are not measurements.
 */
import type { Fuente } from "../sala/almacen";
import type { Respuesta, Transporte } from "../sala/api";
import type { Evento } from "../dominio/eventos";
import type { Backend } from "../viz/tipos";

const NUCLEOS = 24;
const N = 1_000_000;
const K = 123_456;
const HUELLA = "0123456789ab";
/** Illustrative seconds per backend (deliberately round; the speedups they imply are not real). */
const DURACION: Record<Backend, number> = { serial: 8, openmp: 1, mpi_estatico: 1.2, mpi_dinamico: 1.1, hibrido: 1 };
const ESCALA = 0.5; // the mock plays each run in DURACION * ESCALA real seconds

const t0 = performance.now();
const ahora = () => Number(((performance.now() - t0) / 1000).toFixed(3));
let emitir: (e: Evento) => void = () => {};
const st = { modo: "vivo" as "vivo" | "replay", grabando: false, ocupado: false, carga: [] as number[], seq: 0 };
let temporizadores: number[] = [];

function enviar(e: Evento) {
  emitir({ ...e, ts: ahora() } as Evento);
}
function despues(seg: number, f: () => void) {
  temporizadores.push(window.setTimeout(f, seg * 1000));
}
function estado() {
  enviar({ t: "estado", modo: st.modo, grabando: st.grabando, ocupado: st.ocupado });
}

export function wilson(k: number, n: number, z = 1.959963984540054): [number, number] {
  if (!n) return [0, 1];
  const p = k / n;
  const z2 = z * z;
  const den = 1 + z2 / n;
  const centro = (p + z2 / (2 * n)) / den;
  const mitad = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / den;
  return [Math.max(0, centro - mitad), Math.min(1, centro + mitad)];
}

function reparto(b: Backend, nucleos = NUCLEOS, afinidad = "-") {
  if (b === "openmp") return { procesos: 1, hilos: nucleos, afinidad };
  if (b === "mpi_estatico" || b === "mpi_dinamico") return { procesos: nucleos, hilos: 1, afinidad };
  if (b === "hibrido") return { procesos: 4, hilos: nucleos / 4, afinidad: afinidad === "-" ? "false" : afinidad };
  return { procesos: 1, hilos: 1, afinidad };
}

function correr(id: string, b: Backend, afinidad: string, alTerminar: () => void, conSpeedup: boolean) {
  const r = reparto(b, NUCLEOS, afinidad);
  const error = b === "hibrido" && r.afinidad === "close";
  const dur = DURACION[b] * (error ? 3.5 : 1) * ESCALA;
  const comando =
    b === "serial"
      ? "pp_serial --n 1000000 --config sintetico --progreso (mock)"
      : `mpirun -np ${r.procesos} … --n 1000000 --progreso (mock)`;
  enviar({ t: "inicio", id, backend: b, procesos: r.procesos, hilos: r.hilos, n: N, afinidad: r.afinidad, comando });
  // Cores the run keeps busy; the affinity error piles every thread on the first 6 cores.
  const ocupados = b === "serial" ? 1 : error ? 6 : NUCLEOS;
  st.carga = Array.from({ length: NUCLEOS }, (_, i) => (i < ocupados ? 0.95 : 0));
  const pasos = 20;
  for (let i = 1; i <= pasos; i++) {
    despues((dur * i) / pasos, () => {
      const hecho = Math.round((N * i) / pasos);
      if (b === "mpi_estatico" || b === "hibrido") {
        for (let rg = 0; rg < r.procesos; rg++) {
          const tramo = N / r.procesos;
          enviar({ t: "avance", id, rango: rg, hecho: Math.round((tramo * i) / pasos), total: tramo, escenarios_s: hecho / ((dur * i) / pasos) });
        }
      } else if (b === "mpi_dinamico") {
        const bloque = N / pasos;
        const rango = 1 + ((i * 7) % (r.procesos - 1));
        enviar({ t: "bloque", id, rango, i0: (i - 1) * bloque, i1: i * bloque });
      } else {
        enviar({ t: "avance", id, rango: null, hecho, total: N, escenarios_s: hecho / ((dur * i) / pasos) });
      }
    });
  }
  despues(dur + 0.05, () => {
    const segundos = DURACION[b] * (error ? 3.5 : 1);
    const trabajo =
      b === "mpi_estatico"
        ? Array.from({ length: r.procesos }, () => N / r.procesos)
        : b === "mpi_dinamico"
          ? Array.from({ length: r.procesos }, (_, i) => (i === 0 ? 0 : Math.round((N / (r.procesos - 1)) * (0.9 + 0.2 * ((i * 37) % 10) / 10))))
          : null;
    enviar({
      t: "fin",
      id,
      backend: b,
      segundos,
      segundos_pared: segundos + 0.2,
      k: K,
      n: N,
      p: K / N,
      wilson: wilson(K, N),
      huella: HUELLA,
      trabajo_rangos: trabajo,
      speedup: conSpeedup ? DURACION.serial / segundos : null,
    });
    st.carga = [];
    alTerminar();
  });
}

function carrera(backends: Backend[], alFinal?: () => void) {
  const c = `c${++st.seq}`;
  st.ocupado = true;
  estado();
  const siguiente = (i: number) => {
    if (i >= backends.length) {
      st.ocupado = false;
      if (alFinal) alFinal();
      estado();
      return;
    }
    correr(`${c}-${backends[i]}`, backends[i], "-", () => siguiente(i + 1), true);
  };
  siguiente(0);
  return c;
}

function curvaRiesgo(c: number) {
  // Illustrative exceedance curve: shifts left as drainage capacity C grows.
  const escala = 30 + 4 * c;
  const u: number[] = [];
  const p: number[] = [];
  const lo: number[] = [];
  const hi: number[] = [];
  const n = 100_000;
  for (let x = 1; x <= 300; x++) {
    const px = Math.exp(-x / escala) * 0.6;
    const k = Math.round(px * n);
    const [a, b] = wilson(k, n);
    u.push(x);
    p.push(k / n);
    lo.push(a);
    hi.push(b);
    if (k === 0) break;
  }
  return { u, p, lo, hi, n, segundos: 0.4, c, umbral: 50 };
}

const ok = (data: unknown): Respuesta => ({ status: 200, data });
const ocupado = (): Respuesta => ({ status: 409, data: { error: "ya hay una corrida en curso (mock)" } });

export const apiMock: Transporte = async (metodo, ruta, cuerpo) => {
  const [camino, consulta] = ruta.split("?");
  const q = new URLSearchParams(consulta ?? "");
  const d = (cuerpo ?? {}) as Record<string, unknown>;
  await new Promise((r) => setTimeout(r, 120));
  if (metodo === "GET" && camino === "/api/configs") {
    return ok([
      { id: "sintetico", estacion: "sintetica", regimen: "normal", c: 6, u: 50 },
      { id: "piura_bernal_el_nino", estacion: "Bernal (mock)", regimen: "el_nino", c: 8, u: 60 },
      { id: "piura_bernal_normal", estacion: "Bernal (mock)", regimen: "normal", c: 8, u: 60 },
      { id: "tumbes_eltigre_el_nino", estacion: "El Tigre (mock)", regimen: "el_nino", c: 10, u: 80 },
    ]);
  }
  if (metodo === "GET" && camino === "/api/estado") return ok({ t: "estado", modo: st.modo, grabando: st.grabando, ocupado: st.ocupado });
  if (metodo === "GET" && camino === "/api/riesgo") return ok(curvaRiesgo(Number(q.get("c") ?? 6)));
  if (metodo === "GET" && camino === "/api/convergencia") {
    const ns = (q.get("ns") ?? "1000,10000,100000,1000000,10000000").split(",").map(Number);
    await new Promise((r) => setTimeout(r, 900));
    return ok(
      ns.map((n, i) => {
        const p = 0.12 + 0.02 / Math.sqrt(i + 1) * (i % 2 ? 1 : -1);
        const k = Math.round(p * n);
        const [lo, hi] = wilson(k, n);
        return { n, k, p: k / n, lo, hi, segundos: n / 4e6 };
      }),
    );
  }
  if (metodo === "GET" && camino === "/api/grabaciones") {
    return ok([
      { nombre: "ensayo", bytes: 182_344, eventos: 1_204 },
      { nombre: "ensayo-hibrido", bytes: 64_120, eventos: 433 },
    ]);
  }
  if (metodo === "POST" && camino === "/api/carrera") {
    if (st.ocupado) return ocupado();
    return ok({ carrera: carrera((d.backends as Backend[]) ?? ["serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido"]) });
  }
  if (metodo === "POST" && camino === "/api/hibrido") {
    if (st.ocupado) return ocupado();
    const af = String(d.afinidad ?? "false");
    const id = `h${++st.seq}-${af}`;
    st.ocupado = true;
    estado();
    correr(id, "hibrido", af, () => {
      st.ocupado = false;
      estado();
    }, false);
    return ok({ id });
  }
  if (metodo === "POST" && camino === "/api/detener") {
    temporizadores.forEach(clearTimeout);
    temporizadores = [];
    st.carga = [];
    const habia = st.ocupado;
    st.ocupado = false;
    st.modo = "vivo";
    estado();
    return ok({ detenido: habia });
  }
  if (metodo === "POST" && camino === "/api/grabar") {
    st.grabando = d.activo !== false;
    estado();
    return ok(st.grabando ? { grabando: true, archivo: "results/demo/sala/ensayo-mock.jsonl" } : { grabando: false });
  }
  if (metodo === "POST" && camino === "/api/replay") {
    if (st.ocupado) return ocupado();
    st.modo = "replay";
    carrera(["serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido"], () => {
      st.modo = "vivo";
    });
    return ok({ eventos: 120, duracion_s: 7 });
  }
  return { status: 404, data: { error: "no encontrado (mock)" } };
};

export const fuenteMock: Fuente = {
  conectar(e, conexion) {
    emitir = e;
    conexion("abierta");
    estado();
    const cpu = window.setInterval(() => {
      const nucleos = Array.from({ length: NUCLEOS }, (_, i) => {
        const ruido = 0.02 + 0.04 * Math.random();
        const c = st.carga[i] ?? 0;
        return Math.min(1, c ? c - 0.05 * Math.random() : ruido);
      });
      enviar({ t: "cpu", nucleos });
    }, 200);
    // Start an illustrative race so the screen is never empty while developing.
    despues(0.8, () => carrera(["serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido"]));
    return () => {
      clearInterval(cpu);
      temporizadores.forEach(clearTimeout);
      emitir = () => {};
    };
  },
};
