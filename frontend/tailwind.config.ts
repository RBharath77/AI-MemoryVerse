import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        // Custom palette provided by user:
        // #014BAA (Cobalt Blue), #F8F3F0 (Alabaster), #282B4A (Deep Slate Indigo), #EEEBDA (Warm Linen)
        mv: {
          blue: "#014BAA",
          alabaster: "#F8F3F0",
          indigo: "#282B4A",
          linen: "#EEEBDA",
        },
        navy: {
          950: "rgb(var(--mv-bg-950) / <alpha-value>)",
          900: "rgb(var(--mv-bg-900) / <alpha-value>)",
          850: "rgb(var(--mv-bg-850) / <alpha-value>)",
          800: "rgb(var(--mv-border-800) / <alpha-value>)",
          700: "rgb(var(--mv-border-700) / <alpha-value>)",
        },
        brand: {
          cyan: "#014BAA",
          blue: "#014BAA",
          violet: "#282B4A",
          emerald: "#10b981",
          amber: "#f59e0b",
        },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
