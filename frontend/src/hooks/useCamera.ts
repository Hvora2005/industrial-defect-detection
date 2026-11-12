import { useEffect, useRef, useState } from "react";
import { api, ApiError, errorMessage } from "../services/api";
import { useResource } from "./useResource";
import type { CameraOptions, Detection } from "../types";

export function useCamera(onCapture: (result: Detection) => void) {
  const resource = useResource(api.camera, 1000);
  const [options, setOptions] = useState<CameraOptions>({
    source: "0",
    backend: "auto",
    width: 640,
    height: 480,
    fps: 30,
    conf: 0.4,
    device: "auto",
  });
  const [sources, setSources] = useState([{ value: "0", label: "Cámara 0" }]);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const pending = useRef<string | null>(null);
  const lock = useRef(false);
  const attached = useRef(false);
  useEffect(() => {
    const state = resource.data;
    if (state?.running && !attached.current) {
      attached.current = true;
      const source =
        state.source_type === "camera" ? state.source || "0" : "demo";
      setSources((previous) =>
        previous.some((s) => s.value === source)
          ? previous
          : [
              ...previous,
              {
                value: source,
                label:
                  source === "demo"
                    ? "Video de demostración"
                    : `Cámara ${source}`,
              },
            ],
      );
      setOptions((o) => ({
        ...o,
        source,
        device: state.requested_device,
        conf: state.confidence,
        ...state.requested,
      }));
    }
    if (!state?.running) attached.current = false;
  }, [resource.data]);
  async function action(name: string, task: () => Promise<void>) {
    if (lock.current) return;
    lock.current = true;
    setBusy(name);
    setError("");
    setMessage("");
    try {
      await task();
      await resource.reload();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      lock.current = false;
      setBusy("");
    }
  }
  return {
    ...resource,
    options,
    setOptions,
    sources,
    busy,
    actionError: error,
    message,
    scan: () =>
      action("scan", async () => {
        const found = await api.cameras(options.backend);
        const list = [
          ...found.cameras.map((c) => ({
            value: String(c.index),
            label: `Cámara ${c.index}`,
          })),
          ...(found.demo_available
            ? [{ value: "demo", label: "Video de demostración" }]
            : []),
        ];
        setSources(list);
        if (list.length)
          setOptions((o) => ({
            ...o,
            source: list.some((s) => s.value === o.source)
              ? o.source
              : list[0].value,
          }));
        setMessage(
          list.length
            ? "Fuentes actualizadas. Selecciona una cámara."
            : "No se encontraron cámaras. Revisa la conexión USB y vuelve a buscar.",
        );
      }),
    start: () =>
      action("start", async () => {
        await api.start(options);
        setMessage("Iniciando vista previa. Espera el primer fotograma.");
      }),
    stop: () =>
      action("stop", async () => {
        await api.stop();
        setMessage("Captura detenida.");
      }),
    apply: () =>
      action("apply", async () => {
        await api.confidence(options.conf);
        setMessage(`Umbral aplicado: ${Math.round(options.conf * 100)}%.`);
      }),
    capture: () =>
      action("capture", async () => {
        pending.current ||= crypto.randomUUID();
        try {
          const result = await api.capture(pending.current);
          pending.current = null;
          onCapture(result);
          setMessage(
            result.duplicate
              ? "Captura recuperada: ya estaba registrada. No se duplicó la inspección."
              : "Inspección registrada. Imágenes disponibles para descargar.",
          );
        } catch (e) {
          if (e instanceof ApiError && e.status < 500) pending.current = null;
          throw e;
        }
      }),
  };
}
export type CameraController = ReturnType<typeof useCamera>;
