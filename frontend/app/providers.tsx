"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React, { useState, useEffect } from "react";
import { useAuthStore } from "@/store/auth-store";
import { useThemeStore, Theme } from "@/store/theme-store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const initializeAuth = useAuthStore((state) => state.initialize);
  const setTheme = useThemeStore((state) => state.setTheme);

  useEffect(() => {
    initializeAuth();

    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("memoryverse_theme") as Theme | null;
      if (savedTheme === "light" || savedTheme === "dark") {
        setTheme(savedTheme);
      }
    }
  }, [initializeAuth, setTheme]);

  return (
    <QueryClientProvider client={queryClient}>
      {children}
    </QueryClientProvider>
  );
}
