import { nombreCorrida, veredictoIdentidad, type EstadoSala } from "../dominio/estado";
import { fmtEntero, fmtP } from "../dominio/formato";
import { useSala } from "../sala/instancia";
import { IconoAlerta, IconoCheck } from "../ui/iconos";
import { colorBackend } from "../viz/tipos";
import s from "./FranjaIdentidad.module.css";

const selCorridas = (e: EstadoSala) => e.corridas;

export function FranjaIdentidad() {
  const corridas = useSala(selCorridas);
  const terminadas = corridas.filter((c) => c.fin);
  const v = veredictoIdentidad(corridas);
  const distintas = v.tipo === "distintos" ? new Set(v.distintas) : new Set<string>();

  return (
    <section className={s.franja} aria-labelledby="titulo-identidad">
      <div className={s.titulo}>
        <h2 id="titulo-identidad">V1 · Identidad de resultados</h2>
        <p className={s.nota}>Mismo k y misma huella del histograma en todos los backends</p>
      </div>
      <div className={s.celdas}>
        {terminadas.length === 0 ? (
          <p className={s.vacio}>Aquí aparecen k, p̂ y la huella de cada backend al terminar.</p>
        ) : (
          terminadas.map((c) => (
            <div
              key={c.id}
              className={s.celda}
              data-distinta={distintas.has(c.id)}
              style={{ "--color": colorBackend[c.backend] } as React.CSSProperties}
            >
              <span className={s.nombre}>{nombreCorrida(c)}</span>
              <span className={`${s.fila} tnum`}>
                <span>k</span>
                <b>{fmtEntero(c.fin!.k)}</b>
              </span>
              <span className={`${s.fila} tnum`}>
                <span>p̂</span>
                <b>{fmtP(c.fin!.p)}</b>
              </span>
              <span className={s.fila}>
                <span>huella</span>
                <b className={s.huella}>{c.fin!.huella}</b>
              </span>
            </div>
          ))
        )}
      </div>
      <div className={s.veredicto} data-tipo={v.tipo} role="status">
        {v.tipo === "identicos" ? (
          <>
            <IconoCheck className={s.icono} />
            <span>
              <b>Resultados idénticos</b>
              <small className="tnum">{v.corridas} backends · mismo k y huella</small>
            </span>
          </>
        ) : v.tipo === "distintos" ? (
          <>
            <IconoAlerta className={s.icono} />
            <span>
              <b>Resultados distintos</b>
              <small className="tnum">{v.distintas.length} de {v.corridas} no coinciden</small>
            </span>
          </>
        ) : (
          <span>
            <b>{v.corridas === 0 ? "Esperando resultados" : "Falta otro backend"}</b>
            <small>{v.corridas === 0 ? "—" : "para comparar"}</small>
          </span>
        )}
      </div>
    </section>
  );
}
