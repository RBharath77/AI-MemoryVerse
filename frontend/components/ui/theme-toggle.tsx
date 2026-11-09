"use client";

import React, { useEffect, useState } from "react";
import { Sun, Moon } from "lucide-react";
import { useThemeStore } from "@/store/theme-store";

interface ThemeToggleProps {
  variant?: "icon" | "pill" | "dropdown";
  className?: string;
  showLabels?: boolean;
}

export function ThemeToggle({
  variant = "pill",
  className = "",
  showLabels = true,
}: ThemeToggleProps) {
  const { theme, toggleTheme, setTheme } = useThemeStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  // Avoid SSR hydration mismatch
  if (!mounted) {
    return (
      <div className={`h-8 w-20 rounded-lg bg-navy-800/40 animate-pulse ${className}`} />
    );
  }

  const isDark = theme === "dark";

  if (variant === "icon") {
    return (
      <button
        type="button"
        onClick={toggleTheme}
        aria-label={`Switch to ${isDark ? "light" : "dark"} theme`}
        title={`Switch to ${isDark ? "Light (Alabaster)" : "Dark (Indigo)"} mode`}
        className={`relative p-2 rounded-xl border transition-all duration-200 group ${
          isDark
            ? "bg-[#282B4A]/70 hover:bg-[#282B4A] border-indigo-500/30 text-amber-300 shadow-sm shadow-amber-500/10"
            : "bg-[#EEEBDA]/70 hover:bg-[#EEEBDA] border-[#014BAA]/30 text-[#014BAA] shadow-sm shadow-[#014BAA]/10"
        } ${className}`}
      >
        <div className="relative w-4 h-4 flex items-center justify-center">
          {isDark ? (
            <Sun className="w-4 h-4 text-amber-300 transition-transform duration-300 group-hover:rotate-45" />
          ) : (
            <Moon className="w-4 h-4 text-[#014BAA] transition-transform duration-300 group-hover:-rotate-12" />
          )}
        </div>
      </button>
    );
  }

  // Segmented Pill Control (Default)
  return (
    <div
      role="radiogroup"
      aria-label="Theme selector"
      className={`inline-flex items-center p-1 rounded-xl border backdrop-blur-md transition-colors duration-200 ${
        isDark
          ? "bg-[#282B4A]/90 border-indigo-500/30"
          : "bg-[#EEEBDA]/90 border-[#282B4A]/15 shadow-sm"
      } ${className}`}
    >
      {/* Light Option Button */}
      <button
        type="button"
        role="radio"
        aria-checked={!isDark}
        onClick={() => setTheme("light")}
        className={`relative flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200 ${
          !isDark
            ? "bg-[#014BAA] text-white shadow-md shadow-[#014BAA]/25"
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
        }`}
      >
        <Sun className="w-3.5 h-3.5" />
        {showLabels && <span>Light</span>}
      </button>

      {/* Dark Option Button */}
      <button
        type="button"
        role="radio"
        aria-checked={isDark}
        onClick={() => setTheme("dark")}
        className={`relative flex items-center space-x-1.5 px-2.5 py-1 rounded-lg text-xs font-semibold transition-all duration-200 ${
          isDark
            ? "bg-[#014BAA] text-white shadow-md shadow-[#014BAA]/25"
            : "text-[#282B4A]/80 hover:text-[#282B4A] hover:bg-black/5"
        }`}
      >
        <Moon className="w-3.5 h-3.5" />
        {showLabels && <span>Dark</span>}
      </button>

      {/* Palette indicator dots */}
      <div className="hidden sm:flex items-center space-x-1 pl-2 pr-1 border-l border-white/10 ml-1">
        <span
          className="w-2 h-2 rounded-full border border-black/10"
          style={{ backgroundColor: "#014BAA" }}
          title="Cobalt Blue (#014BAA)"
        />
        <span
          className="w-2 h-2 rounded-full border border-black/10"
          style={{ backgroundColor: "#F8F3F0" }}
          title="Alabaster (#F8F3F0)"
        />
        <span
          className="w-2 h-2 rounded-full border border-black/10"
          style={{ backgroundColor: "#282B4A" }}
          title="Indigo Slate (#282B4A)"
        />
        <span
          className="w-2 h-2 rounded-full border border-black/10"
          style={{ backgroundColor: "#EEEBDA" }}
          title="Warm Linen (#EEEBDA)"
        />
      </div>
    </div>
  );
}

