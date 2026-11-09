import { create } from "zustand";

export type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  toggleTheme: () => void;
  setTheme: (theme: Theme) => void;
}

export const useThemeStore = create<ThemeState>((set, get) => ({
  theme: "dark",

  toggleTheme: () => {
    const current = get().theme;
    const next: Theme = current === "dark" ? "light" : "dark";

    if (typeof window !== "undefined") {
      localStorage.setItem("memoryverse_theme", next);
      const root = document.documentElement;
      root.classList.remove("dark", "light");
      root.classList.add(next);
    }

    set({ theme: next });
  },

  setTheme: (theme: Theme) => {
    if (typeof window !== "undefined") {
      localStorage.setItem("memoryverse_theme", theme);
      const root = document.documentElement;
      root.classList.remove("dark", "light");
      root.classList.add(theme);
    }

    set({ theme });
  },
}));

