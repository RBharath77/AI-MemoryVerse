"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Lock,
  Mail,
  User,
  Briefcase,
  ArrowRight,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Circle,
  Eye,
  EyeOff,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { Logo } from "@/components/ui/logo";

export default function RegisterPage() {
  const router = useRouter();
  const setAuth = useAuthStore((state) => state.setAuth);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [workspaceName, setWorkspaceName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  // Password Complexity Validation Rules
  const hasMinLength = password.length >= 8;
  const hasUppercase = /[A-Z]/.test(password);
  const hasLowercase = /[a-z]/.test(password);
  const hasDigit = /\d/.test(password);
  const hasSymbol = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?`~]/.test(password);

  const passedRules = [hasMinLength, hasUppercase, hasLowercase, hasDigit, hasSymbol].filter(Boolean).length;
  const isPasswordValid = hasMinLength && hasUppercase && hasLowercase && hasDigit && hasSymbol;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!isPasswordValid) {
      setError(
        "Please meet all password requirements: at least 8 characters, with uppercase, lowercase, numbers, and special symbols."
      );
      return;
    }

    setIsLoading(true);

    try {
      const res = await api.post("/auth/register", {
        full_name: fullName,
        email,
        password,
        workspace_name: workspaceName || undefined,
      });

      if (!res.success) {
        setError(res.error?.message || "Registration failed. Please check your details.");
        setIsLoading(false);
        return;
      }

      const { user, tokens, workspace } = res.data;
      setAuth(user, tokens.access_token, workspace.id);
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
          Create your Personal AI Memory
        </h2>
        <p className="mt-2 text-center text-sm text-slate-600 dark:text-slate-400">
          Already registered?{" "}
          <Link
            href="/login"
            className="font-semibold text-[#014BAA] hover:underline dark:text-cyan-400 dark:hover:text-cyan-300 transition-colors"
          >
            Sign in to existing account
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

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label
                htmlFor="fullName"
                className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider"
              >
                Full Name
              </label>
              <div className="mt-1.5 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User className="h-4 w-4" />
                </div>
                <input
                  id="fullName"
                  name="fullName"
                  type="text"
                  required
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 rounded-lg text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#014BAA] focus:border-[#014BAA] sm:text-sm"
                  placeholder="Ada Lovelace"
                />
              </div>
            </div>

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
                  placeholder="ada@computing.org"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="workspaceName"
                className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider"
              >
                Workspace Name (Optional)
              </label>
              <div className="mt-1.5 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Briefcase className="h-4 w-4" />
                </div>
                <input
                  id="workspaceName"
                  name="workspaceName"
                  type="text"
                  value={workspaceName}
                  onChange={(e) => setWorkspaceName(e.target.value)}
                  className="block w-full pl-10 pr-3 py-2.5 bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 rounded-lg text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#014BAA] focus:border-[#014BAA] sm:text-sm"
                  placeholder="e.g. Research & Engineering"
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between">
                <label
                  htmlFor="password"
                  className="block text-xs font-semibold text-[#282B4A] dark:text-slate-300 uppercase tracking-wider"
                >
                  Password Security
                </label>
                <span className="text-[10px] text-[#014BAA] dark:text-cyan-400 font-mono font-semibold">
                  {passedRules === 5 ? "Strong ✓" : `${passedRules}/5 Requirements`}
                </span>
              </div>
              <div className="mt-1.5 relative rounded-md shadow-sm">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock className="h-4 w-4" />
                </div>
                <input
                  id="password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="block w-full pl-10 pr-10 py-2.5 bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 rounded-lg text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-[#014BAA] focus:border-[#014BAA] sm:text-sm"
                  placeholder="Upper, lower, digit & symbol"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* Password Strength Meter */}
              {password.length > 0 && (
                <div className="mt-2 space-y-1.5">
                  <div className="w-full h-1.5 bg-slate-200 dark:bg-navy-950 rounded-full overflow-hidden border border-[#EEEBDA] dark:border-navy-800">
                    <div
                      className={`h-full transition-all duration-300 ${
                        passedRules <= 2
                          ? "bg-red-500 w-1/4"
                          : passedRules <= 4
                          ? "bg-amber-400 w-3/4"
                          : "bg-emerald-500 w-full"
                      }`}
                    />
                  </div>
                </div>
              )}

              {/* Real-time Password Rules Checklist */}
              <div className="mt-2.5 p-3 rounded-xl bg-[#F8F3F0] dark:bg-navy-950/80 border border-[#EEEBDA] dark:border-navy-800 space-y-1 text-[11px] font-mono">
                <div className="text-[10px] uppercase font-bold text-slate-500 dark:text-slate-400 pb-0.5 flex items-center space-x-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#014BAA] dark:text-cyan-400" />
                  <span>Required Password Pattern:</span>
                </div>

                <div className={`flex items-center space-x-2 ${hasMinLength ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-slate-500 dark:text-slate-400"}`}>
                  {hasMinLength ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <Circle className="w-3.5 h-3.5 shrink-0 opacity-40" />}
                  <span>At least 8 characters length</span>
                </div>

                <div className={`flex items-center space-x-2 ${hasUppercase ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-slate-500 dark:text-slate-400"}`}>
                  {hasUppercase ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <Circle className="w-3.5 h-3.5 shrink-0 opacity-40" />}
                  <span>At least one uppercase letter (A-Z)</span>
                </div>

                <div className={`flex items-center space-x-2 ${hasLowercase ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-slate-500 dark:text-slate-400"}`}>
                  {hasLowercase ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <Circle className="w-3.5 h-3.5 shrink-0 opacity-40" />}
                  <span>At least one lowercase letter (a-z)</span>
                </div>

                <div className={`flex items-center space-x-2 ${hasDigit ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-slate-500 dark:text-slate-400"}`}>
                  {hasDigit ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <Circle className="w-3.5 h-3.5 shrink-0 opacity-40" />}
                  <span>At least one numeric digit (0-9)</span>
                </div>

                <div className={`flex items-center space-x-2 ${hasSymbol ? "text-emerald-600 dark:text-emerald-400 font-semibold" : "text-slate-500 dark:text-slate-400"}`}>
                  {hasSymbol ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" /> : <Circle className="w-3.5 h-3.5 shrink-0 opacity-40" />}
                  <span>At least one special symbol (!@#$%^&*...)</span>
                </div>
              </div>
            </div>

            <p className="text-[11px] text-slate-500 dark:text-slate-400 pt-1">
              By creating an account, you agree to the Terms of Service and acknowledge the AI Memory Disclosure.
            </p>

            <button
              type="submit"
              disabled={isLoading || !isPasswordValid}
              className="w-full mt-2 flex justify-center items-center py-2.5 px-4 rounded-xl text-sm font-bold text-[#F8F3F0] bg-[#014BAA] hover:bg-[#014BAA]/90 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-[#014BAA] shadow-md shadow-[#014BAA]/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin text-[#F8F3F0]" />
                  <span>Creating external brain...</span>
                </>
              ) : (
                <>
                  <span>Create Account</span>
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
