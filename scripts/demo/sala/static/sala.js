/* Control room client: SSE stream, HTTP API, and rendering (contract: docs/contrato-sala-control.md). */
(function () {
  'use strict';
  const G = window.Graficos;
  const $ = (s) => document.querySelector(s);
  const MOCK = new URLSearchParams(location.search).get('mock') === '1';

  const NOMBRES = {
    serial: 'Serial',
    openmp: 'OpenMP',
    mpi_estatico: 'MPI E1 estático',
    mpi_dinamico: 'MPI E2 dinámico',
    hibrido: 'Híbrido MPI+OpenMP',
  };

  const estado = {
    modo: 'vivo', grabando: false, ocupado: false,
    corridas: new Map(),   // id -> run state, in arrival order
    cpu: null, cpuPendiente: false,
    configs: [], curva: null, riesgoTimer: 0,
  };

  // ---------------------------------------------------------------- transport
  let mockApi = null;

  async function api(metodo, ruta, cuerpo) {
    if (mockApi) return mockApi(metodo, ruta, cuerpo);
    const opts = { method: metodo, headers: {} };
    if (cuerpo !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(cuerpo);
    }
    const r = await fetch(ruta, opts);
    let data = null;
    try { data = await r.json(); } catch (_) { /* empty body */ }
    return { status: r.status, data };
  }

  async function accion(metodo, ruta, cuerpo) {
    try {
      const r = await api(metodo, ruta, cuerpo);
      if (r.status === 409) { toast('Hay una corrida en curso', true); return null; }
      if (r.status >= 400) { toast(`El servidor respondió ${r.status} en ${ruta}`, true); return null; }
      return r.data;
    } catch (e) {
      toast(`Sin respuesta del servidor en ${ruta}`, true);
      return null;
    }
  }

  function conectar() {
    if (MOCK) {
      window.SalaMock.fuente(manejar);
      return;
    }
    let espera = 1000;
    const abrir = () => {
      const es = new EventSource('/api/stream');
      es.onopen = () => { espera = 1000; $('#badge-conexion').hidden = true; };
      es.onmessage = (ev) => {
        let d;
        try { d = JSON.parse(ev.data); } catch (_) { return; }
        manejar(d);
      };
      es.onerror = () => {
        $('#badge-conexion').hidden = false;
        if (es.readyState === EventSource.CLOSED) {
          setTimeout(abrir, espera);
          espera = Math.min(espera * 2, 10000);
        }
        // CONNECTING: the browser retries on its own.
      };
    };
    abrir();
  }

  // ---------------------------------------------------------------- events
  function manejar(d) {
    switch (d.t) {
      case 'cpu': estado.cpu = d.nucleos; programarCpu(); break;
      case 'estado': aplicarEstado(d); break;
      case 'inicio': alIniciar(d); break;
      case 'avance': alAvanzar(d); break;
      case 'bloque': alBloque(d); break;
      case 'fin': alTerminar(d); break;
      case 'error': alError(d); break;
      default: break;
    }
  }

  function aplicarEstado(d) {
    estado.modo = d.modo; estado.grabando = !!d.grabando; estado.ocupado = !!d.ocupado;
    const b = $('#badge-modo');
    b.textContent = d.modo === 'replay' ? 'REPLAY' : 'VIVO';
    b.classList.toggle('replay', d.modo === 'replay');
    b.classList.toggle('ocupado', estado.ocupado);
    $('#badge-rec').hidden = !estado.grabando;
    const g = $('#btn-grabar');
    g.textContent = estado.grabando ? 'Parar grabación' : 'Grabar';
    g.classList.toggle('activo', estado.grabando);
  }

  // Lanes are keyed by backend + affinity, so "híbrido con error" and "corregido" sit side by side.
  const clave = (c) => c.backend + (c.backend === 'hibrido' ? ':' + c.afinidad : '');

  function alIniciar(d) {
    const k = clave(d);
    const repetido = [...estado.corridas.values()].some((c) => clave(c) === k && c.terminada);
    const enCurso = [...estado.corridas.values()].some((c) => !c.terminada);
    if (repetido && !enCurso) {
      // A standalone hybrid run only replaces its own lane, so "con error" and "corregido"
      // stay next to the race; any other repeated backend starts a fresh race.
      if (d.backend === 'hibrido') {
        [...estado.corridas.entries()].forEach(([id, c]) => { if (clave(c) === k) estado.corridas.delete(id); });
      } else {
        estado.corridas.clear();
      }
    }
    const c = {
      id: d.id, backend: d.backend, procesos: d.procesos, hilos: d.hilos, n: d.n,
      afinidad: d.afinidad, ts0: d.ts,
      rangos: new Map(), hechoSolo: null, totalSolo: null, tasa: null, estimado: false,
      bloques: new Map(), asignado: 0, fin: null, error: null, terminada: false, nodo: null,
    };
    estado.corridas.set(d.id, c);
    renderCarriles();
    renderIdentidad();
    mostrarCarril(c);
  }

  // With six or more lanes the column scrolls; keep the lane that is running (or just finished) on screen.
  function mostrarCarril(c) {
    const cont = $('#carriles');
    if (!c.nodo || !cont) return;
    const arriba = c.nodo.offsetTop - cont.offsetTop;
    const abajo = arriba + c.nodo.offsetHeight;
    if (abajo > cont.scrollTop + cont.clientHeight) cont.scrollTop = abajo - cont.clientHeight;
    else if (arriba < cont.scrollTop) cont.scrollTop = arriba;
  }

  function alAvanzar(d) {
    const c = estado.corridas.get(d.id);
    if (!c) return;
    if (d.rango === null || d.rango === undefined) { c.hechoSolo = d.hecho; c.totalSolo = d.total; }
    else c.rangos.set(d.rango, { hecho: d.hecho, total: d.total });
    if (typeof d.escenarios_s === 'number') c.tasa = d.escenarios_s;
    c.estimado = d.estimado === true;
    c.ts = d.ts;
    actualizarCarril(c);
  }

  function alBloque(d) {
    const c = estado.corridas.get(d.id);
    if (!c) return;
    c.bloques.set(d.rango, (c.bloques.get(d.rango) || 0) + 1);
    c.asignado += Math.max(0, d.i1 - d.i0);
    c.ts = d.ts;
    actualizarCarril(c);
    const tile = c.nodo && c.nodo.querySelector(`.rango[data-r="${d.rango}"]`);
    if (tile) {
      tile.classList.remove('destello');
      void tile.offsetWidth; // restart the animation
      tile.classList.add('destello');
    }
  }

  function alTerminar(d) {
    const c = estado.corridas.get(d.id);
    if (!c) return;
    c.fin = d; c.terminada = true;
    renderCarril(c);
    renderIdentidad();
    mostrarCarril(c);
  }

  function alError(d) {
    const c = estado.corridas.get(d.id);
    if (c) { c.error = d.mensaje; c.terminada = true; renderCarril(c); }
    toast(`Error en ${d.id}: ${d.mensaje}`, true);
  }

  // ---------------------------------------------------------------- heatmap
  function programarCpu() {
    if (estado.cpuPendiente) return;
    estado.cpuPendiente = true;
    requestAnimationFrame(() => { estado.cpuPendiente = false; renderCpu(); });
  }

  // Displayed values ease toward the latest sample so the heatmap moves smoothly between events.
  let celdas = [];
  let mostrado = [];
  let animando = false;
  function renderCpu() {
    const v = estado.cpu || [];
    // If frames are throttled (background tab, power saving), never show stale values.
    if (mostrado.length !== v.length || performance.now() - ultimoPintado > 400) {
      mostrado = v.slice();
      pintarCpu(mostrado);
    }
    if (!animando) { animando = true; requestAnimationFrame(paso); }
  }
  let tAnterior = 0;
  function paso(t) {
    const v = estado.cpu || [];
    const dt = tAnterior ? Math.min(0.1, (t - tAnterior) / 1000) : 0.016;
    tAnterior = t;
    const a = 1 - Math.exp(-dt / 0.12);
    let resta = false;
    for (let i = 0; i < v.length; i++) {
      const d = v[i] - mostrado[i];
      mostrado[i] += Math.abs(d) < 0.004 ? d : d * a;
      if (mostrado[i] !== v[i]) resta = true;
    }
    pintarCpu(mostrado);
    if (resta) requestAnimationFrame(paso);
    else { animando = false; tAnterior = 0; }
  }
  let ultimoPintado = 0;
  function pintarCpu(v) {
    ultimoPintado = performance.now();
    const cont = $('#calor');
    if (celdas.length !== v.length) {
      cont.innerHTML = '';
      const r = cont.getBoundingClientRect();
      const aspecto = r.height > 0 ? r.width / r.height : 1.5;
      const cols = Math.max(1, Math.ceil(Math.sqrt(v.length * aspecto)));
      cont.style.setProperty('--cols', cols);
      celdas = v.map((_, i) => {
        const n = document.createElement('div');
        n.className = 'nucleo';
        n.innerHTML = `<span class="nucleo-id">CPU ${i}</span><span class="nucleo-pct">0 %</span>`;
        cont.appendChild(n);
        return { n, pct: n.lastChild };
      });
    }
    let suma = 0;
    v.forEach((x, i) => {
      const f = Math.max(0, Math.min(1, x));
      suma += f;
      const col = G.colorCalor(f);
      const c = celdas[i];
      c.n.style.backgroundColor = col.fondo;
      c.n.style.setProperty('--tinta', col.tinta);
      c.n.style.setProperty('--tinta-2', col.tinta2);
      c.pct.textContent = Math.round(f * 100) + ' %';
      c.n.title = `CPU ${i}: ${(f * 100).toFixed(1)} %`;
    });
    if (v.length) {
      $('#cpu-total').textContent = Math.round((suma / v.length) * 100) + ' %';
      $('#cpu-total-sub').textContent = `uso total · ≈ ${suma.toFixed(1).replace('.', ',')} de ${v.length} núcleos ocupados`;
    }
  }

  // ---------------------------------------------------------------- race lanes
  function progreso(c) {
    if (c.terminada && c.fin) return 1;
    if (c.rangos.size) {
      let h = 0, t = 0;
      c.rangos.forEach((r) => { h += r.hecho; t += r.total; });
      return Math.min(1, h / Math.max(c.n || t, 1));
    }
    if (c.totalSolo) return Math.min(1, c.hechoSolo / c.totalSolo);
    if (c.asignado && c.n) return Math.min(1, c.asignado / c.n);
    return 0;
  }

  function tasa(c) {
    if (c.rangos.size && c.ts && c.ts0 !== undefined && c.ts > c.ts0) {
      let h = 0;
      c.rangos.forEach((r) => { h += r.hecho; });
      return h / (c.ts - c.ts0);
    }
    if (c.tasa !== null) return c.tasa;
    if (c.asignado && c.ts > c.ts0) return c.asignado / (c.ts - c.ts0);
    return null;
  }

  function confTexto(c) {
    const partes = [];
    if (c.procesos > 1) partes.push(`${c.procesos} procesos`);
    if (c.hilos > 1) partes.push(`${c.hilos} hilos`);
    if (c.afinidad && c.afinidad !== '-') partes.push(`bind ${c.afinidad}`);
    partes.push(`N ${G.fmtNum(c.n)}`);
    return partes.join(', ');
  }

  function renderCarriles() {
    const cont = $('#carriles');
    cont.innerHTML = '';
    if (!estado.corridas.size) {
      cont.innerHTML = '<p class="vacio-grande">Pulsa «Carrera» para lanzar los backends uno tras otro.</p>';
      return;
    }
    estado.corridas.forEach((c) => {
      c.nodo = document.createElement('article');
      c.nodo.className = 'carril';
      c.nodo.dataset.b = c.backend;
      cont.appendChild(c.nodo);
      renderCarril(c);
    });
  }

  function renderCarril(c) {
    if (!c.nodo) return;
    let titulo = NOMBRES[c.backend] || c.backend;
    if (c.backend === 'hibrido' && c.afinidad === 'close') titulo += ' · con error';
    if (c.backend === 'hibrido' && c.afinidad === 'false') titulo += ' · corregido';
    let rangos = '';
    if (c.backend === 'mpi_dinamico' && c.procesos > 0) {
      rangos = '<div class="rangos">';
      for (let r = 0; r < c.procesos; r++) {
        rangos += r === 0
          ? '<span class="rango maestro" data-r="0">r0 maestro (no simula)</span>'
          : `<span class="rango" data-r="${r}">r${r}<b>${c.bloques.get(r) || 0}</b></span>`;
      }
      rangos += '</div>';
    }
    let trabajo = '';
    const tr = c.fin && Array.isArray(c.fin.trabajo_rangos) ? c.fin.trabajo_rangos : null;
    if (tr && tr.length) {
      const max = Math.max(...tr, 1);
      trabajo = '<div class="trabajo" title="Escenarios simulados por rango">' + tr.map((w, i) =>
        `<i class="trabajo-barra" style="height:${Math.max(4, (w / max) * 100)}%" title="rango ${i}: ${w.toLocaleString('es')} escenarios"></i>`).join('') +
        `</div><span class="trabajo-etq">Trabajo por rango (${tr.length} rangos): mín ${G.fmtNum(Math.min(...tr))}, máx ${G.fmtNum(max)} escenarios</span>`;
    }
    c.nodo.innerHTML = `
      <div class="carril-cab">
        <span class="carril-nombre">${titulo}</span>
        <span class="carril-conf">${confTexto(c)}</span>
        <span class="carril-estado"></span>
      </div>
      <div class="pista"><div class="pista-relleno"></div></div>
      <div class="carril-datos">
        <span class="dato"><span class="dato-val v-tasa">—</span><span class="dato-etq">escenarios/s</span></span>
        <span class="dato"><span class="dato-val v-seg">—</span><span class="dato-etq">tiempo</span></span>
        <span class="dato dato-speedup"><span class="dato-val v-sp">—</span><span class="dato-etq">speedup</span></span>
      </div>
      ${rangos}${trabajo}`;
    actualizarCarril(c);
  }

  function actualizarCarril(c) {
    const n = c.nodo;
    if (!n) return;
    const pr = progreso(c);
    n.classList.toggle('hecho', !!c.fin);
    n.classList.toggle('error', !!c.error);
    n.classList.toggle('estimado', c.estimado && !c.fin);
    n.querySelector('.pista-relleno').style.width = (pr * 100).toFixed(1) + '%';
    let est;
    if (c.error) est = 'error';
    else if (c.fin) est = 'terminado';
    else est = (c.estimado ? 'estimado ' : '') + Math.round(pr * 100) + ' %';
    n.querySelector('.carril-estado').textContent = est;
    const ts = c.fin && c.fin.segundos > 0 ? c.fin.n / c.fin.segundos : tasa(c);
    n.querySelector('.v-tasa').textContent = ts ? G.fmtNum(ts) : '—';
    if (c.fin) {
      n.querySelector('.v-seg').textContent = c.fin.segundos.toLocaleString('es', { maximumFractionDigits: 2 }) + ' s';
      n.querySelector('.v-sp').textContent = typeof c.fin.speedup === 'number'
        ? c.fin.speedup.toLocaleString('es', { maximumFractionDigits: 2 }) + '×' : '—';
    }
    if (c.bloques.size) {
      c.bloques.forEach((k, r) => {
        const b = n.querySelector(`.rango[data-r="${r}"] b`);
        if (b) b.textContent = k;
      });
    }
  }

  // ---------------------------------------------------------------- identity strip
  function renderIdentidad() {
    const fin = [...estado.corridas.values()].filter((c) => c.fin);
    const cont = $('#identidad');
    const v = $('#veredicto');
    if (!fin.length) {
      cont.innerHTML = '<p class="vacio">Aquí aparece k, p̂ y la huella de cada backend al terminar.</p>';
      v.className = 'veredicto veredicto-espera';
      v.innerHTML = '<span class="veredicto-icono">—</span><span class="veredicto-texto">Esperando resultados</span>';
      return;
    }
    const ref = fin[0].fin;
    const iguales = fin.every((c) => c.fin.k === ref.k && c.fin.huella === ref.huella && c.fin.n === ref.n);
    cont.innerHTML = fin.map((c) => {
      const f = c.fin;
      const distinta = f.k !== ref.k || f.huella !== ref.huella;
      let nombre = NOMBRES[c.backend] || c.backend;
      if (c.backend === 'hibrido') nombre = c.afinidad === 'close' ? 'Híbrido con error' : 'Híbrido corregido';
      return `<div class="celda${distinta ? ' distinta' : ''}" data-b="${c.backend}">
        <span class="celda-nombre">${nombre}</span>
        <span class="celda-fila"><span>k</span><b>${f.k.toLocaleString('es')}</b></span>
        <span class="celda-fila"><span>p̂</span><b>${G.fmtP(f.p)}</b></span>
        <span class="celda-fila huella"><span>huella</span><b>${f.huella}</b></span>
      </div>`;
    }).join('');
    if (fin.length < 2) {
      v.className = 'veredicto veredicto-espera';
      v.innerHTML = '<span class="veredicto-icono">—</span><span class="veredicto-texto">Falta otro backend<br>para comparar</span>';
    } else if (iguales) {
      v.className = 'veredicto veredicto-ok';
      v.innerHTML = `<span class="veredicto-icono">✓</span><span class="veredicto-texto">Resultados idénticos<br><small>${fin.length} backends</small></span>`;
    } else {
      v.className = 'veredicto veredicto-mal';
      v.innerHTML = '<span class="veredicto-icono">✗</span><span class="veredicto-texto">Resultados distintos</span>';
    }
  }

  // ---------------------------------------------------------------- risk explorer
  function configActual() {
    return estado.configs.find((c) => c.id === $('#r-config').value);
  }

  async function cargarConfigs() {
    const data = await accion('GET', '/api/configs');
    if (!Array.isArray(data)) return;
    estado.configs = data;
    $('#r-config').innerHTML = data.map((c) =>
      `<option value="${c.id}">${c.estacion} · ${c.regimen}</option>`).join('');
    $('#p-config-carrera').innerHTML = '<option value="sintetico">sintetico</option>' +
      data.map((c) => `<option value="${c.id}">${c.id}</option>`).join('');
    aplicarConfig();
  }

  function aplicarConfig() {
    const c = configActual();
    if (!c) return;
    const rc = $('#r-c'), ru = $('#r-u');
    rc.max = Math.max(1, c.c * 2); rc.step = c.c * 2 / 100; rc.value = c.c;
    ru.max = Math.max(1, c.u * 2.5); ru.step = c.u * 2.5 / 200; ru.value = c.u;
    mostrarDeslizadores();
    pedirRiesgo(0);
  }

  function mostrarDeslizadores() {
    $('#r-c-val').textContent = G.fmtNum(Number($('#r-c').value));
    $('#r-u-val').textContent = G.fmtNum(Number($('#r-u').value));
  }

  function pedirRiesgo(retardo) {
    clearTimeout(estado.riesgoTimer);
    estado.riesgoTimer = setTimeout(async () => {
      const c = configActual();
      if (!c) return;
      const q = new URLSearchParams({ config: c.id, c: $('#r-c').value });
      $('#r-meta').textContent = 'Calculando curva…';
      const data = await accion('GET', '/api/riesgo?' + q);
      if (!data) { $('#r-meta').textContent = 'No se pudo calcular la curva.'; return; }
      estado.curva = data;
      $('#r-meta').textContent = `Curva con N = ${G.fmtNum(data.n)} escenarios, calculada en ${Number(data.segundos).toLocaleString('es', { maximumFractionDigits: 2 })} s. Banda: intervalo de Wilson al 95 %.`;
      dibujarRiesgo();
    }, retardo);
  }

  function dibujarRiesgo() {
    const u = Number($('#r-u').value);
    const l = G.curvaRiesgo($('#graf-riesgo'), estado.curva, u);
    if (l) {
      $('#r-p').textContent = G.fmtP(l.p);
      $('#r-ic').textContent = `Wilson [${G.fmtP(l.lo)}, ${G.fmtP(l.hi)}]`;
    }
  }

  // ---------------------------------------------------------------- convergence
  async function abrirConvergencia() {
    const c = configActual();
    $('#modal-conv').hidden = false;
    $('#conv-cerrar').focus();
    if (!c) { $('#conv-sub').textContent = 'No hay configuraciones cargadas.'; return; }
    $('#conv-sub').textContent = `${c.estacion} · ${c.regimen}, C = ${G.fmtNum(Number($('#r-c').value))}, U = ${G.fmtNum(Number($('#r-u').value))}. Calculando…`;
    const q = new URLSearchParams({ config: c.id, c: $('#r-c').value, u: $('#r-u').value });
    const data = await accion('GET', '/api/convergencia?' + q);
    if (!Array.isArray(data)) { $('#conv-sub').textContent = 'No se pudo calcular la convergencia.'; return; }
    $('#conv-sub').textContent = `${c.estacion} · ${c.regimen}, C = ${G.fmtNum(Number($('#r-c').value))}, U = ${G.fmtNum(Number($('#r-u').value))}. La banda de Wilson se estrecha como 1/√N: cada ×100 en N la reduce unas 10 veces.`;
    const filas = data.slice().sort((a, b) => a.n - b.n);
    $('#conv-tabla').innerHTML = '<tr><th>N</th><th>p̂</th><th>Wilson inferior</th><th>Wilson superior</th><th>semiancho</th></tr>' +
      filas.map((d) => `<tr><td>${G.fmtNum(d.n)}</td><td>${G.fmtP(d.p)}</td><td>${G.fmtP(d.lo)}</td><td>${G.fmtP(d.hi)}</td><td>${G.fmtP((d.hi - d.lo) / 2)}</td></tr>`).join('');
    estado.convDatos = data;
    G.convergencia($('#graf-conv'), data);
  }

  // ---------------------------------------------------------------- replay menu
  async function abrirReplay() {
    const menu = $('#menu-replay');
    const abierto = !menu.hidden;
    menu.hidden = abierto;
    $('#btn-replay').setAttribute('aria-expanded', String(!abierto));
    if (abierto) return;
    const lista = $('#lista-grabaciones');
    lista.innerHTML = '<li class="vacio">Cargando…</li>';
    const data = await accion('GET', '/api/grabaciones');
    const items = Array.isArray(data) ? data : [];
    if (!items.length) { lista.innerHTML = '<li class="vacio">No hay grabaciones. Usa «Grabar» durante un ensayo.</li>'; return; }
    lista.innerHTML = '';
    items.forEach((it) => {
      const nombre = typeof it === 'string' ? it : (it.nombre || it.id || String(it));
      const li = document.createElement('li');
      const b = document.createElement('button');
      b.className = 'btn';
      b.textContent = 'Reproducir ' + nombre;
      b.onclick = async () => {
        menu.hidden = true;
        $('#btn-replay').setAttribute('aria-expanded', 'false');
        await accion('POST', '/api/replay', { nombre, velocidad: Number($('#replay-velocidad').value) });
      };
      li.appendChild(b);
      lista.appendChild(li);
    });
  }

  // ---------------------------------------------------------------- toasts
  function toast(texto, mal) {
    const t = document.createElement('div');
    t.className = 'toast' + (mal ? ' mal' : '');
    t.textContent = texto;
    $('#toasts').appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  // ---------------------------------------------------------------- wiring
  function nValor() { return Math.max(1, Math.round(Number($('#p-n').value) || 20000000)); }

  function enlazar() {
    $('#btn-carrera').onclick = () => {
      const backends = [...document.querySelectorAll('.backends input:checked')].map((i) => i.value);
      if (!backends.length) { toast('Elige al menos un backend', true); return; }
      accion('POST', '/api/carrera', {
        backends, n: nValor(),
        nucleos: Math.max(1, Math.round(Number($('#p-nucleos').value) || 24)),
        config: $('#p-config-carrera').value,
      });
    };
    $('#btn-hib-error').onclick = () => accion('POST', '/api/hibrido', { procesos: 4, hilos: 6, afinidad: 'close', n: nValor() });
    $('#btn-hib-ok').onclick = () => accion('POST', '/api/hibrido', { procesos: 4, hilos: 6, afinidad: 'false', n: nValor() });
    $('#btn-detener').onclick = () => accion('POST', '/api/detener');
    $('#btn-grabar').onclick = () => accion('POST', '/api/grabar', {
      activo: !estado.grabando, nombre: ($('#p-grabacion').value || 'ensayo').trim(),
    });
    $('#btn-replay').onclick = abrirReplay;
    $('#btn-convergencia').onclick = abrirConvergencia;
    $('#conv-cerrar').onclick = () => { $('#modal-conv').hidden = true; };
    $('#modal-conv').onclick = (e) => { if (e.target.id === 'modal-conv') $('#modal-conv').hidden = true; };
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') { $('#modal-conv').hidden = true; $('#menu-replay').hidden = true; }
    });
    $('#r-config').onchange = aplicarConfig;
    $('#r-c').oninput = () => { mostrarDeslizadores(); pedirRiesgo(300); };
    $('#r-u').oninput = () => { mostrarDeslizadores(); dibujarRiesgo(); };
    let rt = 0;
    window.addEventListener('resize', () => {
      clearTimeout(rt);
      rt = setTimeout(() => {
        dibujarRiesgo();
        celdas = []; pintarCpu(mostrado);
        if (!$('#modal-conv').hidden && estado.convDatos) G.convergencia($('#graf-conv'), estado.convDatos);
      }, 150);
    });
  }

  function cargarScript(src) {
    return new Promise((ok, mal) => {
      const s = document.createElement('script');
      s.src = src; s.onload = ok; s.onerror = mal;
      document.body.appendChild(s);
    });
  }

  async function iniciar() {
    if (MOCK) {
      await cargarScript('mock.js');
      mockApi = window.SalaMock.api;
      $('#badge-mock').hidden = false;
      document.title = 'MOCK · Sala de control';
    }
    enlazar();
    renderIdentidad();
    conectar();
    cargarConfigs();
  }

  iniciar();
})();
