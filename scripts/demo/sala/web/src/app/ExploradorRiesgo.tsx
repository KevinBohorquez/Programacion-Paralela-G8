import { useDeferredValue, useEffect, useState } from "react";
import { fmtDecimal, fmtEntero, fmtP } from "../dominio/formato";
import { accion, llamar } from "../sala/api";
import { useSala } from "../sala/instancia";
import { useAvisar } from "../ui/Avisos";
import { Plegable } from "../ui/Plegable";
import { CurvaRiesgo } from "../viz/CurvaRiesgo";
import { configPreferida, useControles, type Config } from "./controles";
import f from "./Formulario.module.css";

interface Curva {
  u: number[];
  p: number[];
  lo: number[];
  hi: number[];
  n: number;
  segundos: number;
  c?: number;
  umbral?: number;
}

type EstadoCurva =
  | { tipo: "cargando" }
  | { tipo: "lista"; curva: Curva; clave: string }
  | { tipo: "ocupado" }
  | { tipo: "fallo" };

/** P(Amax > U) read from the curve; u starts at 1 mm and the curve ends at its first zero. */
export function leerCurva(curva: Curva, umbral: number): { p: number; lo: number; hi: number } | null {
  if (!curva.u.length) return null;
  const i = curva.u.findIndex((u) => u >= umbral);
  const j = i === -1 ? curva.u.length - 1 : i;
  return { p: curva.p[j], lo: curva.lo[j], hi: curva.hi[j] };
}

function rangos(cfg: Config | undefined) {
  const c = cfg?.c ?? 6;
  const u = cfg?.u ?? 50;
  return { cMax: Math.max(1, c * 2), cPaso: Math.max(c * 2, 1) / 100, uMax: Math.max(10, Math.round(u * 2.5)) };
}

export function ExploradorRiesgo() {
  const avisar = useAvisar();
  const { controles, fijar } = useControles();
  const { configs, configRiesgo, c, u } = controles;
  const ocupado = useSala((s) => s.ocupado);
  const [estado, setEstado] = useState<EstadoCurva>({ tipo: "cargando" });
  // The slider moves at pointer speed; the simulator query follows the deferred value.
  const cDiferido = useDeferredValue(c);
  const cfg = configs.find((x) => x.id === configRiesgo);
  const esperaLibre = estado.tipo === "ocupado";

  useEffect(() => {
    let vigente = true;
    void accion<Config[]>(avisar, "GET", "/api/configs").then((d) => {
      if (!vigente || !Array.isArray(d) || !d.length) return;
      const pref = configPreferida(d);
      fijar({ configs: d, configRiesgo: pref?.id ?? "", c: pref?.c ?? 0, u: pref?.u ?? 0 });
    });
    return () => {
      vigente = false;
    };
  }, [avisar, fijar]);

  useEffect(() => {
    if (!configRiesgo) return;
    // A 409 means a run holds the cores: wait for `ocupado` to clear, then ask again.
    if (esperaLibre && ocupado) return;
    let vigente = true;
    const t = window.setTimeout(() => {
      setEstado((e) => (e.tipo === "lista" ? e : { tipo: "cargando" }));
      const q = new URLSearchParams({ config: configRiesgo, c: String(cDiferido) });
      llamar<Curva>("GET", `/api/riesgo?${q}`)
        .then((r) => {
          if (!vigente) return;
          if (r.status === 409) setEstado({ tipo: "ocupado" });
          else if (r.status === 200 && r.data) setEstado({ tipo: "lista", curva: r.data, clave: q.toString() });
          else setEstado({ tipo: "fallo" });
        })
        .catch(() => vigente && setEstado({ tipo: "fallo" }));
    }, 250);
    return () => {
      vigente = false;
      clearTimeout(t);
    };
  }, [configRiesgo, cDiferido, esperaLibre, esperaLibre ? ocupado : false]);

  const { cMax, cPaso, uMax } = rangos(cfg);
  const curva = estado.tipo === "lista" ? estado.curva : null;
  const lectura = curva ? leerCurva(curva, u) : null;
  const desfasada = c !== cDiferido;

  return (
    <Plegable.Root porDefecto className={f.panel}>
      <h2>
        <Plegable.Trigger className={f.panelCabecera}>Explorador de riesgo</Plegable.Trigger>
      </h2>
      <Plegable.Content className={f.panelCuerpo}>
        <label className={f.campo}>
          Estación y régimen
          <select
            className={f.entrada}
            value={configRiesgo}
            onChange={(e) => {
              const nueva = configs.find((x) => x.id === e.target.value);
              if (nueva) fijar({ configRiesgo: nueva.id, c: nueva.c, u: nueva.u });
            }}
          >
            {configs.length === 0 ? <option value="">Cargando…</option> : null}
            {configs.map((x) => (
              <option key={x.id} value={x.id}>
                {x.estacion} · {x.regimen.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>
        <label className={f.campo}>
          <span className={f.campoCabecera}>
            Capacidad de drenaje C<output className={f.valor}>{fmtDecimal(c)}</output>
          </span>
          <input
            className={f.deslizador}
            type="range"
            min={0}
            max={cMax}
            step={cPaso}
            value={c}
            onChange={(e) => fijar({ c: Number(e.target.value) })}
          />
        </label>
        <label className={f.campo}>
          <span className={f.campoCabecera}>
            Umbral U<output className={f.valor}>{fmtEntero(u)} mm</output>
          </span>
          <input
            className={f.deslizador}
            type="range"
            min={1}
            max={uMax}
            step={1}
            value={u}
            onChange={(e) => fijar({ u: Number(e.target.value) })}
          />
        </label>
        <div className={f.lectura} aria-live="off" style={{ opacity: desfasada ? 0.6 : 1 }}>
          <span className={f.lecturaEtiqueta}>P(Amax &gt; U)</span>
          <span className={f.lecturaValor}>{lectura ? fmtP(lectura.p) : "—"}</span>
          <span className={f.lecturaIntervalo}>
            {lectura ? `Wilson 95 % [${fmtP(lectura.lo)}, ${fmtP(lectura.hi)}]` : " "}
          </span>
        </div>
        <div className={f.grafico}>
          <CurvaRiesgo u={curva?.u ?? []} p={curva?.p ?? []} lo={curva?.lo ?? []} hi={curva?.hi ?? []} umbral={u} alto={220} />
        </div>
        <p className={f.nota}>
          {estado.tipo === "cargando"
            ? "Calculando curva…"
            : estado.tipo === "ocupado"
              ? "Hay una corrida en curso: la curva se recalcula al terminar."
              : estado.tipo === "fallo"
                ? "No se pudo calcular la curva."
                : `N = ${fmtEntero(estado.curva.n)} · ${fmtDecimal(estado.curva.segundos)} s · banda de Wilson 95 %`}
        </p>
      </Plegable.Content>
    </Plegable.Root>
  );
}
