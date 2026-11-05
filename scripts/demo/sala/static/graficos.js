/* Dependency-free SVG charts and the heatmap color scale for the control room. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';

  // Cold-to-hot scale: dark water blue -> teal -> amber -> pale yellow (monotone lightness).
  const PARADAS = [
    [0.00, [19, 41, 61]],
    [0.20, [29, 78, 116]],
    [0.45, [47, 127, 158]],
    [0.70, [201, 162, 58]],
    [0.88, [255, 204, 51]],
    [1.00, [255, 241, 184]],
  ];

  function colorCalor(v) {
    v = Math.max(0, Math.min(1, Number(v) || 0));
    let i = 1;
    while (i < PARADAS.length - 1 && v > PARADAS[i][0]) i++;
    const [a, ca] = PARADAS[i - 1];
    const [b, cb] = PARADAS[i];
    const t = b === a ? 0 : (v - a) / (b - a);
    const c = ca.map((x, k) => Math.round(x + (cb[k] - x) * t));
    const fondo = `rgb(${c[0]},${c[1]},${c[2]})`;
    const claro = v >= 0.62; // dark ink on the bright end
    return { fondo, tinta: claro ? '#1a1300' : '#eef5fb', tinta2: claro ? '#4a3a00' : '#a9c3d9' };
  }

  function el(tag, attrs, parent) {
    const n = document.createElementNS(NS, tag);
    for (const k in attrs) n.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(n);
    return n;
  }

  function lienzo(contenedor, margen) {
    contenedor.innerHTML = '';
    const w = Math.max(200, contenedor.clientWidth);
    const h = Math.max(120, contenedor.clientHeight);
    const svg = el('svg', { viewBox: `0 0 ${w} ${h}` }, contenedor);
    const m = Object.assign({ t: 12, r: 14, b: 30, l: 50 }, margen || {});
    return { svg, w, h, m, iw: w - m.l - m.r, ih: h - m.t - m.b };
  }

  function escalaLineal(d0, d1, r0, r1) {
    const k = d1 === d0 ? 0 : (r1 - r0) / (d1 - d0);
    return (x) => r0 + (x - d0) * k;
  }

  function fmtNum(x) {
    if (!isFinite(x)) return '—';
    const a = Math.abs(x);
    if (a >= 1e6) return (x / 1e6).toLocaleString('es', { maximumFractionDigits: 1 }) + ' M';
    if (a >= 1e3) return (x / 1e3).toLocaleString('es', { maximumFractionDigits: 1 }) + ' k';
    return x.toLocaleString('es', { maximumFractionDigits: 2 });
  }

  function fmtP(p) {
    if (!isFinite(p)) return '—';
    if (p === 0) return '0';
    if (p < 0.001) return p.toExponential(2).replace('.', ',');
    return p.toLocaleString('es', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
  }

  function interpolar(xs, ys, x) {
    if (!xs.length) return NaN;
    if (x <= xs[0]) return ys[0];
    if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
    let i = 1;
    while (xs[i] < x) i++;
    const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
    return ys[i - 1] + (ys[i] - ys[i - 1]) * t;
  }

  function ejeY(g, c, y, ticks, fmt) {
    const eje = el('g', { class: 'eje' }, g);
    const rej = el('g', { class: 'rejilla' }, g);
    ticks.forEach((v) => {
      const yy = y(v);
      el('line', { x1: c.m.l, x2: c.m.l + c.iw, y1: yy, y2: yy }, rej);
      const t = el('text', { x: c.m.l - 8, y: yy + 4, 'text-anchor': 'end' }, eje);
      t.textContent = fmt(v);
    });
  }

  /* Exceedance curve P(Amax > u) with its Wilson band and a marker at U. */
  function curvaRiesgo(contenedor, datos, uMarcador) {
    const c = lienzo(contenedor, { l: 54, b: 34 });
    const { svg } = c;
    if (!datos || !datos.u || !datos.u.length) {
      const t = el('text', { x: c.w / 2, y: c.h / 2, 'text-anchor': 'middle', class: 'etiqueta-graf' }, svg);
      t.textContent = 'Sin curva todavía';
      return null;
    }
    const u = datos.u, p = datos.p, lo = datos.lo, hi = datos.hi;
    const x = escalaLineal(u[0], u[u.length - 1], c.m.l, c.m.l + c.iw);
    const y = escalaLineal(0, 1, c.m.t + c.ih, c.m.t);
    ejeY(svg, c, y, [0, 0.25, 0.5, 0.75, 1], (v) => v.toLocaleString('es'));

    const eje = el('g', { class: 'eje' }, svg);
    el('line', { x1: c.m.l, x2: c.m.l + c.iw, y1: c.m.t + c.ih, y2: c.m.t + c.ih }, eje);
    const nt = 5;
    for (let i = 0; i <= nt; i++) {
      const v = u[0] + (u[u.length - 1] - u[0]) * i / nt;
      const t = el('text', { x: x(v), y: c.m.t + c.ih + 20, 'text-anchor': 'middle' }, eje);
      t.textContent = fmtNum(v);
    }
    const tx = el('text', { x: c.m.l + c.iw, y: c.m.t + c.ih + 33, 'text-anchor': 'end' }, eje);
    tx.textContent = 'u';

    let band = '';
    for (let i = 0; i < u.length; i++) band += `${i ? 'L' : 'M'}${x(u[i])},${y(hi[i])}`;
    for (let i = u.length - 1; i >= 0; i--) band += `L${x(u[i])},${y(lo[i])}`;
    el('path', { d: band + 'Z', class: 'banda' }, svg);
    let linea = '';
    for (let i = 0; i < u.length; i++) linea += `${i ? 'L' : 'M'}${x(u[i])},${y(p[i])}`;
    el('path', { d: linea, class: 'curva' }, svg);

    const lectura = {
      p: interpolar(u, p, uMarcador),
      lo: interpolar(u, lo, uMarcador),
      hi: interpolar(u, hi, uMarcador),
    };
    const ux = x(Math.max(u[0], Math.min(u[u.length - 1], uMarcador)));
    el('line', { x1: ux, x2: ux, y1: c.m.t, y2: c.m.t + c.ih, class: 'marcador' }, svg);
    el('circle', { cx: ux, cy: y(lectura.p), r: 6, class: 'marcador-punto' }, svg);
    const etq = el('text', {
      x: ux + (ux > c.m.l + c.iw * 0.75 ? -8 : 8), y: c.m.t + 14,
      'text-anchor': ux > c.m.l + c.iw * 0.75 ? 'end' : 'start', class: 'marcador-texto',
    }, svg);
    etq.textContent = 'U = ' + fmtNum(uMarcador);

    // Hover crosshair with a readout.
    const sonda = el('g', { class: 'sonda', visibility: 'hidden' }, svg);
    const sl = el('line', { y1: c.m.t, y2: c.m.t + c.ih, stroke: '#a9c3d9', 'stroke-width': 1 }, sonda);
    const sr = el('rect', { width: 170, height: 24, rx: 4 }, sonda);
    const st = el('text', {}, sonda);
    const zona = el('rect', { x: c.m.l, y: c.m.t, width: c.iw, height: c.ih, fill: 'transparent' }, svg);
    zona.addEventListener('mousemove', (ev) => {
      const r = svg.getBoundingClientRect();
      const px = (ev.clientX - r.left) * (c.w / r.width);
      const uv = u[0] + (px - c.m.l) / c.iw * (u[u.length - 1] - u[0]);
      const pv = interpolar(u, p, uv);
      sl.setAttribute('x1', px); sl.setAttribute('x2', px);
      const bx = px + 180 > c.w ? px - 178 : px + 8;
      sr.setAttribute('x', bx); sr.setAttribute('y', c.m.t + 22);
      st.setAttribute('x', bx + 8); st.setAttribute('y', c.m.t + 39);
      st.textContent = `u ${fmtNum(uv)} · p ${fmtP(pv)}`;
      sonda.setAttribute('visibility', 'visible');
    });
    zona.addEventListener('mouseleave', () => sonda.setAttribute('visibility', 'hidden'));
    return lectura;
  }

  /* p-hat with Wilson band against N on a log-x axis, with a 1/sqrt(N) guide. */
  function convergencia(contenedor, puntos) {
    const c = lienzo(contenedor, { l: 80, b: 44, r: 24, t: 18 });
    const { svg } = c;
    if (!puntos || !puntos.length) {
      const t = el('text', { x: c.w / 2, y: c.h / 2, 'text-anchor': 'middle', class: 'etiqueta-graf' }, svg);
      t.textContent = 'Sin datos de convergencia';
      return;
    }
    const pts = puntos.slice().sort((a, b) => a.n - b.n);
    const lx0 = Math.floor(Math.log10(pts[0].n));
    const lx1 = Math.ceil(Math.log10(pts[pts.length - 1].n));
    const x = (n) => c.m.l + (Math.log10(n) - lx0) / Math.max(1e-9, lx1 - lx0) * c.iw;
    let ymin = Math.min(...pts.map((d) => d.lo));
    let ymax = Math.max(...pts.map((d) => d.hi));
    const pad = (ymax - ymin) * 0.08 || 0.01;
    ymin = Math.max(0, ymin - pad); ymax = Math.min(1, ymax + pad);
    const y = escalaLineal(ymin, ymax, c.m.t + c.ih, c.m.t);
    const ticks = [];
    for (let i = 0; i <= 4; i++) ticks.push(ymin + (ymax - ymin) * i / 4);
    ejeY(svg, c, y, ticks, fmtP);

    const eje = el('g', { class: 'eje' }, svg);
    el('line', { x1: c.m.l, x2: c.m.l + c.iw, y1: c.m.t + c.ih, y2: c.m.t + c.ih }, eje);
    for (let e = lx0; e <= lx1; e++) {
      const t = el('text', { x: x(Math.pow(10, e)), y: c.m.t + c.ih + 24, 'text-anchor': 'middle' }, eje);
      t.textContent = G_fmt(Math.pow(10, e));
    }
    const tn = el('text', { x: c.m.l + c.iw, y: c.m.t + c.ih + 42, 'text-anchor': 'end' }, eje);
    tn.textContent = 'N escenarios (escala logarítmica)';

    let band = '';
    pts.forEach((d, i) => { band += `${i ? 'L' : 'M'}${x(d.n)},${y(d.hi)}`; });
    for (let i = pts.length - 1; i >= 0; i--) band += `L${x(pts[i].n)},${y(pts[i].lo)}`;
    el('path', { d: band + 'Z', class: 'banda' }, svg);

    // Reference envelope: last p-hat +/- the first half-width scaled by sqrt(n0/n).
    const ult = pts[pts.length - 1];
    const n0 = pts[0].n;
    const hw0 = (pts[0].hi - pts[0].lo) / 2;
    let gs = '', gi = '';
    for (let k = 0; k <= 60; k++) {
      const n = Math.pow(10, Math.log10(n0) + (Math.log10(ult.n) - Math.log10(n0)) * k / 60);
      const hw = hw0 * Math.sqrt(n0 / n);
      gs += `${k ? 'L' : 'M'}${x(n)},${y(Math.min(ymax, ult.p + hw))}`;
      gi += `${k ? 'L' : 'M'}${x(n)},${y(Math.max(ymin, ult.p - hw))}`;
    }
    el('path', { d: gs, class: 'guia' }, svg);
    el('path', { d: gi, class: 'guia' }, svg);
    const tg = el('text', { x: x(n0) + 10, y: y(Math.min(ymax, ult.p + hw0)) + 18, class: 'marcador-texto' }, svg);
    tg.textContent = 'ancho ∝ 1/√N';

    let linea = '';
    pts.forEach((d, i) => { linea += `${i ? 'L' : 'M'}${x(d.n)},${y(d.p)}`; });
    el('path', { d: linea, class: 'curva' }, svg);
    pts.forEach((d) => {
      el('line', { x1: x(d.n), x2: x(d.n), y1: y(d.lo), y2: y(d.hi), class: 'barra-error' }, svg);
      el('circle', { cx: x(d.n), cy: y(d.p), r: 6, class: 'punto-conv' }, svg);
      const hit = el('circle', { cx: x(d.n), cy: y(d.p), r: 18, fill: 'transparent' }, svg);
      const ti = el('title', {}, hit);
      ti.textContent = `N = ${fmtNum(d.n)}\np̂ = ${fmtP(d.p)}\nWilson [${fmtP(d.lo)}, ${fmtP(d.hi)}]`;
    });
  }

  function G_fmt(n) { return fmtNum(n).replace(/,0 /, ' '); }
  window.Graficos = { colorCalor, curvaRiesgo, convergencia, fmtNum, fmtP, interpolar };
})();
