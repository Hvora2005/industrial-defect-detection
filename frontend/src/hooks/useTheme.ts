import { useEffect, useState } from "react";

export function useTheme() {
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    try {
      const saved = localStorage.getItem("acero-theme");
      if (saved === "light" || saved === "dark") return saved;
    } catch {
      /* Use the prepaint/session theme if storage cannot be read. */
    }
    return document.documentElement.dataset.theme === "light"
      ? "light"
      : "dark";
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document
      .querySelector('meta[name="theme-color"]')
      ?.setAttribute("content", theme === "light" ? "#f0f3f6" : "#11151b");
    try {
      localStorage.setItem("acero-theme", theme);
    } catch {
      /* The current session can still change theme. */
    }
  }, [theme]);
  return {
    theme,
    toggleTheme: () =>
      setTheme((previous) => (previous === "dark" ? "light" : "dark")),
  };
}
