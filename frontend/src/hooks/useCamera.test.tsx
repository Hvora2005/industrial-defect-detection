import { act, renderHook, waitFor } from "@testing-library/react";
import { vi } from "vitest";
import { api } from "../services/api";
import { useCamera } from "./useCamera";
const state = {
  state: "running",
  running: true,
  confidence: 0.4,
  requested_device: "cuda" as const,
  source: "2",
  source_type: "camera",
  frames_processed: 10,
  inspections_recorded: 0,
};
test("reattaches an existing camera and polling never records pieces", async () => {
  vi.spyOn(api, "camera").mockResolvedValue(state);
  const capture = vi.spyOn(api, "capture");
  const { result } = renderHook(() => useCamera(vi.fn()));
  await waitFor(() => expect(result.current.options.source).toBe("2"));
  expect(result.current.options.device).toBe("cuda");
  expect(capture).not.toHaveBeenCalled();
});
test("lost capture response reuses UUID; successful next capture gets a new UUID", async () => {
  vi.spyOn(api, "camera").mockResolvedValue(state);
  const capture = vi
    .spyOn(api, "capture")
    .mockRejectedValueOnce(new TypeError("network"))
    .mockResolvedValue({
      status: "NO_DETECTIONS",
      defects_found: 0,
      defects: [],
      severity: null,
      annotated_image: "",
    });
  const receive = vi.fn();
  const { result } = renderHook(() => useCamera(receive));
  await waitFor(() => expect(result.current.data?.running).toBe(true));
  await act(() => result.current.capture());
  await act(() => result.current.capture());
  await act(() => result.current.capture());
  expect(capture.mock.calls[0][0]).toBe(capture.mock.calls[1][0]);
  expect(capture.mock.calls[2][0]).not.toBe(capture.mock.calls[1][0]);
  expect(receive).toHaveBeenCalledTimes(2);
});
test("camera actions call stop and confidence endpoints with the selected value", async () => {
  vi.spyOn(api, "camera").mockResolvedValue(state);
  const stop = vi
    .spyOn(api, "stop")
    .mockResolvedValue({ ...state, running: false });
  const confidence = vi.spyOn(api, "confidence").mockResolvedValue(state);
  const { result } = renderHook(() => useCamera(vi.fn()));
  await waitFor(() => expect(result.current.data).toBeDefined());
  act(() => result.current.setOptions((o) => ({ ...o, conf: 0.77 })));
  await act(() => result.current.apply());
  await act(() => result.current.stop());
  expect(confidence).toHaveBeenCalledWith(0.77);
  expect(stop).toHaveBeenCalledTimes(1);
});
