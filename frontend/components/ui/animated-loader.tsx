"use client";

import React, { useEffect, useRef, useState } from "react";
import { Sparkles, Brain, CheckCircle2 } from "lucide-react";
import { BrainLoader } from "./brain-loader";

export { BrainLoader } from "./brain-loader";

export interface AnimatedLoaderProps {
  size?: "sm" | "md" | "lg" | "fullscreen";
  label?: string;
  sublabel?: string;
  cycleMessages?: boolean;
  className?: string;
  onComplete?: () => void;
  autoDismiss?: boolean;
  speedMs?: number;
  durationMs?: number;
  moduleName?: string;
  stages?: any[];
}

const DEFAULT_MESSAGES = [
  "Synchronizing memory vault...",
  "Traversing knowledge graph...",
  "Synthesizing neural vectors...",
  "Assembling grounded context...",
  "Calibrating intelligence engine...",
  "External brain ready.",
];

export function AnimatedLoader({
  size = "md",
  label,
  sublabel,
  cycleMessages = true,
  className = "",
  onComplete,
  autoDismiss = true,
  speedMs = 70,
  durationMs,
  moduleName,
  stages,
}: AnimatedLoaderProps) {
  const [msgIndex, setMsgIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isDone, setIsDone] = useState(false);
  const [isFading, setIsFading] = useState(false);

  // Keep onComplete reference stable across parent re-renders so interval is never reset
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Smooth progressive loading bar from 0% to 100%
  useEffect(() => {
    let current = 0;
    const interval = setInterval(() => {
      // Deterministic smooth climbing curve to 100%
      if (current < 30) {
        current += Math.floor(Math.random() * 8) + 8; // fast start
      } else if (current < 70) {
        current += Math.floor(Math.random() * 7) + 6; // steady mid
      } else if (current < 95) {
        current += Math.floor(Math.random() * 6) + 4; // smooth approach
      } else {
        current = 100;
      }

      if (current >= 100) {
        current = 100;
        setProgress(100);
        setIsDone(true);
        clearInterval(interval);

        if (onCompleteRef.current) {
          setTimeout(() => {
            onCompleteRef.current?.();
          }, 250);
        }

        if (autoDismiss && size === "fullscreen") {
          setTimeout(() => {
            setIsFading(true);
          }, 450);
        }
        return;
      }

      setProgress(current);
    }, speedMs);

    // Hard safety timeout: guarantee 100% within 1.5s regardless of anything
    const safetyTimer = setTimeout(() => {
      setProgress(100);
      setIsDone(true);
      clearInterval(interval);
      if (onCompleteRef.current) {
        onCompleteRef.current();
      }
      if (autoDismiss && size === "fullscreen") {
        setTimeout(() => setIsFading(true), 350);
      }
    }, 1500);

    return () => {
      clearInterval(interval);
      clearTimeout(safetyTimer);
    };
  }, [size, autoDismiss, speedMs]);

  // Cycle status messages
  useEffect(() => {
    if (!cycleMessages || label || isDone) return;
    const interval = setInterval(() => {
      setMsgIndex((prev) => (prev + 1) % DEFAULT_MESSAGES.length);
    }, 800);
    return () => clearInterval(interval);
  }, [cycleMessages, label, isDone]);

  const activeLabel = isDone
    ? "External brain online and synchronized."
    : label || (cycleMessages ? DEFAULT_MESSAGES[msgIndex] : "Loading MemoryVerse...");

  // Compact size for buttons or inline badges
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
          <div className="absolute inset-0 rounded-full bg-brand-cyan/15 blur-xl animate-pulse" />
          <div className="absolute inset-0 rounded-full border-2 border-dashed border-brand-cyan/40 animate-spin-slow" />
          <div className="absolute inset-2 rounded-full border-2 border-t-brand-violet border-r-transparent border-b-brand-blue border-l-transparent animate-spin-reverse-slow" />
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
          <div className="absolute inset-0 rounded-full border border-brand-cyan/30 animate-ripple" />
          <div className="absolute inset-0 rounded-full bg-gradient-to-tr from-brand-cyan/20 via-brand-blue/20 to-brand-violet/20 blur-2xl animate-pulse" />

          <div className="absolute inset-0 rounded-full border-2 border-dashed border-slate-700/60 animate-spin-slow">
            <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 rounded-full bg-brand-cyan shadow-[0_0_10px_#06b6d4]" />
          </div>

          <div className="absolute inset-3 rounded-full border-2 border-t-brand-violet border-r-brand-cyan/30 border-b-brand-blue border-l-transparent animate-spin-reverse-slow">
            <div className="absolute -bottom-1.5 left-1/2 -translate-x-1/2 w-2.5 h-2.5 rounded-full bg-brand-violet shadow-[0_0_8px_#8b5cf6]" />
          </div>

          <div className="relative w-12 h-12 rounded-xl bg-navy-900/80 border border-brand-cyan/50 shadow-[0_0_20px_rgba(6,182,212,0.4)] flex items-center justify-center backdrop-blur-md animate-pulse-glow">
            <Brain className="w-6 h-6 text-brand-cyan" />
          </div>
        </div>

        <div className="mt-6 space-y-2 max-w-xs">
          <p className="text-sm font-semibold tracking-wide text-slate-200 animate-shimmer">
            {activeLabel}
          </p>
          {/* Progressive visual bar */}
          <div className="w-48 h-1.5 bg-navy-900 rounded-full overflow-hidden border border-navy-800 mx-auto">
            <div
              className="h-full bg-gradient-to-r from-brand-cyan via-brand-blue to-brand-violet transition-all duration-200 shadow-[0_0_8px_#06b6d4]"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono px-1 w-48 mx-auto">
            <span>Neural Sync</span>
            <span className="text-cyan-400 font-bold">{progress}%</span>
          </div>
        </div>
        <span className="sr-only">Loading</span>
      </div>
    );
  }

  // Fullscreen loading overlay for route transitions or app boot: use high-fidelity neural BrainLoader
  const activeStages =
    stages ||
    (label
      ? [
          { pct: 0, message: label },
          {
            pct: 35,
            message: sublabel || `Synchronizing ${moduleName || "module"} neural network...`,
          },
          { pct: 75, message: "Synthesizing vector representations..." },
          { pct: 100, message: `${moduleName || "Module"} online and synchronized.` },
        ]
      : undefined);

  return (
    <BrainLoader
      variant="fullscreen"
      durationMs={durationMs || 1800}
      stages={activeStages}
      onComplete={onComplete}
      autoDismiss={autoDismiss}
      className={className}
      clickToDismiss={true}
    />
  );
}
