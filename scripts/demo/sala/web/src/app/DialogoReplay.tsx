import { useState, type ReactNode } from "react";
import { fmtEntero } from "../dominio/formato";
import { accion } from "../sala/api";
import { Boton } from "../ui/Boton";
import { Dialogo } from "../ui/Dialogo";
import { useAvisar } from "../ui/Avisos";
import { IconoPlay } from "../ui/iconos";
import s from "./DialogoReplay.module.css";

interface Grabacion {
  nombre: string;
  bytes?: number;
  eventos?: number;
}

interface Props {
  children: ReactNode;
  nombreGrabacion: string;
  alCambiarNombre: (n: string) => void;
}

export function DialogoReplay({ children, nombreGrabacion, alCambiarNombre }: Props) {
  const avisar = useAvisar();
  const [abierto, setAbierto] = useState(false);
  const [lista, setLista] = useState<Grabacion[] | null>(null);
  const [velocidad, setVelocidad] = useState("1");

  const alCambiar = (v: boolean) => {
    setAbierto(v);
    if (!v) return;
    setLista(null);
    void accion<Grabacion[]>(avisar, "GET", "/api/grabaciones").then((d) => setLista(Array.isArray(d) ? d : []));
  };

  const reproducir = async (nombre: string) => {
    const r = await accion(avisar, "POST", "/api/replay", { nombre, velocidad: Number(velocidad) });
    if (r) {
      avisar(`Reproduciendo «${nombre}» a ${velocidad.replace(".", ",")}×`, "exito");
      setAbierto(false);
    }
  };

  return (
    <Dialogo.Root abierto={abierto} alCambiar={alCambiar}>
      <Dialogo.Trigger variante="fantasma">{children}</Dialogo.Trigger>
      <Dialogo.Content descripcion="Reproduce por el mismo stream una grabación de ensayo con sus tiempos originales.">
        <Dialogo.Header>
          <Dialogo.Title>Grabaciones y replay</Dialogo.Title>
          <Dialogo.Close />
        </Dialogo.Header>
        <p className={s.nota}>
          El replay emite los eventos grabados por el mismo stream, con sus tiempos. Es el respaldo si el simulador no
          puede correr en vivo; la barra muestra «REPLAY» mientras dura.
        </p>
        <div className={s.campos}>
          <label className={s.campo}>
            <span>Nombre para «Grabar»</span>
            <input
              className={s.entrada}
              value={nombreGrabacion}
              maxLength={64}
              pattern="[A-Za-z0-9_.\-]+"
              onChange={(e) => alCambiarNombre(e.target.value)}
            />
          </label>
          <label className={s.campo}>
            <span>Velocidad</span>
            <select className={s.entrada} value={velocidad} onChange={(e) => setVelocidad(e.target.value)}>
              <option value="0.5">0,5×</option>
              <option value="1">1×</option>
              <option value="2">2×</option>
              <option value="4">4×</option>
            </select>
          </label>
        </div>
        {lista === null ? (
          <p className={s.nota}>Cargando grabaciones…</p>
        ) : lista.length === 0 ? (
          <p className={s.nota}>No hay grabaciones. Usa «Grabar» durante un ensayo.</p>
        ) : (
          <ul className={s.lista}>
            {lista.map((g) => (
              <li key={g.nombre} className={s.fila}>
                <span className={s.nombre}>{g.nombre}</span>
                <span className={`${s.meta} tnum`}>
                  {g.eventos !== undefined ? `${fmtEntero(g.eventos)} eventos` : ""}
                  {g.bytes !== undefined ? ` · ${fmtEntero(Math.round(g.bytes / 1024))} KB` : ""}
                </span>
                <Boton onClick={() => void reproducir(g.nombre)}>
                  <IconoPlay />
                  Reproducir
                </Boton>
              </li>
            ))}
          </ul>
        )}
      </Dialogo.Content>
    </Dialogo.Root>
  );
}
