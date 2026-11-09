"use client";

import Link from "next/link";
import {
  Brain,
  ShieldCheck,
  Sparkles,
  GitFork,
  FileText,
  Search,
  Lock,
  Zap,
  ArrowRight,
  CheckCircle2,
  Database,
  Cpu,
} from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Logo } from "@/components/ui/logo";

export default function LandingPage() {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div className="min-h-screen bg-[#F8F3F0] dark:bg-navy-950 text-[#282B4A] dark:text-slate-100 flex flex-col transition-colors">
      {/* Top Navigation */}
      <header className="border-b border-[#EEEBDA] dark:border-navy-800/80 bg-white/80 dark:bg-navy-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Logo size="md" href="/" />

          <nav className="hidden md:flex items-center space-x-8 text-sm font-semibold text-slate-600 dark:text-slate-300">
            <a href="#features" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">
              How it Works
            </a>
            <a href="#security" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">
              Security & Privacy
            </a>
            <a href="#faq" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">
              FAQ
            </a>
          </nav>

          <div className="flex items-center space-x-4">
            <ThemeToggle variant="pill" showLabels={false} />
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="px-4 py-2 rounded-xl bg-[#014BAA] text-[#F8F3F0] font-semibold text-sm hover:bg-[#014BAA]/90 transition-all shadow-md shadow-[#014BAA]/25 flex items-center space-x-2"
              >
                <span>Enter Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-sm font-semibold text-slate-600 hover:text-[#014BAA] dark:text-slate-300 dark:hover:text-white transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-2 rounded-xl bg-[#014BAA] text-[#F8F3F0] font-semibold text-sm hover:bg-[#014BAA]/90 transition-all shadow-md shadow-[#014BAA]/25"
                >
                  Get Started Free
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative pt-24 pb-20 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto text-center flex-1">
        <div className="inline-flex items-center space-x-2 px-3.5 py-1.5 rounded-full border border-[#014BAA]/30 bg-[#014BAA]/10 text-[#014BAA] dark:border-cyan-500/30 dark:bg-cyan-950/30 dark:text-cyan-400 text-xs font-semibold mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Announcing AI-MemoryVerse 1.0 — Persistent Long-Term Memory for AI</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight max-w-4xl mx-auto leading-tight sm:leading-none text-[#282B4A] dark:text-white">
          The Personal Knowledge Platform That{" "}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-[#014BAA] via-blue-600 to-indigo-600 dark:from-cyan-400 dark:via-blue-400 dark:to-violet-400">
            Never Forgets.
          </span>
        </h1>

        <p className="mt-6 text-lg sm:text-xl text-slate-600 dark:text-slate-400 max-w-2xl mx-auto font-normal leading-relaxed">
          Remember. Connect. Understand. Retrieve. Transform your conversations, documents,
          and scattered facts into a structured, source-grounded external brain with zero hallucinations.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/register"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-[#014BAA] text-[#F8F3F0] font-bold text-base hover:bg-[#014BAA]/90 transition-all shadow-lg shadow-[#014BAA]/25 flex items-center justify-center space-x-2"
          >
            <span>Start Building Memory</span>
            <ArrowRight className="w-5 h-5 text-[#F8F3F0]" />
          </Link>
          <a
            href="#how-it-works"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl border border-[#EEEBDA] dark:border-navy-700 bg-white dark:bg-navy-900/60 text-[#282B4A] dark:text-slate-200 font-semibold text-base hover:bg-slate-50 dark:hover:bg-navy-800 transition-colors shadow-sm"
          >
            View Live Architecture
          </a>
        </div>

        {/* Feature Highlights Grid */}
        <div id="features" className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
          <div className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all group shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform text-[#014BAA] dark:text-cyan-400">
              <Brain className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-[#282B4A] dark:text-white mb-2">Human-in-the-Loop Memory</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Categorizes memories into episodic, semantic, project, and preference domains. Inferred facts are held in a review inbox so you maintain absolute control over what is remembered.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all group shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform text-[#014BAA] dark:text-blue-400">
              <FileText className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-[#282B4A] dark:text-white mb-2">Document Intelligence</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Asynchronous parsing of PDFs, Word docs, spreadsheets, slides, and markdown with recursive character chunking and pgvector embeddings.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all group shadow-sm">
            <div className="w-12 h-12 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform text-[#014BAA] dark:text-violet-400">
              <GitFork className="w-6 h-6" />
            </div>
            <h3 className="text-lg font-bold text-[#282B4A] dark:text-white mb-2">Relational Knowledge Graph</h3>
            <p className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
              Automatically discovers entities, projects, technologies, and relationships across all documents and conversations, rendered in an interactive visual explorer.
            </p>
          </div>
        </div>

        {/* How It Works */}
        <div id="how-it-works" className="mt-28 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-[#282B4A] dark:text-white">How AI-MemoryVerse Works</h2>
          <p className="mt-3 text-slate-600 dark:text-slate-400 max-w-xl mx-auto text-sm">
            From raw input to verified citations — an end-to-end cognitive architecture.
          </p>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-4 gap-6 text-left">
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <span className="text-xs font-mono font-bold text-[#014BAA] dark:text-cyan-400">01 / CAPTURE</span>
              <h4 className="text-base font-bold text-[#282B4A] dark:text-white mt-2 mb-1">Upload & Converse</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Chat with the assistant or upload documents into your private workspace.</p>
            </div>
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <span className="text-xs font-mono font-bold text-[#014BAA] dark:text-blue-400">02 / EXTRACT</span>
              <h4 className="text-base font-bold text-[#282B4A] dark:text-white mt-2 mb-1">Extract & Deduplicate</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">AI extracts candidate facts and checks for duplicates and contradictions.</p>
            </div>
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <span className="text-xs font-mono font-bold text-[#014BAA] dark:text-violet-400">03 / APPROVE</span>
              <h4 className="text-base font-bold text-[#282B4A] dark:text-white mt-2 mb-1">Human Review</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Review, edit, or approve candidate facts into your permanent Memory Vault.</p>
            </div>
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <span className="text-xs font-mono font-bold text-emerald-600 dark:text-emerald-400">04 / RETRIEVE</span>
              <h4 className="text-base font-bold text-[#282B4A] dark:text-white mt-2 mb-1">Hybrid Retrieval</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Dense vector similarity combined with lexical search yields verified citations.</p>
            </div>
          </div>
        </div>

        {/* Security Section */}
        <div id="security" className="mt-28 p-8 sm:p-12 rounded-3xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/50 text-left shadow-sm">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8">
            <div>
              <div className="inline-flex items-center space-x-2 text-[#014BAA] dark:text-cyan-400 text-xs font-bold uppercase tracking-wider mb-2">
                <ShieldCheck className="w-4 h-4" />
                <span>Zero-Trust Architecture</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-[#282B4A] dark:text-white">Security & Privacy First</h2>
            </div>
            <Link
              href="/register"
              className="px-5 py-2.5 rounded-xl bg-[#F8F3F0] dark:bg-navy-800 hover:bg-[#EEEBDA] dark:hover:bg-navy-700 text-[#282B4A] dark:text-slate-200 text-sm font-semibold border border-[#EEEBDA] dark:border-navy-700 transition-colors shadow-xs"
            >
              Read Security Architecture
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-sm">
            <div className="space-y-1">
              <h4 className="font-semibold text-[#282B4A] dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
                <span>Tenant Isolation</span>
              </h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Every database query and vector retrieval strictly filters by workspace ID.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-[#282B4A] dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
                <span>Argon2id Passwords</span>
              </h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">State-of-the-art memory-hard password hashing with salted digests.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-[#282B4A] dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
                <span>Prompt Injection Defense</span>
              </h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Untrusted document content is isolated and barred from overriding system rules.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-[#282B4A] dark:text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
                <span>Permanent Deletion</span>
              </h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">Complete data export and irreversible cascade deletion options at any time.</p>
            </div>
          </div>
        </div>

        {/* FAQ Section */}
        <div id="faq" className="mt-28 max-w-3xl mx-auto text-left">
          <h2 className="text-3xl font-bold tracking-tight text-[#282B4A] dark:text-white text-center">Frequently Asked Questions</h2>
          <div className="mt-10 space-y-6">
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <h4 className="font-bold text-[#282B4A] dark:text-white text-sm">How does AI-MemoryVerse prevent hallucinations?</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                We combine hybrid vector search (pgvector) with PostgreSQL lexical search. Every claim produced by the AI is mapped to concrete chunk citations. If evidence is insufficient, the system explicitly acknowledges the gap rather than inventing facts.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <h4 className="font-bold text-[#282B4A] dark:text-white text-sm">Can other users or administrators read my private memories?</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                No. Tenant isolation is enforced at the database query level with workspace and user ID foreign key constraints. Administrator roles only access aggregate system metrics, not personal memory payloads.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/30 shadow-sm">
              <h4 className="font-bold text-[#282B4A] dark:text-white text-sm">Can I export or delete all of my data?</h4>
              <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 leading-relaxed">
                Yes. Full data exports (JSON format) and cascade permanent deletions are available under Settings &gt; Privacy at any time.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[#EEEBDA] dark:border-navy-800/80 bg-white dark:bg-navy-950 py-12 px-4 sm:px-6 lg:px-8 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center space-x-3">
            <Logo size="sm" />
            <span>&copy; {new Date().getFullYear()} All rights reserved.</span>
          </div>

          <div className="flex items-center space-x-6 text-slate-600 dark:text-slate-400">
            <Link href="/privacy" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">Terms of Service</Link>
            <Link href="/security" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">Security Architecture</Link>
            <a href="https://github.com/BharathR/AI-MemoryVerse" target="_blank" rel="noreferrer" className="hover:text-[#014BAA] dark:hover:text-cyan-400 transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
