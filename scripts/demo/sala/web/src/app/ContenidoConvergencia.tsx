// Lazy-loaded body of the Convergencia dialog: one /api/convergencia request per opening.
import { useEffect, useState } from "react";
import { fmtCompacto, fmtDecimal, fmtEntero, fmtP, fmtSegundos } from "../dominio/formato";
import { accion } from "../sala/api";
import { useAvisar } from "../ui/Avisos";
import { GraficoConvergencia } from "../viz/GraficoConvergencia";
import { useControles } from "./controles";
import s from "./ContenidoConvergencia.module.css";

interface Punto {
  n: number;
  k?: number;
  p: number;
  lo: number;
  hi: number;
  segundos?: number;
}

const NS = "1000,10000,100000,1000000,10000000";

export default function ContenidoConvergencia() {
  const avisar = useAvisar();
  const { controles } = useControles();
  const { configRiesgo, c, u, configs } = controles;
  const [puntos, setPuntos] = useState<Punto[] | null>(null);
  const [fallo, setFallo] = useState(false);
  const config = configs.find((x) => x.id === configRiesgo);

  useEffect(() => {
    if (!configRiesgo) return;
    let vigente = true;
    const q = new URLSearchParams({ config: configRiesgo, c: String(c), u: String(u), ns: NS });
    void accion<Punto[]>(avisar, "GET", `/api/convergencia?${q}`).then((d) => {
      if (!vigente) return;
      if (Array.isArray(d)) setPuntos([...d].sort((a, b) => a.n - b.n));
      else setFallo(true);
    });
    return () => {
      vigente = false;
    };
  }, [avisar, configRiesgo, c, u]);

  const contexto = config
    ? `${config.estacion} · ${config.regimen.replace("_", " ")}, C = ${fmtDecimal(c)}, U = ${fmtDecimal(u)} mm`
    : "Sin configuración elegida";

  return (
    <div className={s.contenido}>
      <p className={s.sub}>
        {contexto}.{" "}
        {puntos
          ? "La banda de Wilson se estrecha como 1/√N: cada ×100 en N la reduce unas 10 veces."
          : fallo
            ? "No se pudo calcular la convergencia."
            : "Calculando con N = 10³ … 10⁷…"}
      </p>
      <div className={s.grafico}>
        <GraficoConvergencia puntos={puntos ?? []} />
      </div>
      {puntos ? (
        <table className={`${s.tabla} tnum`}>
          <thead>
            <tr>
              <th scope="col">N</th>
              <th scope="col">k</th>
              <th scope="col">p̂</th>
              <th scope="col">Wilson 95 %</th>
              <th scope="col">semiancho</th>
              <th scope="col">tiempo</th>
            </tr>
          </thead>
          <tbody>
            {puntos.map((p) => (
              <tr key={p.n}>
                <td>{fmtCompacto(p.n)}</td>
                <td>{fmtEntero(p.k)}</td>
                <td>{fmtP(p.p)}</td>
                <td>
                  [{fmtP(p.lo)}, {fmtP(p.hi)}]
                </td>
                <td>±{fmtP((p.hi - p.lo) / 2)}</td>
                <td>{fmtSegundos(p.segundos)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </div>
  );
}
