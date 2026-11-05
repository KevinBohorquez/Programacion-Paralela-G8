// Centre card. It is the only component that subscribes to the 5 Hz cpu samples.
import { memo } from "react";
import { nombreCorrida, terminada, type EstadoSala } from "../dominio/estado";
import { fmtDecimal } from "../dominio/formato";
import { useSala } from "../sala/instancia";
import { MapaNucleos } from "../viz/MapaNucleos";
import t from "../ui/Tarjeta.module.css";
import s from "./PanelNucleos.module.css";

const selCpu = (e: EstadoSala) => e.cpu;
const selEnCurso = (e: EstadoSala) => {
  const c = e.corridas.find((x) => !terminada(x));
  return c ? nombreCorrida(c) : null;
};

const Mapa = memo(function Mapa({ etiqueta }: { etiqueta?: string }) {
  const nucleos = useSala(selCpu);
  return <MapaNucleos nucleos={nucleos} etiqueta={etiqueta} />;
});

function Total() {
  const nucleos = useSala(selCpu);
  const suma = nucleos.reduce((a, x) => a + Math.max(0, Math.min(1, x)), 0);
  const pct = nucleos.length ? Math.round((suma / nucleos.length) * 100) : null;
  return (
    <div className={s.total}>
      <span className={`${s.totalValor} tnum`}>{pct === null ? "—" : `${pct} %`}</span>
      <span className={`${s.totalSub} tnum`}>
        {nucleos.length
          ? `≈ ${fmtDecimal(suma, 1)} de ${nucleos.length} núcleos ocupados`
          : "esperando muestras de CPU…"}
      </span>
    </div>
  );
}

export function PanelNucleos() {
  const enCurso = useSala(selEnCurso);
  return (
    <section className={`${t.tarjeta} ${s.panel}`} aria-labelledby="titulo-nucleos">
      <header className={t.cabecera}>
        <h2 id="titulo-nucleos" className={t.titulo}>
          Uso de núcleos
        </h2>
        <span className={s.enCurso}>{enCurso ? `En curso: ${enCurso}` : "En reposo"}</span>
        <Total />
      </header>
      <div className={s.mapa}>
        <Mapa etiqueta={enCurso ?? undefined} />
      </div>
    </section>
  );
}
