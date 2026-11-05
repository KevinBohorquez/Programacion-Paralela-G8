/*
 * DEVELOPMENT MOCK — loaded only with ?mock=1. Never the default and never the demo fallback
 * (the fallback is the server's REPLAY mode). Every number here is synthetic and illustrative:
 * round durations, k = 123456, huella 0123456789ab. They are NOT measurements.
 */
(function () {
  'use strict';
  const t0 = performance.now();
  const ahora = () => (performance.now() - t0) / 1000;
  let emitir = () => {};
  const st = { modo: 'vivo', grabando: false, ocupado: false, carga: [], timers: [], seq: 0 };

  const NUCLEOS = 24;
  const N = 1000000;
  const K = 123456;
  const HUELLA = '0123456789ab';
  // Illustrative durations in seconds (deliberately round; speedups are not real).
  const DUR = { serial: 8, openmp: 2, mpi_estatico: 2, mpi_dinamico: 2, hibrido: 2 };
  const ESCALA = 0.5; // mock plays each run in DUR * ESCALA real seconds

  function wilson(k, n, z) {
    z = z || 1.96;
    if (!n) return [0, 1];
    const p = k / n, z2 = z * z;
    const den = 1 + z2 / n;
    const centro = (p + z2 / (2 * n)) / den;
    const semi = (z * Math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / den;
    return [Math.max(0, centro - semi), Math.min(1, centro + semi)];
  }

  function enviar(ev) { emitir(Object.assign({ ts: Number(ahora().toFixed(3)) }, ev)); }
  function despues(seg, fn) { st.timers.push(setTimeout(fn, seg * 1000)); }
  function estado() { enviar({ t: 'estado', modo: st.modo, grabando: st.grabando, ocupado: st.ocupado }); }

  // CPU sampler: background noise plus the cores the current run keeps busy.
  setInterval(() => {
    const nucleos = [];
    for (let i = 0; i < NUCLEOS; i++) {
      const ruido = 0.02 + 0.04 * Math.random();
      const c = st.carga[i] || 0;
      nucleos.push(Math.min(1, c ? c - 0.06 * Math.random() : ruido));
    }
    enviar({ t: 'cpu', nucleos });
  }, 200);

  function cargaPara(b, afinidad) {
    const a = new Array(NUCLEOS).fill(0);
    if (b === 'serial') a[3] = 1;
    else if (b === 'hibrido' && afinidad === 'close') for (let i = 0; i < 6; i++) a[i] = 1; // threads piled up
    else for (let i = 0; i < NUCLEOS; i++) a[i] = 0.97;
    if (b === 'mpi_dinamico') a[0] = 0.15; // master hands out blocks, does not simulate
    return a;
  }

  function correr(b, opts, id, alTerminar) {
    const procesos = { serial: 1, openmp: 1, mpi_estatico: 24, mpi_dinamico: 24, hibrido: 4 }[b];
    const hilos = { serial: 1, openmp: 24, mpi_estatico: 1, mpi_dinamico: 1, hibrido: 6 }[b];
    const afinidad = b === 'hibrido' ? (opts.afinidad || 'false') : '-';
    let dur = DUR[b] * ESCALA;
    if (b === 'hibrido' && afinidad === 'close') dur *= 3;
    const segundos = (b === 'hibrido' && afinidad === 'close') ? DUR[b] * 3 : DUR[b];
    const ts0 = ahora();
    enviar({ t: 'inicio', id, backend: b, procesos, hilos, n: N, afinidad, comando: `(mock) ${b}` });
    st.carga = cargaPara(b, afinidad);
    const pasos = 20;
    if (b === 'mpi_dinamico') {
      const bloque = N / 100;
      for (let j = 0; j < 100; j++) {
        despues(dur * j / 100, () => enviar({ t: 'bloque', id, rango: 1 + (j * 7) % (procesos - 1), i0: j * bloque, i1: (j + 1) * bloque }));
      }
    } else if (procesos > 1) {
      const tramo = N / procesos;
      for (let s = 1; s <= pasos; s++) {
        for (let r = 0; r < procesos; r++) {
          despues(dur * s / pasos, () => enviar({ t: 'avance', id, rango: r, hecho: Math.round(tramo * s / pasos), total: tramo, escenarios_s: Math.round(N / segundos / procesos) }));
        }
      }
    } else {
      for (let s = 1; s <= pasos; s++) {
        despues(dur * s / pasos, () => enviar({ t: 'avance', id, rango: null, hecho: N * s / pasos, total: N, escenarios_s: Math.round(N / segundos) }));
      }
    }
    despues(dur + 0.05, () => {
      st.carga = [];
      let trabajo = null;
      if (b === 'mpi_estatico') trabajo = new Array(procesos).fill(N / procesos);
      if (b === 'mpi_dinamico') trabajo = [0].concat(new Array(procesos - 1).fill(0).map((_, i) => 40000 + ((i * 3) % 7) * 1000));
      enviar({
        t: 'fin', id, segundos, k: K, n: N, p: K / N, wilson: wilson(K, N), huella: HUELLA,
        trabajo_rangos: trabajo, speedup: opts.serialSeg ? opts.serialSeg / segundos : null,
      });
      void ts0;
      alTerminar(segundos);
    });
  }

  function carrera(backends, alFinal) {
    st.ocupado = true; estado();
    const id = 'm' + (++st.seq);
    let serialSeg = null;
    const siguiente = (i) => {
      if (i >= backends.length) { st.ocupado = false; estado(); if (alFinal) alFinal(); return; }
      correr(backends[i], { serialSeg }, `${id}-${backends[i]}`, (seg) => {
        if (backends[i] === 'serial') serialSeg = seg;
        despues(0.6, () => siguiente(i + 1));
      });
    };
    siguiente(0);
    return id;
  }

  function detener() {
    st.timers.forEach(clearTimeout); st.timers = [];
    st.carga = []; st.ocupado = false; st.modo = 'vivo'; estado();
  }

  // ---------------------------------------------------------------- fake HTTP API
  const CONFIGS = [
    { id: 'ejemplo_normal', estacion: 'Estación de ejemplo', regimen: 'normal', c: 6.0, u: 50.0 },
    { id: 'ejemplo_el_nino', estacion: 'Estación de ejemplo', regimen: 'El Niño', c: 6.0, u: 50.0 },
  ];

  function pVerdadera(cfg, c, u) {
    const escala = (cfg.regimen === 'El Niño' ? 60 : 35) * (6 / Math.max(0.5, c));
    return Math.exp(-Math.pow(u / escala, 1.4));
  }

  function riesgo(q) {
    const cfg = CONFIGS.find((x) => x.id === q.get('config')) || CONFIGS[0];
    const c = Number(q.get('c')) || cfg.c;
    const n = 100000;
    const u = [], p = [], lo = [], hi = [];
    for (let i = 0; i <= 150; i++) {
      const uu = i * (cfg.u * 2.5) / 150;
      const pp = pVerdadera(cfg, c, uu);
      const w = wilson(Math.round(pp * n), n);
      u.push(uu); p.push(pp); lo.push(w[0]); hi.push(w[1]);
    }
    return { u, p, lo, hi, n, segundos: 0.5 };
  }

  function convergencia(q) {
    const cfg = CONFIGS.find((x) => x.id === q.get('config')) || CONFIGS[0];
    const pt = Math.max(1e-4, pVerdadera(cfg, Number(q.get('c')) || cfg.c, Number(q.get('u')) || cfg.u));
    const salida = [];
    const ruido = [1.6, -1.1, 0.8, -0.9, 0.5, -0.4, 0.3, -0.2, 0.1];
    for (let e = 0; e <= 8; e++) {
      const n = Math.round(Math.pow(10, 3 + e / 2));
      const sd = Math.sqrt(pt * (1 - pt) / n);
      const k = Math.round(Math.min(1, Math.max(0, pt + ruido[e] * sd)) * n);
      const w = wilson(k, n);
      salida.push({ n, p: k / n, lo: w[0], hi: w[1] });
    }
    return salida;
  }

  function api(metodo, ruta, cuerpo) {
    const url = new URL(ruta, 'http://mock.local');
    const r = (status, data) => new Promise((ok) => setTimeout(() => ok({ status, data }), 80));
    const p = url.pathname;
    if (metodo === 'GET' && p === '/api/configs') return r(200, CONFIGS);
    if (metodo === 'GET' && p === '/api/riesgo') return r(200, riesgo(url.searchParams));
    if (metodo === 'GET' && p === '/api/convergencia') return r(200, convergencia(url.searchParams));
    if (metodo === 'GET' && p === '/api/grabaciones') return r(200, ['ensayo-ejemplo']);
    if (metodo === 'POST' && p === '/api/carrera') {
      if (st.ocupado) return r(409, { error: 'ocupado' });
      return r(200, { carrera: carrera(cuerpo.backends) });
    }
    if (metodo === 'POST' && p === '/api/hibrido') {
      if (st.ocupado) return r(409, { error: 'ocupado' });
      st.ocupado = true; estado();
      const id = `m${++st.seq}-hibrido-${cuerpo.afinidad}`;
      correr('hibrido', { afinidad: cuerpo.afinidad }, id, () => { st.ocupado = false; estado(); });
      return r(200, { id });
    }
    if (metodo === 'POST' && p === '/api/detener') { detener(); return r(200, {}); }
    if (metodo === 'POST' && p === '/api/grabar') { st.grabando = !!cuerpo.activo; estado(); return r(200, {}); }
    if (metodo === 'POST' && p === '/api/replay') {
      if (st.ocupado) return r(409, { error: 'ocupado' });
      st.modo = 'replay';
      carrera(['serial', 'openmp', 'mpi_estatico', 'mpi_dinamico', 'hibrido'], () => { st.modo = 'vivo'; estado(); });
      return r(200, {});
    }
    return r(404, null);
  }

  function fuente(fn) {
    emitir = fn;
    estado();
    // Play one synthetic race on load so the layout can be inspected.
    setTimeout(() => carrera(['serial', 'openmp', 'mpi_estatico', 'mpi_dinamico', 'hibrido']), 800);
  }

  window.SalaMock = { api, fuente };
})();
