"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import {
  BRAIN_MODEL,
  BRAIN_TEXTURE_BASE64,
  DEFAULT_BRAIN_STAGES,
  BrainStage,
} from "./brain-loader-data";
import { useThemeStore } from "@/store/theme-store";
import { Sun, Moon, RotateCcw, X } from "lucide-react";

export interface BrainThemeColors {
  bg: string;
  bg2: string;
  text: string;
  muted: string;
  pink: string;
  amber: string;
  teal: string;
}

export const DARK_BRAIN_PALETTE: BrainThemeColors = {
  bg: "#16132A",       // Deep cosmic indigo canvas
  bg2: "#2A1F4A",      // Luminous celestial indigo core
  text: "#F8F3F0",     // Crisp luminescent vanilla
  muted: "#A0A3BA",    // Soft nebula slate
  pink: "#FF4F81",     // Electric neon pink/magenta
  amber: "#FFC857",    // Luminous solar amber
  teal: "#3DDBD9",     // Bioluminescent electric cyan
};

export const LIGHT_BRAIN_PALETTE: BrainThemeColors = {
  bg: "#F8F3F0",       // Signature AI-MemoryVerse Warm Vanilla canvas
  bg2: "#EEEBDA",      // Warm Vanilla Cream radial core
  text: "#282B4A",     // Signature Deep Indigo Slate text
  muted: "#5A5D7A",    // Muted indigo slate
  pink: "#D81B60",     // Vivid Royal Crimson / Magenta
  amber: "#D97706",    // Deep radiant golden amber
  teal: "#0E9C9A",     // Rich jewel sapphire teal
};

export interface BrainLoaderProps {
  /** "fullscreen" for app/route boot, "embedded" for inline dashboard cards */
  variant?: "fullscreen" | "embedded";
  /** Optional manual progress override (0-100). If omitted, runs the cinematic timeline */
  progress?: number;
  /** Custom stage status messages */
  stages?: BrainStage[];
  /** Force theme ("dark" | "light") or "auto" to track app theme */
  theme?: "dark" | "light" | "auto";
  /** Invoked when progress hits 100% and finale animation concludes */
  onComplete?: () => void;
  /** Invoked if user manually closes/dismisses */
  onDismiss?: () => void;
  /** Auto-dismiss fullscreen overlay after finale zoom */
  autoDismiss?: boolean;
  /** Duration in ms for the simulated progress curve (default: 4200ms) */
  durationMs?: number;
  /** Show theme switcher pill in top-right corner */
  showThemeToggle?: boolean;
  /** Show replay button once finished */
  showReplay?: boolean;
  /** Allow clicking backdrop to fast-forward/dismiss */
  clickToDismiss?: boolean;
  /** Custom className */
  className?: string;
}

interface Pulse {
  a: number;
  b: number;
  t: number;
  v: number;
}

interface DustParticle {
  x: number;
  y: number;
  v: number;
  s: number;
  ph: number;
  a: boolean;
}

export function BrainLoader({
  variant = "fullscreen",
  progress: externalProgress,
  stages = DEFAULT_BRAIN_STAGES,
  theme: explicitTheme = "auto",
  onComplete,
  onDismiss,
  autoDismiss = true,
  durationMs = 4200,
  showThemeToggle = false,
  showReplay = false,
  clickToDismiss = true,
  className = "",
}: BrainLoaderProps) {
  const storeTheme = useThemeStore((s) => s.theme);
  const toggleStoreTheme = useThemeStore((s) => s.toggleTheme);

  // Determine active theme
  const [resolvedTheme, setResolvedTheme] = useState<"dark" | "light">(() => {
    if (explicitTheme === "dark" || explicitTheme === "light") return explicitTheme;
    if (typeof window !== "undefined") {
      if (document.documentElement.classList.contains("light")) return "light";
      if (document.documentElement.classList.contains("dark")) return "dark";
      if (window.matchMedia?.("(prefers-color-scheme: light)").matches) return "light";
    }
    return storeTheme === "light" ? "light" : "dark";
  });

  // Keep theme synced with document/store changes
  useEffect(() => {
    if (explicitTheme === "dark" || explicitTheme === "light") {
      setResolvedTheme(explicitTheme);
      return;
    }
    setResolvedTheme(storeTheme === "light" ? "light" : "dark");
  }, [explicitTheme, storeTheme]);

  const isDark = resolvedTheme === "dark";
  const palette = isDark ? DARK_BRAIN_PALETTE : LIGHT_BRAIN_PALETTE;

  // Canvas and DOM refs
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const auraRef = useRef<HTMLDivElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // HUD and state
  const [percent, setPercent] = useState<number>(0);
  const [neuronsOnline, setNeuronsOnline] = useState<number>(0);
  const [stageMsg, setStageMsg] = useState<string>(stages[0]?.message || "Initializing neural mesh");
  const [isZooming, setIsZooming] = useState<boolean>(false);
  const [isDone, setIsDone] = useState<boolean>(false);
  const [isDismissed, setIsDismissed] = useState<boolean>(false);

  // Stable callback ref
  const onCompleteRef = useRef(onComplete);
  useEffect(() => {
    onCompleteRef.current = onComplete;
  }, [onComplete]);

  // Simulation timeline checkpoints: [timeFraction, targetPercentage]
  const simTimeline = useRef<[number, number][]>([
    [0, 0],
    [0.12, 14],
    [0.34, 42],
    [0.55, 68],
    [0.78, 86],
    [0.92, 96],
    [1.0, 100],
  ]);

  // Restart / replay trigger
  const [runKey, setRunKey] = useState<number>(0);

  const handleRestart = useCallback(() => {
    setIsZooming(false);
    setIsDone(false);
    setIsDismissed(false);
    setPercent(0);
    setNeuronsOnline(0);
    setRunKey((k) => k + 1);
  }, []);

  const handleFastForward = useCallback(() => {
    if (isDone || isDismissed) return;
    setPercent(100);
  }, [isDone, isDismissed]);

  // Main canvas animation effect
  useEffect(() => {
    const cv = canvasRef.current;
    if (!cv) return;
    const ctx = cv.getContext("2d");
    if (!ctx) return;

    const D = BRAIN_MODEL;
    const IW = D.w;
    const IH = D.h;
    const N = D.r.length; // 323 neurons
    const E = D.e.length / 2; // 567 edges

    // Unpack interleaved coordinates for high-speed cache-local loops
    const nx = new Float32Array(N);
    const ny = new Float32Array(N);
    for (let j = 0; j < N; j++) {
      nx[j] = D.n[2 * j];
      ny[j] = D.n[2 * j + 1];
    }
    const nr = D.r;
    const rk = D.k;

    // Projected screen coordinates
    const sx = new Float32Array(N);
    const sy = new Float32Array(N);
    const act = new Float32Array(N);
    const fl = new Float32Array(N);

    // Offscreen glow canvas (rendered at half resolution for 60fps performance)
    const gcv = document.createElement("canvas");
    const gctx = gcv.getContext("2d");

    // Offscreen silhouette contour canvas (pre-baked once, updated on resize/theme)
    const rimCv = document.createElement("canvas");
    const rctx = rimCv.getContext("2d");

    // Photographic underlay texture
    const img = new Image();
    img.src = BRAIN_TEXTURE_BASE64;

    // Check motion preference
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    // Dynamic DPR scaling: cap at 1.5 for retina smoothness, adapt down to 1.0 if frames lag
    let dprCap = 1.5;
    let dpr = 1;
    let W = 0;
    let H = 0;
    let K = 1;
    let CX = 0;
    let CY = 0;

    // Glow sprites generator
    function createSprite(color: string): HTMLCanvasElement {
      const s = document.createElement("canvas");
      s.width = s.height = 48;
      const g = s.getContext("2d");
      if (!g) return s;
      const gr = g.createRadialGradient(24, 24, 0, 24, 24, 24);
      gr.addColorStop(0, color);
      gr.addColorStop(0.4, color);
      gr.addColorStop(1, "rgba(0,0,0,0)");
      g.fillStyle = gr;
      g.fillRect(0, 0, 48, 48);
      return s;
    }

    let sprites: HTMLCanvasElement[] = [];

    // Size and projection recalculation
    function resizeCanvas() {
      if (!cv || !gctx || !rctx) return;
      const rect = cv.getBoundingClientRect();
      W = Math.max(300, rect.width || window.innerWidth);
      H = Math.max(300, rect.height || window.innerHeight);

      dpr = Math.min(window.devicePixelRatio || 1, dprCap);
      cv.width = Math.round(W * dpr);
      cv.height = Math.round(H * dpr);
      ctx?.setTransform(dpr, 0, 0, dpr, 0, 0);

      gcv.width = Math.ceil(W * 0.5);
      gcv.height = Math.ceil(H * 0.5);
      gctx.setTransform(0.5, 0, 0, 0.5, 0, 0);

      K = Math.min((W * 0.92) / IW, (H * 0.56) / IH);
      CX = W / 2;
      CY = H * 0.40;

      // Project neuron vertices to screen coordinates
      for (let j = 0; j < N; j++) {
        sx[j] = CX + (nx[j] - IW / 2) * K;
        sy[j] = CY + (ny[j] - IH / 2) * K;
      }

      // Re-bake glowing silhouette contour
      rimCv.width = cv.width;
      rimCv.height = cv.height;
      rctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      rctx.clearRect(0, 0, W, H);
      rctx.lineJoin = "round";
      rctx.strokeStyle = palette.pink;
      rctx.lineWidth = 2.2;
      rctx.shadowColor = palette.pink;
      rctx.shadowBlur = 14;
      rctx.beginPath();
      for (let k = 0; k < D.c.length; k += 2) {
        const x = CX + (D.c[k] - IW / 2) * K;
        const y = CY + (D.c[k + 1] - IH / 2) * K;
        if (k === 0) rctx.moveTo(x, y);
        else rctx.lineTo(x, y);
      }
      rctx.closePath();
      rctx.stroke();
      rctx.stroke();
    }

    // Initialize sprites from active palette
    sprites = [
      createSprite(palette.pink),
      createSprite(palette.amber),
      createSprite(palette.teal),
    ];
    resizeCanvas();

    // Pulses and dust particles
    const pulses: Pulse[] = [];
    const dust: DustParticle[] = [];
    for (let j = 0; j < 32; j++) {
      dust.push({
        x: Math.random(),
        y: Math.random(),
        v: 0.02 + Math.random() * 0.05,
        s: 0.8 + Math.random() * 1.6,
        ph: Math.random() * 6.28,
        a: Math.random() < 0.25,
      });
    }

    let target = externalProgress !== undefined ? externalProgress : 0;
    let shown = 0;
    let rafId = 0;
    let finished = false;
    let flash = 0;
    let ring = -1;
    let lastStep = -1;
    let zoomStart = -1;
    let spawnAcc = 0;
    let lastTime = performance.now();
    let simStart = performance.now();
    let avgDelta = 0.0167;
    let frameCount = 0;
    let lastAura = -1;
    const timeouts: NodeJS.Timeout[] = [];

    const isLightMode = !isDark;

    function getSimTarget(now: number): number {
      if (externalProgress !== undefined) {
        return Math.max(0, Math.min(100, externalProgress));
      }
      const fraction = Math.min(1, (now - simStart) / durationMs);
      const keys = simTimeline.current;
      let a = keys[0];
      let b = keys[1];
      for (let q = 1; q < keys.length; q++) {
        if (fraction <= keys[q][0]) {
          a = keys[q - 1];
          b = keys[q];
          break;
        }
      }
      return a[1] + (b[1] - a[1]) * ((fraction - a[0]) / (b[0] - a[0] || 1));
    }

    // Animation frame render
    function render(now: number, dt: number): number {
      if (!ctx || !gctx) return 0;
      const t = now / 1000;
      const p = Math.max(0, Math.min(1, shown / 100));
      const on = Math.round(p * N);

      ctx.clearRect(0, 0, W, H);

      const zt = zoomStart >= 0 ? Math.min(1, Math.max(0, (now - zoomStart) / 1600)) : 0;
      const fade = 1 - Math.min(1, Math.max(0, (zt - 0.3) / 0.6));
      const ka = 1 - Math.exp(-dt * 8);

      for (let j = 0; j < N; j++) {
        act[j] += ((rk[j] < on ? 1 : 0) - act[j]) * ka;
        fl[j] *= Math.exp(-dt * 5.5);
      }

      // Volumetric aura modulation
      const auraBase = isLightMode ? 0.08 : 0.14;
      const auraVal =
        Math.round(
          (auraBase + 0.42 * p + 0.4 * flash + (reduce ? 0 : 0.04 * Math.sin(t * 1.6))) * 100
        ) / 100;
      if (auraVal !== lastAura && zoomStart < 0 && auraRef.current) {
        lastAura = auraVal;
        auraRef.current.style.opacity = String(auraVal);
      }

      if (zt >= 1) return on;

      // 1. Drifting celestial dust particles
      ctx.globalAlpha = (palette === DARK_BRAIN_PALETTE ? 0.14 : 0.22 + 0.25 * p) * fade;
      for (let g = 0; g < 2; g++) {
        ctx.fillStyle = g ? palette.amber : palette.text;
        ctx.beginPath();
        for (let j = 0; j < dust.length; j++) {
          const d = dust[j];
          if (!!d.a !== !!g) continue;
          if (!reduce) {
            d.y -= d.v * dt;
            if (d.y < -0.02) {
              d.y = 1.02;
              d.x = Math.random();
            }
          }
          const dx = d.x * W + (reduce ? 0 : Math.sin(t * 0.4 + d.ph) * 10);
          const dy = d.y * H;
          ctx.moveTo(dx + d.s, dy);
          ctx.arc(dx, dy, d.s, 0, 6.283);
        }
        ctx.fill();
      }

      // 2. Synaptic signal pulse generation
      if (!reduce && on > 8) {
        spawnAcc += (8 + 50 * p + flash * 90) * dt;
        while (spawnAcc >= 1) {
          spawnAcc -= 1;
          if (pulses.length < 75) {
            for (let tr = 0; tr < 6; tr++) {
              const ei = Math.floor(Math.random() * E);
              const ea = D.e[2 * ei];
              const eb = D.e[2 * ei + 1];
              if (act[ea] > 0.6 && act[eb] > 0.6) {
                const fw = Math.random() < 0.5;
                pulses.push({
                  a: fw ? ea : eb,
                  b: fw ? eb : ea,
                  t: 0,
                  v: 0.9 + Math.random() * 1.3,
                });
                break;
              }
            }
          }
        }
      }

      for (let j = pulses.length - 1; j >= 0; j--) {
        const pu = pulses[j];
        pu.t += pu.v * dt;
        if (pu.t >= 1) {
          fl[pu.b] = 1;
          pulses.splice(j, 1);
        }
      }

      // 3. Camera breathing & zoom transformation
      const bob = reduce ? 0 : Math.sin(t * 1.1) * 3;
      const rot = reduce ? 0 : Math.sin(t * 0.5) * 0.012;
      const br =
        (reduce ? 1 : 1 + 0.012 * Math.sin(t * 1.6)) *
        (1 + (reduce ? 0 : 11 * zt * zt * zt));

      ctx.save();
      ctx.translate(CX, CY + bob);
      ctx.rotate(rot);
      ctx.scale(br, br);
      ctx.translate(-CX, -CY);

      // 4. Photographic underlay fading in as brain stem activates
      if (img.complete && img.naturalWidth) {
        ctx.globalAlpha = Math.min(1, (isLightMode ? 0.06 : 0.12) + 0.6 * p + 0.25 * flash) * fade;
        ctx.drawImage(img, CX - (IW * K) / 2, CY - (IH * K) / 2, IW * K, IH * K);
      }

      // 5. Half-res glow layer composited once
      gctx.clearRect(0, 0, W, H);
      gctx.globalCompositeOperation = isLightMode ? "source-over" : "lighter";
      for (let j = 0; j < N; j++) {
        const A = act[j];
        const F = fl[j];
        if (A < 0.03 && F < 0.03) continue;
        const rr = (22 + 26 * A + 24 * F) * K;
        gctx.globalAlpha = (isLightMode ? 0.18 : 0.3) * A + 0.4 * F;
        gctx.drawImage(
          sprites[F > 0.25 ? 1 : nr[j]],
          sx[j] - rr,
          sy[j] - rr,
          rr * 2,
          rr * 2
        );
      }
      gctx.globalAlpha = 0.6;
      for (let j = 0; j < pulses.length; j++) {
        const pu = pulses[j];
        const px = sx[pu.a] + (sx[pu.b] - sx[pu.a]) * pu.t;
        const py = sy[pu.a] + (sy[pu.b] - sy[pu.a]) * pu.t;
        gctx.drawImage(sprites[1], px - 9, py - 9, 18, 18);
      }

      ctx.globalCompositeOperation = isLightMode ? "source-over" : "lighter";
      ctx.globalAlpha = fade;
      ctx.drawImage(gcv, 0, 0, W, H);
      ctx.globalCompositeOperation = "source-over";

      // 6. Silhouette rim glow
      ctx.globalAlpha = Math.min(1, 0.15 + 0.7 * p + 0.25 * flash) * fade;
      ctx.drawImage(rimCv, 0, 0, W, H);

      // 7. Synapses (batched by region into 4 single-stroke paths)
      const batchedEdges: [number, number][][] = [[], [], [], []];
      for (let j = 0; j < E; j++) {
        const a = D.e[2 * j];
        const b = D.e[2 * j + 1];
        const m = Math.min(act[a], act[b]);
        if (m < 0.03) continue;
        const bucket = m > 0.5 ? nr[a] + 1 : 0;
        batchedEdges[bucket].push([a, b]);
      }

      const gc = [palette.muted, palette.pink, palette.amber, palette.teal];
      const ga = [
        isLightMode ? 0.2 : 0.12,
        0.42 + 0.3 * flash,
        0.42 + 0.3 * flash,
        0.42 + 0.3 * flash,
      ];
      ctx.lineWidth = 1;
      for (let g = 0; g < 4; g++) {
        const edges = batchedEdges[g];
        if (!edges.length) continue;
        ctx.globalAlpha = ga[g] * fade;
        ctx.strokeStyle = gc[g];
        ctx.beginPath();
        for (let k = 0; k < edges.length; k++) {
          const [u, v] = edges[k];
          ctx.moveTo(sx[u], sy[u]);
          ctx.lineTo(sx[v], sy[v]);
        }
        ctx.stroke();
      }

      // 8. Signal comet trails
      ctx.fillStyle = isLightMode ? palette.pink : "#ffffff";
      for (let tl = 0; tl < 4; tl++) {
        ctx.globalAlpha = (0.95 - tl * 0.22) * fade;
        ctx.beginPath();
        for (let j = 0; j < pulses.length; j++) {
          const pu = pulses[j];
          const tt = Math.max(0, pu.t - tl * 0.05);
          const qx = sx[pu.a] + (sx[pu.b] - sx[pu.a]) * tt;
          const qy = sy[pu.a] + (sy[pu.b] - sy[pu.a]) * tt;
          const qr = Math.max(0.9, 2.7 - tl * 0.55);
          ctx.moveTo(qx + qr, qy);
          ctx.arc(qx, qy, qr, 0, 6.283);
        }
        ctx.fill();
      }

      // 9. Arrival impact ripple
      ctx.strokeStyle = palette.amber;
      ctx.lineWidth = 1.2;
      ctx.globalAlpha = 0.4 * fade;
      ctx.beginPath();
      for (let j = 0; j < N; j++) {
        if (fl[j] > 0.15) {
          const rrr = 4 + (1 - fl[j]) * 18;
          ctx.moveTo(sx[j] + rrr, sy[j]);
          ctx.arc(sx[j], sy[j], rrr, 0, 6.283);
        }
      }
      ctx.stroke();

      // 10. Neurons (Resting, Awake, Firing)
      const tw = reduce ? 1 : 0.88 + 0.12 * Math.sin(t * 2.2);

      // Resting neurons
      ctx.globalAlpha = 0.4 * fade;
      ctx.fillStyle = palette.muted;
      ctx.beginPath();
      for (let j = 0; j < N; j++) {
        if (act[j] < 0.5) {
          ctx.moveTo(sx[j] + 1.5, sy[j]);
          ctx.arc(sx[j], sy[j], 1.5, 0, 6.283);
        }
      }
      ctx.fill();

      // Awake neurons
      ctx.globalAlpha = 0.95 * tw * fade;
      ctx.fillStyle = isLightMode ? palette.text : "#ffffff";
      ctx.beginPath();
      for (let j = 0; j < N; j++) {
        if (act[j] >= 0.5 && fl[j] <= 0.2) {
          const r = 1.8 + 1.6 * act[j] + 1.4 * flash;
          ctx.moveTo(sx[j] + r, sy[j]);
          ctx.arc(sx[j], sy[j], r, 0, 6.283);
        }
      }
      ctx.fill();

      // Firing neurons
      ctx.globalAlpha = fade;
      ctx.fillStyle = palette.amber;
      ctx.beginPath();
      for (let j = 0; j < N; j++) {
        if (fl[j] > 0.2) {
          const r2 = 3 + 2.2 * fl[j];
          ctx.moveTo(sx[j] + r2, sy[j]);
          ctx.arc(sx[j], sy[j], r2, 0, 6.283);
        }
      }
      ctx.fill();

      ctx.restore();

      // Finale ring expansion at 100%
      if (ring >= 0 && ring < 1) {
        ring += dt * 1.2;
        ctx.globalAlpha = Math.max(0, 1 - ring) * 0.8;
        ctx.strokeStyle = palette.amber;
        ctx.lineWidth = 2.4;
        ctx.beginPath();
        ctx.arc(CX, CY, K * IW * (0.2 + ring * 0.9), 0, 6.283);
        ctx.stroke();
      }

      flash *= Math.exp(-dt * 2.4);
      ctx.globalAlpha = 1;
      return on;
    }

    // Main animation loop
    function loop(now: number) {
      const dt = Math.max(0.001, Math.min(0.05, (now - lastTime) / 1000 || 0.0167));
      lastTime = now;

      target = Math.max(0, getSimTarget(now));
      shown += (target - shown) * (1 - Math.exp(-dt * 4));
      if (target >= 100 && shown > 99.5) shown = 100;

      const on = render(now, dt);
      const v = Math.round(shown);

      setPercent(v);
      setNeuronsOnline(on);

      // Active stage message
      let activeStageIdx = 0;
      stages.forEach((stg, idx) => {
        if (shown >= stg.pct - (idx === stages.length - 1 ? 0.5 : 0)) {
          activeStageIdx = idx;
        }
      });
      if (activeStageIdx !== lastStep) {
        lastStep = activeStageIdx;
        setStageMsg(stages[activeStageIdx]?.message || "Brain online");
      }

      // Finale trigger upon reaching 100%
      if (shown >= 100 && !finished) {
        finished = true;
        flash = 1;
        ring = 0;

        const zoomDelay = reduce ? 60 : Math.min(300, Math.max(100, Math.round(durationMs * 0.1)));
        const finishDelay = reduce ? 250 : Math.min(750, Math.max(300, Math.round(durationMs * 0.25)));
        const dismissDelay = reduce ? 180 : Math.min(450, Math.max(200, Math.round(durationMs * 0.15)));

        timeouts.push(
          setTimeout(
            () => {
              zoomStart = performance.now();
              setIsZooming(true);
            },
            zoomDelay
          )
        );

        timeouts.push(
          setTimeout(
            () => {
              setIsDone(true);
              onCompleteRef.current?.();
              if (autoDismiss && variant === "fullscreen") {
                timeouts.push(
                  setTimeout(() => {
                    setIsDismissed(true);
                  }, dismissDelay)
                );
              }
            },
            finishDelay
          )
        );
      }

      // Frame rate monitoring: adapt DPR cap if performance drops
      avgDelta = avgDelta * 0.95 + dt * 0.05;
      frameCount++;
      if (frameCount > 45 && avgDelta > 0.027 && dprCap > 1) {
        dprCap = 1;
        resizeCanvas();
        avgDelta = 0.0167;
      }

      rafId = requestAnimationFrame(loop);
    }

    // Setup window resize handler
    window.addEventListener("resize", resizeCanvas);
    rafId = requestAnimationFrame(loop);

    return () => {
      cancelAnimationFrame(rafId);
      window.removeEventListener("resize", resizeCanvas);
      timeouts.forEach(clearTimeout);
    };
  }, [
    runKey,
    palette,
    isDark,
    externalProgress,
    durationMs,
    stages,
    variant,
    autoDismiss,
  ]);

  if (isDismissed) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      role="progressbar"
      aria-label="Loading AI Memoryverse Brain"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={percent}
      onClick={clickToDismiss && variant === "fullscreen" && !isDone ? handleFastForward : undefined}
      style={{
        ["--bg" as string]: palette.bg,
        ["--bg2" as string]: palette.bg2,
        ["--text" as string]: palette.text,
        ["--muted" as string]: palette.muted,
        ["--pink" as string]: palette.pink,
        ["--amber" as string]: palette.amber,
        ["--teal" as string]: palette.teal,
      }}
      className={`relative overflow-hidden select-none font-sans transition-all duration-700 ${
        variant === "fullscreen"
          ? "fixed inset-0 z-[9999] min-h-screen w-screen flex flex-col"
          : "w-full min-h-[460px] rounded-2xl border border-white/10 shadow-2xl"
      } ${isDone && autoDismiss && variant === "fullscreen" ? "opacity-0 scale-105 pointer-events-none" : "opacity-100"} ${className}`}
    >
      <style jsx>{`
        .loader-bg {
          background: radial-gradient(60% 55% at 50% 42%, var(--bg2), var(--bg));
        }
        .aura-layer {
          position: absolute;
          inset: 0;
          opacity: 0.12;
          will-change: opacity;
          background: radial-gradient(
            50% 44% at 50% 40%,
            color-mix(in srgb, var(--pink) 42%, transparent),
            transparent 72%
          );
        }
        .bloom-sphere {
          position: absolute;
          left: 50%;
          top: 40%;
          width: 160vmax;
          height: 160vmax;
          margin: -80vmax 0 0 -80vmax;
          border-radius: 50%;
          pointer-events: none;
          background: radial-gradient(
            circle,
            color-mix(in srgb, var(--pink) 60%, transparent),
            transparent 58%
          );
          transform: scale(0.04);
          opacity: 0;
          will-change: transform, opacity;
          transition: transform 1.7s cubic-bezier(0.45, 0, 0.85, 0.45),
            opacity 0.9s ease 0.35s;
        }
        .zoom-active .bloom-sphere {
          transform: scale(1);
          opacity: 0.55;
        }
        .logo-reveal {
          position: absolute;
          inset: 0;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: 16px;
          opacity: 0;
          transform: scale(0.72);
          pointer-events: none;
          transition: opacity 0.7s ease 1.1s,
            transform 1.2s cubic-bezier(0.2, 0.7, 0.2, 1) 1.1s;
        }
        .zoom-active .logo-reveal {
          opacity: 1;
          transform: none;
        }
        .logo-mark {
          width: min(34vmin, 150px);
          height: auto;
          overflow: visible;
        }
        .logo-mark path,
        .logo-mark .ring-shape {
          stroke-dasharray: 340;
          stroke-dashoffset: 340;
          transition: stroke-dashoffset 1s ease 1.2s;
        }
        .zoom-active .logo-mark .ring-shape {
          stroke-dashoffset: 0;
        }
        .zoom-active .logo-mark path {
          stroke-dashoffset: 0;
          transition: stroke-dashoffset 1s ease 1.6s;
        }
        .hud-layer {
          transition: opacity 0.4s ease;
        }
        .zoom-active .hud-layer,
        .zoom-active .brand-corner {
          opacity: 0;
          pointer-events: none;
        }
        @media (prefers-reduced-motion: reduce) {
          .zoom-active .logo-reveal,
          .zoom-active .logo-mark path,
          .zoom-active .logo-mark .ring-shape,
          .zoom-active .bloom-sphere {
            transition: none !important;
            transform: none !important;
          }
        }
      `}</style>

      {/* Main radial ambient canvas backdrop */}
      <div className="loader-bg absolute inset-0" />

      {/* Volumetric aura glow */}
      <div ref={auraRef} className="aura-layer" />

      {/* Primary Neural Canvas */}
      <canvas
        ref={canvasRef}
        className={`absolute inset-0 w-full h-full transform-gpu transition-opacity duration-500 ${
          isZooming ? "opacity-0" : "opacity-100"
        }`}
      />

      {/* Finale bloom sphere */}
      <div className={`bloom-sphere ${isZooming ? "zoom-active" : ""}`} />

      {/* Finale Logo Mark & Reveal */}
      <div
        className={`logo-reveal ${isZooming ? "zoom-active" : ""}`}
        aria-hidden={!isZooming}
      >
        <svg className="logo-mark" viewBox="0 0 120 120">
          <circle
            className="ring-shape"
            cx="60"
            cy="60"
            r="54"
            fill="none"
            stroke="var(--pink)"
            strokeWidth="3.2"
          />
          <path
            d="M30 84V38L60 66L90 38V84"
            fill="none"
            stroke="var(--text)"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <g fill="var(--amber)">
            <circle cx="30" cy="38" r="6" />
            <circle cx="60" cy="66" r="6" />
            <circle cx="90" cy="38" r="6" />
            <circle cx="30" cy="84" r="6" />
            <circle cx="90" cy="84" r="6" />
          </g>
        </svg>

        <div className="text-center">
          <div className="text-2xl sm:text-3xl md:text-4xl font-extrabold tracking-tight text-[var(--text)]">
            AI-MemoryVerse <span className="font-light text-[var(--pink)]">Brain</span>
          </div>
          <div className="text-xs sm:text-sm text-[var(--muted)] mt-1 font-mono tracking-wide">
            Your intelligence, grounded & connected.
          </div>
        </div>

        {showReplay && isDone && (
          <button
            type="button"
            onClick={handleRestart}
            className="mt-4 pointer-events-auto inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-semibold bg-[var(--pink)] text-white shadow-lg hover:brightness-110 active:scale-95 transition-all"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>Replay Neural Boot</span>
          </button>
        )}
      </div>

      {/* Top Brand corner */}
      <div className={`brand-corner absolute top-6 left-6 z-20 flex items-center space-x-2.5 transition-opacity ${isZooming ? "opacity-0 pointer-events-none" : "opacity-100"}`}>
        <div className="w-7 h-7 rounded-lg bg-[var(--pink)]/20 border border-[var(--pink)]/50 flex items-center justify-center">
          <div className="w-2.5 h-2.5 rounded-full bg-[var(--pink)] animate-ping" />
        </div>
        <div className="text-sm font-semibold tracking-tight text-[var(--text)]">
          AI-MemoryVerse <span className="font-light text-[var(--muted)]">· External Brain</span>
        </div>
      </div>

      {/* Top right theme toggle and controls */}
      <div className="absolute top-6 right-6 z-20 flex items-center space-x-2">
        {showThemeToggle && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              toggleStoreTheme();
            }}
            title={`Switch to ${isDark ? "Light" : "Dark"} theme`}
            className="p-2 rounded-full bg-black/10 dark:bg-white/10 hover:bg-black/20 dark:hover:bg-white/20 text-[var(--text)] border border-[var(--pink)]/20 backdrop-blur-md transition-all active:scale-90"
          >
            {isDark ? <Sun className="w-4 h-4 text-amber-300" /> : <Moon className="w-4 h-4 text-indigo-900" />}
          </button>
        )}

        {onDismiss && (
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDismiss();
            }}
            title="Close loader"
            className="p-2 rounded-full bg-black/20 dark:bg-white/10 hover:bg-black/30 dark:hover:bg-white/20 text-[var(--text)] border border-[var(--pink)]/30 backdrop-blur-md transition-all active:scale-90"
          >
            <X className="w-4 h-4" />
          </button>
        )}

        {clickToDismiss && variant === "fullscreen" && !isDone && (
          <span className="hidden sm:inline-block text-[11px] font-mono text-[var(--muted)] bg-black/10 dark:bg-white/5 px-2.5 py-1 rounded-full border border-white/5 opacity-70">
            Click anywhere to enter
          </span>
        )}
      </div>

      {/* Bottom HUD readout */}
      <div
        className={`hud-layer absolute left-0 right-0 bottom-8 z-20 text-center px-4 ${
          isZooming ? "opacity-0 pointer-events-none" : "opacity-100"
        }`}
      >
        <div className="font-light text-4xl sm:text-5xl md:text-6xl tracking-tighter tabular-nums text-[var(--text)]">
          <span>{percent}</span>
          <small className="text-sm sm:text-base font-semibold text-[var(--pink)] ml-1">
            %
          </small>
        </div>

        <div
          className="mt-2 text-sm sm:text-base font-semibold text-[var(--text)] tracking-wide"
          aria-live="polite"
        >
          {stageMsg}
        </div>

        <div className="mt-1 text-xs text-[var(--muted)] font-mono tabular-nums tracking-wider">
          {neuronsOnline} of {BRAIN_MODEL.r.length} neurons online
        </div>
      </div>
    </div>
  );
}
