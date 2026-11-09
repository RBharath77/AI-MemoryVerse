"use client";

import React from "react";
import Link from "next/link";
import { Brain } from "lucide-react";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  showText?: boolean;
  className?: string;
  href?: string | null;
}

export function Logo({
  size = "md",
  showText = true,
  className = "",
  href = "/dashboard",
}: LogoProps) {
  const iconSizes = {
    sm: "w-4 h-4",
    md: "w-5 h-5",
    lg: "w-6 h-6",
  };

  const boxSizes = {
    sm: "w-7 h-7 rounded-lg",
    md: "w-8 h-8 rounded-xl",
    lg: "w-10 h-10 rounded-2xl",
  };

  const textSizes = {
    sm: "text-sm",
    md: "text-base",
    lg: "text-2xl",
  };

  const content = (
    <div className={`inline-flex items-center space-x-2.5 select-none ${className}`}>
      {/* Signature Royal Blue (#014BAA) Box with Vanilla (#F8F3F0) Brain Icon */}
      <div
        data-logo-box="true"
        className={`logo-icon-box ${boxSizes[size]} flex items-center justify-center shrink-0 shadow-md transition-transform duration-200 hover:scale-105`}
        style={{
          backgroundColor: "#014BAA",
          boxShadow: "0 4px 12px rgba(1, 75, 170, 0.35)",
          border: "1px solid rgba(248, 243, 240, 0.25)",
        }}
        title="AI-MemoryVerse"
      >
        <Brain
          className={iconSizes[size]}
          style={{ color: "#F8F3F0", stroke: "#F8F3F0" }}
          stroke="#F8F3F0"
          strokeWidth={2.4}
        />
      </div>

      {showText && (
        <span className={`font-extrabold ${textSizes[size]} tracking-tight flex items-center whitespace-nowrap`}>
          <span className="font-black text-[#014BAA]">
            AI
          </span>
          <span className="text-slate-400 dark:text-slate-500 font-normal mx-0.5">-</span>
          <span className="font-extrabold text-[#282B4A] dark:text-[#F8F3F0] transition-colors">
            MemoryVerse
          </span>
        </span>
      )}
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-flex items-center group">
        {content}
      </Link>
    );
  }

  return content;
}
