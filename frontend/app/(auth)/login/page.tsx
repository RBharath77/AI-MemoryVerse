"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Lock, Mail, ArrowRight, AlertCircle, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { Logo } from "@/components/ui/logo";

export default function LoginPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await api.post("/auth/login", { email, password });
      if (!res.success) {
        setError(res.error?.message || "Invalid credentials. Please try again.");
        setIsLoading(false);
        return;
      }

      const { user, tokens, default_workspace_id } = res.data;
      setAuth(user, tokens.access_token, default_workspace_id);
      router.push("/dashboard");
    } catch (err: any) {
      setError(err.message || "An unexpected error occurred.");
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#F8F3F0] dark:bg-navy-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 transition-colors">
      <div className="sm:mx-auto sm:w-full sm:max-w-md text-center">
        <Link href="/" className="inline-block">
          <Logo size="lg" />
        </Link>
        <h2 className="mt-6 text-center text-2xl font-bold tracking-tight text-[#282B4A] dark:text-white">
          Sign in to your External Brain
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600 dark:text-slate-400">
          Or{" "}
          <Link
            href="/register"
            className="font-semibold text-[#014BAA] hover:underline dark:text-cyan-400 dark:hover:text-cyan-300 transition-colors"
          >
            create a new personal account
          </Link>
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md px-4 sm:px-0">
        <div className="bg-white dark:bg-navy-900/60 border border-[#EEEBDA] dark:border-navy-800 py-8 px-6 shadow-xl rounded-2xl sm:px-10 backdrop-blur">
          {error && (
            <div className="mb-6 p-4 rounded-xl border border-red-500/30 bg-red-950/30 text-red-400 text-sm flex items-start space-x-3">
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          <form className="space-y-5" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider"
              >
                Email address
              </label>
              <div className="mt-1.5 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Mail className="h-4 w-4" />
                </div>
                <input
                  id="email"
                  name="email"
                  type="email"
                  autoComplete="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 rounded-lg text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#014BAA] focus:border-[#014BAA] sm:text-sm"
                  placeholder="you@domain.com"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider"
                >
                  Password
                </label>
                <a
                  href="#"
                  className="text-xs font-semibold text-[#014BAA] hover:underline dark:text-cyan-400 dark:hover:text-cyan-300"
                >
                  Forgot password?
                </a>
              </div>
              <div className="mt-1.5 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 rounded-lg text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#014BAA] focus:border-[#014BAA] sm:text-sm"
                  placeholder="••••••••"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-sm font-bold text-[#F8F3F0] bg-[#014BAA] hover:bg-[#014BAA]/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#014BAA] shadow-md shadow-[#014BAA]/25 transition-all disabled:opacity-50"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin text-[#F8F3F0]" />
                  <span>Signing in...</span>
                </>
              ) : (
                <>
                  <span>Sign In</span>
                  <ArrowRight className="w-4 h-4 ml-2 text-[#F8F3F0]" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

