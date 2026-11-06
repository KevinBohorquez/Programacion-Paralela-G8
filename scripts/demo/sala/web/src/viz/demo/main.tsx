import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "./harness.css";
import { VizDemo } from "./VizDemo";

// `?tema=claro` or `?tema=oscuro` forces a theme for screenshots; otherwise the OS preference applies.
const tema = new URLSearchParams(window.location.search).get("tema");
if (tema === "claro") document.documentElement.dataset.theme = "light";
if (tema === "oscuro") document.documentElement.dataset.theme = "dark";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <VizDemo />
  </StrictMode>,
);
