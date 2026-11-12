import { act, renderHook } from "@testing-library/react";
import { vi } from "vitest";
import { useTheme } from "./useTheme";
beforeEach(() => {
  localStorage.clear();
  document.documentElement.dataset.theme = "dark";
});
test("switches both ways and persists only the theme preference", () => {
  const { result } = renderHook(useTheme);
  expect(result.current.theme).toBe("dark");
  act(() => result.current.toggleTheme());
  expect(document.documentElement.dataset.theme).toBe("light");
  expect(localStorage.getItem("acero-theme")).toBe("light");
  act(() => result.current.toggleTheme());
  expect(localStorage.getItem("acero-theme")).toBe("dark");
});
test("uses the theme initialized before first paint", () => {
  document.documentElement.dataset.theme = "light";
  const { result } = renderHook(useTheme);
  expect(result.current.theme).toBe("light");
});
test("restores a saved choice even before the document theme is initialized", () => {
  localStorage.setItem("acero-theme", "light");
  const { result } = renderHook(useTheme);
  expect(result.current.theme).toBe("light");
  expect(document.documentElement.dataset.theme).toBe("light");
});
test("storage restrictions do not prevent switching in the session", () => {
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
    throw new Error("blocked");
  });
  const { result } = renderHook(useTheme);
  act(() => result.current.toggleTheme());
  expect(document.documentElement.dataset.theme).toBe("light");
});
