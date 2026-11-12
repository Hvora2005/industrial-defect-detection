import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";

const image =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/l1sAAAAASUVORK5CYII=";
const detection = {
  status: "FAIL",
  defects_found: 2,
  severity: "MAJOR",
  defects: [
    { class_name: "patches", confidence: 74.7, severity: "MAJOR" },
    { class_name: "scratches", confidence: 68.2, severity: "MINOR" },
  ],
  annotated_image: image,
  inference_device: "cuda:0",
  inference_ms: 18.4,
  processing_fps: 27.2,
  captures: {
    original_url: "/captures/fixture_original.jpg",
    annotated_url: "/captures/fixture_annotated.jpg",
  },
};
const history = Array.from({ length: 22 }, (_, i) => ({
  id: 220 - i,
  timestamp: `2026-11-11T${String(20 - Math.floor(i / 5)).padStart(2, "0")}:${String((i * 2) % 60).padStart(2, "0")}:00Z`,
  status: i % 5 === 0 ? "NO_DETECTIONS" : "FAIL",
  defects_found: i % 5 === 0 ? 0 : 2,
  primary_defect: i % 5 === 0 ? null : i % 3 === 0 ? "scratches" : "patches",
  primary_confidence: i % 5 === 0 ? null : 74.7,
  severity: i % 5 === 0 ? null : "MAJOR",
}));
const stats = {
  total_inspected: 220,
  fail_count: 164,
  no_detections_count: 54,
  pass_count: 2,
  defect_rate: 74.5,
  avg_confidence: 78.4,
  most_common_defect: "patches",
  defect_distribution: {
    patches: 146,
    scratches: 84,
    inclusion: 38,
    crazing: 21,
    pitted_surface: 12,
    "rolled-in_scale": 7,
  },
  severity_distribution: { MINOR: 82, MAJOR: 76, CRITICAL: 6 },
};
async function fixtures(
  page: Page,
  { empty = false, offline = false, missing = false } = {},
) {
  const plate = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 800;
    canvas.height = 500;
    const c = canvas.getContext("2d")!;
    c.fillStyle = "#18242c";
    c.fillRect(0, 0, 800, 500);
    const gradient = c.createLinearGradient(0, 0, 800, 500);
    gradient.addColorStop(0, "#849498");
    gradient.addColorStop(0.5, "#c5ced0");
    gradient.addColorStop(1, "#596d77");
    c.fillStyle = gradient;
    c.fillRect(70, 60, 660, 360);
    c.strokeStyle = "#657d86";
    c.lineWidth = 5;
    c.beginPath();
    c.moveTo(260, 125);
    c.lineTo(310, 330);
    c.lineTo(390, 285);
    c.stroke();
    c.strokeStyle = "#d3b07a";
    c.lineWidth = 2;
    c.strokeRect(220, 95, 220, 270);
    c.font = "15px sans-serif";
    c.fillStyle = "#e9d1ab";
    c.fillText("Manchas o parches · 74.7%", 220, 85);
    c.fillStyle = "#22343e";
    c.font = "16px sans-serif";
    c.fillText("Fixture visual sintética · no inferencia real", 90, 400);
    return canvas.toDataURL("image/jpeg").split(",")[1];
  });
  let state = {
    state: "stopped",
    running: false,
    frames_processed: 0,
    inspections_recorded: 0,
    confidence: 0.4,
    requested_device: "auto",
    source: "0",
    source_type: "camera",
    requested: { width: 640, height: 480, fps: 30 },
    effective: { width: 640, height: 480, fps: 30 },
    frame_width: 640,
    frame_height: 480,
    inference_device: "cuda:0",
    inference_ms: 18.4,
    processing_fps: 27.2,
  };
  const calls: { path: string; body: Record<string, unknown> }[] = [];
  let lost = false;
  const receipts = new Set<string>();
  await page.routeWebSocket("**/ws/monitor", () => {});
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    const name = url.pathname;
    if (
      ![
        "/health",
        "/runtime",
        "/stats",
        "/history",
        "/trend",
        "/cameras",
        "/camera/status",
        "/camera/start",
        "/camera/stop",
        "/camera/settings",
        "/camera/capture",
        "/camera/stream",
        "/preview",
        "/detect",
        "/upload",
      ].includes(name)
    )
      return route.continue();
    if (offline) return route.abort("connectionrefused");
    const body = route
      .request()
      .headers()
      ["content-type"]?.includes("application/json")
      ? (route.request().postDataJSON() as Record<string, unknown>)
      : {};
    calls.push({ path: name, body });
    let data: unknown = {};
    if (name === "/health")
      data = {
        status: "ok",
        model_loaded: !missing,
        classes: [
          "patches",
          "scratches",
          "inclusion",
          "crazing",
          "pitted_surface",
          "rolled-in_scale",
        ],
      };
    if (name === "/runtime")
      data = {
        cuda_available: true,
        gpus: [
          {
            index: 0,
            name: "NVIDIA GeForce RTX 4050 Laptop GPU",
            memory_mb: 6141,
          },
        ],
        model_loaded: !missing,
        torch_version: "fixture",
        cuda_runtime: "13.0",
        requested_device: "auto",
        active_device: "cuda:0",
      };
    if (name === "/stats")
      data = empty
        ? {
            ...stats,
            total_inspected: 0,
            fail_count: 0,
            no_detections_count: 0,
            pass_count: 0,
            defect_rate: 0,
            avg_confidence: null,
            defect_distribution: {},
            severity_distribution: {},
          }
        : stats;
    if (name === "/history") data = { inspections: empty ? [] : history };
    if (name === "/trend")
      data = {
        buckets: empty
          ? []
          : [2, 4, 3, 6, 5, 8, 4, 5].map((n, i) => ({
              time: `18:${String(i * 5).padStart(2, "0")}`,
              fail: n,
              no_detections: Math.max(1, 6 - n),
              pass: 0,
            })),
      };
    if (name === "/cameras")
      data = {
        cameras: [
          { index: 0, name: "Camera 0" },
          { index: 2, name: "Camera 2" },
        ],
        demo_available: true,
      };
    if (name === "/camera/start") {
      state = {
        ...state,
        state: "running",
        running: true,
        requested_device: String(body.device),
        confidence: Number(body.conf),
        source: String(body.camera_index),
        frames_processed: 10,
      };
      data = state;
    }
    if (name === "/camera/stop") {
      state = { ...state, state: "stopped", running: false };
      data = state;
    }
    if (name === "/camera/settings") {
      state.confidence = Number(body.conf);
      data = state;
    }
    if (name === "/camera/status") data = state;
    if (name === "/camera/capture") {
      const id = String(body.request_id);
      const duplicate = receipts.has(id);
      receipts.add(id);
      state.inspections_recorded = receipts.size;
      if (!lost) {
        lost = true;
        await route.abort("connectionreset");
        return;
      }
      data = {
        ...detection,
        annotated_image: plate,
        duplicate,
        capture_id: id,
      };
    }
    if (["/preview", "/detect", "/upload"].includes(name))
      data = { ...detection, annotated_image: plate };
    if (name === "/camera/stream")
      return route.fulfill({
        contentType: "image/svg+xml",
        body: `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600"><defs><linearGradient id="a" x2=".8" y2="1"><stop stop-color="#67777e"/><stop offset=".5" stop-color="#bac6c8"/><stop offset="1" stop-color="#52616b"/></linearGradient></defs><rect width="960" height="600" fill="#121b23"/><rect x="130" y="70" width="700" height="450" rx="8" fill="url(#a)"/><path d="M340 150l70 210m0-90l90 20" stroke="#62747c" stroke-width="6"/><rect x="290" y="120" width="260" height="280" stroke="#d3b07a" stroke-width="2" fill="none"/><text x="292" y="110" fill="#e6c995" font-family="sans-serif" font-size="15">Manchas o parches · fixture visual</text><text x="150" y="495" fill="#22323c" font-family="sans-serif" font-size="17">Datos de prueba · imagen sintética, no inferencia real</text></svg>`,
      });
    await route.fulfill({ json: data });
  });
  return calls;
}
async function navigate(page: Page, label: string) {
  if (await page.getByRole("button", { name: "Abrir navegación" }).isVisible())
    await page.getByRole("button", { name: "Abrir navegación" }).click();
  await page
    .getByRole("navigation")
    .getByRole("link", { name: label, exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: label, exact: true, level: 1 }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
}
test("navigation, loaded history filters, detail and responsive layout", async ({
  page,
}, info) => {
  await fixtures(page);
  await page.goto("/static/");
  await expect(
    page.getByRole("heading", { name: "Inspección en vivo", exact: true }),
  ).toBeVisible();
  const folder = path.resolve("../outputs/frontend-redesign");
  mkdirSync(folder, { recursive: true });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    path: path.join(folder, `${info.project.name}-inspection.png`),
    fullPage: true,
  });
  await navigate(page, "Panel general");
  await expect(page.getByText("220", { exact: true })).toBeVisible();
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    path: path.join(folder, `${info.project.name}-overview.png`),
    fullPage: true,
  });
  await navigate(page, "Historial");
  await page
    .getByRole("textbox", { name: "Buscar inspecciones" })
    .fill("rayaduras");
  await expect(
    page.getByRole("cell", { name: "Manchas o parches" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Ver inspección" }).first().click();
  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(
    page.getByText("Imágenes no vinculadas al historial"),
  ).toBeVisible();
  await page.keyboard.press("Escape");
  await navigate(page, "Estadísticas");
  await page.getByLabel("Agrupar por").selectOption("3600");
  await expect(
    page.getByRole("img", { name: /Inspecciones por hora/ }),
  ).toBeVisible();
  await navigate(page, "Configuración");
  await expect(
    page.getByRole("heading", { name: "Modelo de inspección" }),
  ).toBeVisible();
  await navigate(page, "Monitor remoto");
  await expect(page.getByText("Escuchando inspecciones")).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
test("camera controls use real contracts; capture retry is idempotent; preview does not record", async ({
  page,
}, info) => {
  const calls = await fixtures(page);
  await page.goto("/static/");
  await page.getByRole("button", { name: "Buscar cámaras" }).click();
  await page.getByLabel("Fuente de cámara").selectOption("2");
  await page.getByLabel("Dispositivo de inferencia").selectOption("cuda");
  await page
    .getByRole("button", { name: "Iniciar cámara", exact: true })
    .click();
  await expect(
    page.getByRole("img", {
      name: "Vista previa de la cámara USB con detecciones",
    }),
  ).toBeVisible();
  expect(calls.find((c) => c.path === "/camera/start")?.body).toMatchObject({
    camera_index: 2,
    device: "cuda",
    width: 640,
    height: 480,
    fps: 30,
  });
  expect(calls.filter((c) => c.path === "/camera/capture")).toHaveLength(0);
  const capture = page.getByRole("button", {
    name: "Capturar e inspeccionar",
    exact: true,
  });
  await capture.click();
  await expect(page.getByRole("alert")).toBeVisible();
  await capture.click();
  await expect(page.getByText(/Captura recuperada/)).toBeVisible();
  const requests = calls.filter((c) => c.path === "/camera/capture");
  expect(requests[0].body.request_id).toBe(requests[1].body.request_id);
  await expect(page.getByText("74.7", { exact: false }).first()).toBeVisible();
  await page.getByLabel("Umbral de confianza", { exact: true }).fill("0.73");
  await page.getByRole("button", { name: "Aplicar umbral en vivo" }).click();
  expect(calls.find((c) => c.path === "/camera/settings")?.body).toEqual({
    conf: 0.73,
  });
  await page.evaluate(() => {
    window.scrollTo(0, 0);
    if (document.activeElement instanceof HTMLElement)
      document.activeElement.blur();
  });
  await page.screenshot({
    path: path.resolve(
      `../outputs/frontend-redesign/${info.project.name}-capture-fixture.png`,
    ),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Detener", exact: true }).click();
  await expect(
    page.getByRole("img", {
      name: "Vista previa de la cámara USB con detecciones",
    }),
  ).toHaveCount(0);
});
test("empty state and missing model stay actionable without fake approval", async ({
  page,
}) => {
  await fixtures(page, { empty: true, missing: true });
  await page.goto("/static/");
  await expect(
    page.getByRole("button", { name: "Iniciar cámara", exact: true }),
  ).toBeDisabled();
  await expect(page.getByText(/no tiene un modelo cargado/)).toBeVisible();
  await navigate(page, "Historial");
  await expect(
    page.getByRole("heading", { name: "Sin coincidencias" }),
  ).toBeVisible();
  await navigate(page, "Panel general");
  await expect(
    page.getByRole("heading", { name: "Faltan datos para la tendencia" }),
  ).toBeVisible();
});
test("offline error and retry controls are visible", async ({ page }) => {
  await fixtures(page, { offline: true });
  await page.goto("/static/");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reintentar" }).first(),
  ).toBeVisible();
});
test("browser camera preview is separate from capture and image upload", async ({
  page,
}) => {
  const calls = await fixtures(page);
  await page.goto("/static/");
  // Deterministic native MediaStream: Edge's OS fake camera can stall at 2×2.
  // This still exercises video playback, canvas capture, Blob upload and stop().
  await page.evaluate(() => {
    navigator.mediaDevices.getUserMedia = async () => {
      const canvas = document.createElement('canvas');
      canvas.width=640;canvas.height=480;
      const context=canvas.getContext('2d')!;
      const stream=canvas.captureStream(25);
      let frame=0;
      const timer=window.setInterval(()=>{
        if(stream.getTracks().every(track=>track.readyState==='ended')) {clearInterval(timer);return;}
        context.fillStyle='#527787';context.fillRect(0,0,640,480);
        context.fillStyle='#d3b07a';context.fillRect(frame++%600,100,30,30);
      },40);
      return stream;
    };
  });
  await page
    .getByRole("button", { name: "Este dispositivo", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Iniciar cámara", exact: true })
    .click();
  await expect(page.locator("video")).toBeVisible();
  await expect.poll(() => page.locator('video').evaluate(video =>
    video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 2,
  ), { timeout: 15000 }).toBe(true);
  await page.getByRole("checkbox", { name: /Analizar vista previa/ }).check();
  await expect
    .poll(() => calls.filter((c) => c.path === "/preview").length)
    .toBeGreaterThan(0);
  expect(
    calls.filter((c) =>
      ["/detect", "/upload", "/camera/capture"].includes(c.path),
    ),
  ).toHaveLength(0);
  await page.getByRole("checkbox", { name: /Analizar vista previa/ }).uncheck();
  await page
    .getByRole("button", { name: "Capturar e inspeccionar", exact: true })
    .click();
  await expect
    .poll(() => calls.filter((c) => c.path === "/detect").length)
    .toBe(1);
  await expect(
    page.getByRole("link", { name: "Imagen original" }),
  ).toBeVisible();
  await page.getByLabel("Subir imagen de inspección").setInputFiles({
    name: "fixture.png",
    mimeType: "image/png",
    buffer: Buffer.from(image, "base64"),
  });
  await expect
    .poll(() => calls.filter((c) => c.path === "/upload").length)
    .toBe(1);
  await page.getByRole("button", { name: "Detener", exact: true }).click();
  await expect(page.locator("video")).toBeHidden();
});

test("light theme persists and stays readable across all views", async ({
  page,
}, info) => {
  await fixtures(page);
  await page.goto("/static/");
  await page.getByRole("button", { name: "Activar tema claro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await navigate(page, "Panel general");
  await page.reload();
  await expect(
    page.getByRole("button", { name: "Activar tema oscuro" }),
  ).toBeVisible();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  await expect(page.getByText("220", { exact: true })).toBeVisible();
  const ratios = await page.evaluate(() => {
    const color = (value: string) =>
      value
        .match(/[\d.]+/g)!
        .slice(0, 3)
        .map(Number);
    const luminance = (rgb: number[]) =>
      rgb
        .map((v) => {
          v /= 255;
          return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
        })
        .reduce((sum, v, i) => sum + v * [0.2126, 0.7152, 0.0722][i], 0);
    const contrast = (fg: string, bg: string) => {
      const a = luminance(color(fg)),
        b = luminance(color(bg));
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    };
    const title = getComputedStyle(document.querySelector("h1")!);
    const detail = getComputedStyle(
      document.querySelector(".panel-heading p")!,
    );
    const panel = getComputedStyle(document.querySelector(".panel")!);
    const primary = getComputedStyle(
      document.querySelector(".overview-lead .primary")!,
    );
    return [
      contrast(title.color, getComputedStyle(document.body).backgroundColor),
      contrast(detail.color, panel.backgroundColor),
      contrast(primary.color, primary.backgroundColor),
    ];
  });
  ratios.forEach((ratio) => expect(ratio).toBeGreaterThanOrEqual(4.5));
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({
    path: path.resolve(
      `../outputs/frontend-redesign/${info.project.name}-overview-light.png`,
    ),
    fullPage: true,
  });
  for (const name of [
    "Historial",
    "Estadísticas",
    "Configuración",
    "Monitor remoto",
    "Inspección en vivo",
  ])
    await navigate(page, name);
  await expect(page.locator(".camera-viewport")).toHaveCSS(
    "background-color",
    "rgb(12, 17, 22)",
  );
  await page.screenshot({
    path: path.resolve(
      `../outputs/frontend-redesign/${info.project.name}-inspection-light.png`,
    ),
    fullPage: true,
  });
  await page.getByRole("button", { name: "Activar tema oscuro" }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});
test("theme remains usable when browser storage is restricted", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Storage.prototype.getItem = () => {
      throw new Error("blocked");
    };
    Storage.prototype.setItem = () => {
      throw new Error("blocked");
    };
  });
  await fixtures(page, { offline: true });
  await page.goto("/static/");
  await expect(page.getByRole("alert").first()).toBeVisible();
  await page.getByRole("button", { name: "Activar tema claro" }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
});
