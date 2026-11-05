"use client";

import React, { useEffect, useState } from "react";
import { Sparkles, Brain, Cpu } from "lucide-react";

export interface AnimatedLoaderProps {
  size?: "sm" | "md" | "lg" | "fullscreen";
  label?: string;
  sublabel?: string;
  cycleMessages?: boolean;
  className?: string;
}

const DEFAULT_MESSAGES = [
  "Synchronizing memory vault...",
  "Traversing knowledge graph...",
  "Synthesizing neural vectors...",
  "Assembling grounded context...",
  "Calibrating intelligence engine...",
];

export function AnimatedLoader({
  size = "md",
  label,
  sublabel,
  cycleMessages = true,
  className = "",
}: AnimatedLoaderProps) {
  const [msgIndex, setMsgIndex] = useState(0);

  useEffect(() => {
    if (!cycleMessages || label) return;
    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % DEFAULT_MESSAGES.length);
    }, 2400);
    return () => clearInterval(interval);
  }, [cycleMessages, label]);

  const activeLabel = label || (cycleMessages ? DEFAULT_MESSAGES[msgIndex] : "Loading MemoryVerse...");

  // Compact size for buttons or cards
  if (size === "sm") {
    return (
      <div
        role="status"
        aria-live="polite"
        className={`inline-flex items-center gap-2 text-slate-300 ${className}`}
      >
        <div className="relative w-5 h-5 flex items-center justify-center">
          <div className="absolute inset-0 rounded-full border-2 border-brand-cyan/20 border-t-brand-cyan animate-spin" />
          <div className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-pulse" />
        </div>
        {label && <span className="text-xs font-medium">{label}</span>}
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  // Medium size for dashboard cards / panels
  if (size === "md") {
    return (
      <div
        role="status"
        aria-live="polite"
        className={`flex flex-col items-center justify-center p-6 text-center ${className}`}
      >
        <div className="relative w-16 h-16 flex items-center justify-center">
          {/* Ambient background glow */}
          <div className="absolute inset-0 rounded-full bg-brand-cyan/15 blur-xl animate-pulse" />

          {/* Outer rotating gyro ring */}
          <div className="absolute inset-0 rounded-full border-2 border-dashed border-brand-cyan/40 animate-spin-slow" />

          {/* Inner counter-rotating ring */}
          <div className="absolute inset-2 rounded-full border-2 border-t-brand-violet border-r-transparent border-b-brand-blue border-l-transparent animate-spin-reverse-slow" />

          {/* Central Memory Core */}
          <div className="relative w-8 h-8 rounded-full bg-gradient-to-br from-brand-cyan/30 to-brand-violet/30 border border-brand-cyan/60 flex items-center justify-center backdrop-blur-sm animate-pulse-glow">
            <Sparkles className="w-4 h-4 text-brand-cyan animate-pulse" />
          </div>
        </div>

        {activeLabel && (
          <p className="mt-4 text-xs font-medium text-slate-300 tracking-wide animate-shimmer">
            {activeLabel}
          </p>
        )}
        {sublabel && (
          <p className="mt-1 text-[11px] text-slate-500 font-mono">{sublabel}</p>
        )}
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  // Large size for page sections
  if (size === "lg") {
    return (
      <div
        role="status"
        aria-live="polite"
        className={`flex flex-col items-center justify-center p-12 text-center ${className}`}
      >
        <div className="relative w-24 h-24 flex items-center justify-center">
          {/* Outer ripple wave */}
          <div className="absolute inset-0 rounded-full border border-brand-cyan/30 animate-ripple" />
          <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-brand-cyan/20 via-brand-blue/20 to-brand-violet/20 blur-2xl animate-pulse" />

          {/* Outer orbit track */}
          <div className="absolute inset-0 rounded-full border-2 border-dashed border-slate-700/60 animate-spin-slow">
            <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-brand-cyan shadow-[0_0_10px_#06b6d4]" />
          </div>

          {/* Counter-rotating middle ring */}
          <div className="absolute inset-3 rounded-full border-2 border-t-brand-violet border-r-brand-cyan/30 border-b-brand-blue border-l-transparent animate-spin-reverse-slow">
            <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-brand-violet shadow-[0_0_8px_#8b5cf6]" />
          </div>

          {/* Inner holographic core */}
          <div className="relative w-12 h-12 rounded-xl bg-navy-900/80 border border-brand-cyan/50 shadow-[0_0_20px_rgba(6,182,212,0.4)] flex items-center justify-center backdrop-blur-md animate-pulse-glow">
            <Brain className="w-6 h-6 text-brand-cyan" />
          </div>
        </div>

        <div className="mt-6 space-y-1.5">
          <p className="text-sm font-semibold tracking-wide text-slate-200 animate-shimmer">
            {activeLabel}
          </p>
          {sublabel ? (
            <p className="text-xs text-slate-500 font-mono">{sublabel}</p>
          ) : (
            <p className="text-[11px] text-slate-500 font-mono uppercase tracking-wider">
              AI-MemoryVerse Neural Engine
            </p>
          )}
        </div>
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  // Fullscreen loading overlay for route transitions or app boot
  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed inset-0 z-50 flex flex-col items-center justify-center bg-navy-950/90 backdrop-blur-xl transition-all duration-300 ${className}`}
    >
      {/* Ambient background volumetric lighting */}
      <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-96 h-96 bg-brand-cyan/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute -bottom-32 left-1/2 -translate-x-1/2 w-96 h-96 bg-brand-violet/10 rounded-full blur-3xl pointer-events-none" />

      {/* Main Hologram Container */}
      <div className="relative w-32 h-32 flex items-center justify-center">
        {/* Pulsing ripples */}
        <div className="absolute inset-0 rounded-full border border-brand-cyan/20 animate-ripple" />
        <div
          className="absolute inset-0 rounded-full border border-brand-violet/20 animate-ripple"
          style={{ animationDelay: "1s" }}
        />

        {/* Outer orbital ring with satellite node */}
        <div className="absolute inset-0 rounded-full border-2 border-dashed border-slate-700/80 animate-spin-slow">
          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3.5 h-3.5 rounded-full bg-brand-cyan shadow-[0_0_12px_#06b6d4]" />
        </div>

        {/* Intermediate angled ring */}
        <div className="absolute inset-3 rounded-full border-2 border-t-brand-cyan border-r-transparent border-b-brand-violet border-l-transparent animate-spin-reverse-slow">
          <div className="absolute top-1/2 -right-1.5 -translate-y-1/2 w-2.5 h-2.5 rounded-full bg-brand-violet shadow-[0_0_10px_#8b5cf6]" />
        </div>

        {/* Inner high-speed synaptic core ring */}
        <div className="absolute inset-6 rounded-full border border-brand-blue/60 border-t-white animate-spin">
          <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-brand-blue shadow-[0_0_6px_#3b82f6]" />
        </div>

        {/* Central Quantum Brain Core */}
        <div className="relative w-14 h-14 rounded-2xl bg-gradient-to-br from-navy-900 via-navy-850 to-navy-950 border border-brand-cyan/60 shadow-[0_0_30px_rgba(6,182,212,0.5)] flex items-center justify-center backdrop-blur-md animate-pulse-glow">
          <Brain className="w-7 h-7 text-brand-cyan" />
        </div>
      </div>

      {/* Dynamic status readout */}
      <div className="mt-8 text-center space-y-2 max-w-sm px-4">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-navy-900/80 border border-slate-800 text-xs font-mono text-brand-cyan shadow-inner">
          <span className="w-1.5 h-1.5 rounded-full bg-brand-cyan animate-ping" />
          <span>NEURAL PIPELINE ACTIVE</span>
        </div>

        <h3 className="text-base font-semibold text-slate-100 tracking-wide animate-shimmer min-h-[1.5rem]">
          {activeLabel}
        </h3>

        <p className="text-xs text-slate-500 font-mono">
          {sublabel || "AI-MemoryVerse Knowledge Platform"}
        </p>
      </div>

      <span className="sr-only">Loading</span>
    </div>
  );
}
