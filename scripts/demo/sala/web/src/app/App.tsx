import { useEffect } from "react";
import { almacen, arrancar } from "../sala/instancia";
import { ProveedorAvisos, useAvisar } from "../ui/Avisos";
import { BarraSuperior } from "./BarraSuperior";
import { ProveedorControles } from "./controles";
import { ExploradorRiesgo } from "./ExploradorRiesgo";
import { FranjaIdentidad } from "./FranjaIdentidad";
import { PanelCarrera } from "./PanelCarrera";
import { PanelNucleos } from "./PanelNucleos";
import { PanelParametros } from "./PanelParametros";
import s from "./App.module.css";

/** Run errors arrive on the stream; surface each one as a toast. */
function AvisosDeErrores() {
  const avisar = useAvisar();
  useEffect(
    () => almacen.alError((e) => avisar(e.id ? `Error en ${e.id}: ${e.mensaje}` : e.mensaje, "peligro")),
    [avisar],
  );
  return null;
}

export function App() {
  useEffect(arrancar, []);
  return (
    <ProveedorAvisos>
      <ProveedorControles>
        <AvisosDeErrores />
        <div className={s.app}>
          <BarraSuperior />
          <main className={s.rejilla}>
            <aside className={s.izquierda} aria-label="Parámetros y explorador de riesgo">
              <PanelParametros />
              <ExploradorRiesgo />
            </aside>
            <PanelNucleos />
            <PanelCarrera />
            <div className={s.abajo}>
              <FranjaIdentidad />
            </div>
          </main>
        </div>
      </ProveedorControles>
    </ProveedorAvisos>
  );
}
