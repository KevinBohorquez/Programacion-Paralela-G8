import { BACKENDS } from "../dominio/eventos";
import { colorBackend } from "../viz/tipos";
import { Plegable } from "../ui/Plegable";
import { useControles } from "./controles";
import f from "./Formulario.module.css";

const ETIQUETAS = { serial: "Serial", openmp: "OpenMP", mpi_estatico: "MPI E1", mpi_dinamico: "MPI E2", hibrido: "Híbrido" };

export function PanelParametros() {
  const { controles, fijar } = useControles();
  return (
    <Plegable.Root porDefecto className={f.panel}>
      <h2>
        <Plegable.Trigger className={f.panelCabecera}>Parámetros</Plegable.Trigger>
      </h2>
      <Plegable.Content className={f.panelCuerpo}>
        <div className={f.rejilla}>
          <label className={f.campo}>
            N escenarios
            <input
              className={f.entrada}
              type="number"
              min={1000}
              step={1_000_000}
              value={controles.n}
              onChange={(e) => fijar({ n: Math.max(1, Math.round(Number(e.target.value) || 1)) })}
            />
          </label>
          <label className={f.campo}>
            Núcleos
            <input
              className={f.entrada}
              type="number"
              min={1}
              max={256}
              value={controles.nucleos}
              onChange={(e) => fijar({ nucleos: Math.min(256, Math.max(1, Math.round(Number(e.target.value) || 1))) })}
            />
          </label>
        </div>
        <label className={f.campo}>
          Configuración de la carrera
          <select
            className={f.entrada}
            value={controles.configCarrera}
            onChange={(e) => fijar({ configCarrera: e.target.value })}
          >
            {controles.configs.length === 0 ? <option value="sintetico">sintetico</option> : null}
            {controles.configs.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id}
              </option>
            ))}
          </select>
        </label>
        <fieldset className={f.casillas}>
          <legend>Backends de la carrera</legend>
          {BACKENDS.map((b) => (
            <label key={b} className={f.casilla}>
              <input
                type="checkbox"
                checked={controles.backends.includes(b)}
                onChange={(e) =>
                  fijar({
                    backends: e.target.checked
                      ? BACKENDS.filter((x) => x === b || controles.backends.includes(x))
                      : controles.backends.filter((x) => x !== b),
                  })
                }
              />
              <i className={f.muestra} style={{ background: colorBackend[b] }} aria-hidden="true" />
              {ETIQUETAS[b]}
            </label>
          ))}
        </fieldset>
        <p className={f.nota}>
          Los backends corren uno tras otro para que el speedup frente al serial sea honesto. Los híbridos sueltos usan
          4 procesos × {Math.max(1, Math.floor(controles.nucleos / 4))} hilos.
        </p>
      </Plegable.Content>
    </Plegable.Root>
  );
}
