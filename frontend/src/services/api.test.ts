import { vi } from "vitest";
import { api, ApiError, errorMessage } from "./api";
afterEach(() => vi.unstubAllGlobals());
test("camera start uses actual backend contract, including demo and device", async () => {
  const fetch = vi
    .fn()
    .mockResolvedValue({ ok: true, json: async () => ({ running: true }) });
  vi.stubGlobal("fetch", fetch);
  await api.start({
    source: "demo",
    backend: "dshow",
    width: 640,
    height: 480,
    fps: 30,
    conf: 0.61,
    device: "cuda",
  });
  expect(fetch).toHaveBeenCalledWith(
    "/camera/start",
    expect.objectContaining({
      method: "POST",
      body: JSON.stringify({
        source_type: "demo",
        camera_index: 0,
        backend: "dshow",
        width: 640,
        height: 480,
        fps: 30,
        conf: 0.61,
        device: "cuda",
      }),
    }),
  );
});
test("preview has its own non-recording endpoint and carries inference settings", async () => {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetch);
  await api.image(new Blob(["image"]), "/preview", 0.57, "cpu");
  expect(fetch).toHaveBeenCalledWith(
    "/preview?conf=0.57&device=cpu",
    expect.objectContaining({ method: "POST", body: expect.any(FormData) }),
  );
});
test("503 errors are actionable and the raw backend error is retained", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "Missing weights" }),
      }),
  );
  await expect(api.health()).rejects.toThrow("Missing weights");
  expect(errorMessage(new ApiError(503, "Missing weights"))).toContain(
    "modelo o el dispositivo",
  );
});
