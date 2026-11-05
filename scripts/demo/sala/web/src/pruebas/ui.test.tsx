import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { Dialogo } from "../ui/Dialogo";
import { Plegable } from "../ui/Plegable";

function Ejemplo() {
  return (
    <>
      <button type="button">antes</button>
      <Dialogo.Root>
        <Dialogo.Trigger>Abrir</Dialogo.Trigger>
        <Dialogo.Content>
          <Dialogo.Title>Título</Dialogo.Title>
          <button type="button">uno</button>
          <Dialogo.Close>Cerrar</Dialogo.Close>
        </Dialogo.Content>
      </Dialogo.Root>
    </>
  );
}

describe("Dialogo", () => {
  it("is modal, labelled by its title, and traps Tab", async () => {
    const u = userEvent.setup();
    render(<Ejemplo />);
    await u.click(screen.getByRole("button", { name: "Abrir" }));
    const dialogo = screen.getByRole("dialog", { name: "Título" });
    expect(dialogo).toHaveAttribute("aria-modal", "true");
    expect(screen.getByRole("button", { name: "uno" })).toHaveFocus();
    await u.tab();
    expect(screen.getByRole("button", { name: "Cerrar" })).toHaveFocus();
    await u.tab();
    expect(screen.getByRole("button", { name: "uno" })).toHaveFocus();
    await u.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Cerrar" })).toHaveFocus();
  });

  it("closes on Escape and restores focus to the trigger", async () => {
    const u = userEvent.setup();
    render(<Ejemplo />);
    const abrir = screen.getByRole("button", { name: "Abrir" });
    await u.click(abrir);
    expect(abrir).toHaveAttribute("aria-expanded", "true");
    await u.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(abrir).toHaveFocus();
    expect(abrir).toHaveAttribute("aria-expanded", "false");
  });

  it("Escape closes only the topmost of two nested dialogs", async () => {
    const u = userEvent.setup();
    render(
      <Dialogo.Root>
        <Dialogo.Trigger>Exterior</Dialogo.Trigger>
        <Dialogo.Content>
          <Dialogo.Title>Uno</Dialogo.Title>
          <Dialogo.Root>
            <Dialogo.Trigger>Interior</Dialogo.Trigger>
            <Dialogo.Content>
              <Dialogo.Title>Dos</Dialogo.Title>
            </Dialogo.Content>
          </Dialogo.Root>
        </Dialogo.Content>
      </Dialogo.Root>,
    );
    await u.click(screen.getByRole("button", { name: "Exterior" }));
    await u.click(screen.getByRole("button", { name: "Interior" }));
    expect(screen.getAllByRole("dialog")).toHaveLength(2);
    await u.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "Uno" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog", { name: "Dos" })).not.toBeInTheDocument();
  });

  it("closes on a scrim click but not on a click inside", async () => {
    const u = userEvent.setup();
    render(<Ejemplo />);
    await u.click(screen.getByRole("button", { name: "Abrir" }));
    await u.click(screen.getByRole("dialog"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await u.click(screen.getByTestId("velo"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});

describe("Plegable", () => {
  it("toggles aria-expanded and hides its content", async () => {
    const u = userEvent.setup();
    render(
      <Plegable.Root>
        <Plegable.Trigger>Parámetros</Plegable.Trigger>
        <Plegable.Content>contenido</Plegable.Content>
      </Plegable.Root>,
    );
    const disparador = screen.getByRole("button", { name: "Parámetros" });
    expect(disparador).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByText("contenido")).not.toBeVisible();
    expect(disparador.getAttribute("aria-controls")).toBe(screen.getByText("contenido").id);
    await u.click(disparador);
    expect(disparador).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("contenido")).toBeVisible();
    await u.keyboard("{Enter}");
    expect(disparador).toHaveAttribute("aria-expanded", "false");
  });
});
