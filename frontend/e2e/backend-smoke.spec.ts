import { expect, test } from "@playwright/test";
import path from "node:path";
test("compiled frontend against isolated real FastAPI, YOLO and CUDA", async ({
  page,
  request,
}) => {
  const runtime = await (await request.get("/runtime")).json();
  expect(runtime.model_loaded).toBe(true);
  await page.goto("/");
  await expect(
    page.getByText("Sistema conectado", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Buscar cámaras" }).click();
  await page.getByLabel("Fuente de cámara").selectOption("demo");
  await page
    .getByLabel("Dispositivo de inferencia")
    .selectOption(runtime.cuda_available ? "cuda" : "cpu");
  await page
    .getByRole("button", { name: "Iniciar cámara", exact: true })
    .click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/camera/status")).json()).frames_processed,
      { timeout: 30000 },
    )
    .toBeGreaterThan(2);
  expect((await (await request.get("/stats")).json()).total_inspected).toBe(0);
  await expect(
    page.getByRole("img", {
      name: "Vista previa de la cámara USB con detecciones",
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Capturar e inspeccionar", exact: true })
    .click();
  await expect(
    page.getByText(
      "Inspección registrada. Imágenes disponibles para descargar.",
    ),
  ).toBeVisible({ timeout: 30000 });
  await expect
    .poll(
      async () => (await (await request.get("/stats")).json()).total_inspected,
    )
    .toBe(1);
  const original = await page
    .getByRole("link", { name: "Imagen original" })
    .getAttribute("href");
  expect((await request.get(original!)).status()).toBe(200);
  const state = await (await request.get("/camera/status")).json();
  expect(state.inference_device).toBe(
    runtime.cuda_available ? "cuda:0" : "cpu",
  );
  await page.getByLabel("Umbral de confianza", { exact: true }).fill("0.65");
  await page.getByRole("button", { name: "Aplicar umbral en vivo" }).click();
  await expect
    .poll(
      async () =>
        (await (await request.get("/camera/status")).json()).confidence,
    )
    .toBe(0.65);
  await page.evaluate(() => { window.scrollTo(0, 0); if(document.activeElement instanceof HTMLElement) document.activeElement.blur(); });
  await page.screenshot({
    path: path.resolve("../outputs/frontend-redesign/real-stack-demo.png"),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Detener", exact: true }).click();
  await expect
    .poll(
      async () => (await (await request.get("/camera/status")).json()).running,
    )
    .toBe(false);
  if (await page.getByRole("button", { name: "Abrir navegación" }).isVisible())
    await page.getByRole("button", { name: "Abrir navegación" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: "Historial", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Ver inspección 1", exact: true }),
  ).toBeVisible();
});
