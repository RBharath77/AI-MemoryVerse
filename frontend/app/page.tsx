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

export default function LandingPage() {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div className="min-h-screen bg-navy-950 text-slate-100 flex flex-col">
      {/* Top Navigation */}
      <header className="border-b border-navy-800/80 bg-navy-950/80 backdrop-blur sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-lg shadow-cyan-500/20">
              <Brain className="w-5 h-5 text-white" />
            </div>
            <span className="font-bold text-lg tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-white via-slate-200 to-cyan-400">
              AI-MemoryVerse
            </span>
          </div>

          <nav className="hidden md:flex items-center space-x-8 text-sm font-medium text-slate-300">
            <a href="#features" className="hover:text-cyan-400 transition-colors">
              Features
            </a>
            <a href="#how-it-works" className="hover:text-cyan-400 transition-colors">
              How it Works
            </a>
            <a href="#security" className="hover:text-cyan-400 transition-colors">
              Security & Privacy
            </a>
            <a href="#pricing" className="hover:text-cyan-400 transition-colors">
              Pricing
            </a>
            <a href="#faq" className="hover:text-cyan-400 transition-colors">
              FAQ
            </a>
          </nav>

          <div className="flex items-center space-x-4">
            {isAuthenticated ? (
              <Link
                href="/dashboard"
                className="px-4 py-2 rounded-lg bg-cyan-500 text-navy-950 font-semibold text-sm hover:bg-cyan-400 transition-colors shadow-lg shadow-cyan-500/20 flex items-center space-x-2"
              >
                <span>Enter Workspace</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  href="/login"
                  className="text-sm font-medium text-slate-300 hover:text-white transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  href="/register"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-cyan-500 to-blue-600 text-white font-medium text-sm hover:from-cyan-400 hover:to-blue-500 transition-all shadow-lg shadow-cyan-500/25"
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
        <div className="inline-flex items-center space-x-2 px-3 py-1.5 rounded-full border border-cyan-500/30 bg-cyan-950/30 text-cyan-400 text-xs font-medium mb-8">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Announcing AI-MemoryVerse 1.0 — Persistent Long-Term Memory for AI</span>
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight max-w-4xl mx-auto leading-tight sm:leading-none">
          The Personal Knowledge Platform That{" "}
          <span className="bg-clip-text text-transparent bg-gradient-to-r from-cyan-400 via-blue-400 to-violet-400">
            Never Forgets.
          </span>
        </h1>

        <p className="mt-6 text-lg sm:text-xl text-slate-400 max-w-2xl mx-auto font-normal">
          Remember. Connect. Understand. Retrieve. Transform your conversations, documents,
          and scattered facts into a structured, source-grounded external brain with zero hallucinations.
        </p>

        <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
          <Link
            href="/register"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-cyan-500 text-navy-950 font-bold text-base hover:bg-cyan-400 transition-all shadow-xl shadow-cyan-500/25 flex items-center justify-center space-x-2"
          >
            <span>Start Building Memory</span>
            <ArrowRight className="w-5 h-5" />
          </Link>
          <a
            href="#how-it-works"
            className="w-full sm:w-auto px-8 py-3.5 rounded-xl border border-navy-700 bg-navy-900/60 text-slate-200 font-semibold text-base hover:bg-navy-800 transition-colors"
          >
            View Live Architecture
          </a>
        </div>

        {/* Feature Highlights Grid */}
        <div id="features" className="mt-24 grid grid-cols-1 md:grid-cols-3 gap-8 text-left">
          <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/40 hover:border-cyan-500/40 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
              <Brain className="w-6 h-6 text-cyan-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Human-in-the-Loop Memory</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Categorizes memories into episodic, semantic, project, and preference domains. Inferred facts are held in a review inbox so you maintain absolute control over what is remembered.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/40 hover:border-blue-500/40 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-blue-950/80 border border-blue-500/30 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
              <FileText className="w-6 h-6 text-blue-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Document Intelligence</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Asynchronous parsing of PDFs, Word docs, spreadsheets, slides, and markdown with recursive character chunking and pgvector embeddings.
            </p>
          </div>

          <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/40 hover:border-violet-500/40 transition-all group">
            <div className="w-12 h-12 rounded-xl bg-violet-950/80 border border-violet-500/30 flex items-center justify-center mb-5 group-hover:scale-105 transition-transform">
              <GitFork className="w-6 h-6 text-violet-400" />
            </div>
            <h3 className="text-lg font-bold text-white mb-2">Relational Knowledge Graph</h3>
            <p className="text-sm text-slate-400 leading-relaxed">
              Automatically discovers entities, projects, technologies, and relationships across all documents and conversations, rendered in an interactive visual explorer.
            </p>
          </div>
        </div>

        {/* How It Works */}
        <div id="how-it-works" className="mt-28 text-center">
          <h2 className="text-3xl font-bold tracking-tight text-white">How AI-MemoryVerse Works</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto text-sm">
            From raw input to verified citations — an end-to-end cognitive architecture.
          </p>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-4 gap-6 text-left">
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <span className="text-xs font-mono font-bold text-cyan-400">01 / CAPTURE</span>
              <h4 className="text-base font-bold text-white mt-2 mb-1">Upload & Converse</h4>
              <p className="text-xs text-slate-400">Chat with the assistant or upload documents into your private workspace.</p>
            </div>
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <span className="text-xs font-mono font-bold text-blue-400">02 / EXTRACT</span>
              <h4 className="text-base font-bold text-white mt-2 mb-1">Extract & Deduplicate</h4>
              <p className="text-xs text-slate-400">AI extracts candidate facts and checks for duplicates and contradictions.</p>
            </div>
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <span className="text-xs font-mono font-bold text-violet-400">03 / APPROVE</span>
              <h4 className="text-base font-bold text-white mt-2 mb-1">Human Review</h4>
              <p className="text-xs text-slate-400">Review, edit, or approve candidate facts into your permanent Memory Vault.</p>
            </div>
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <span className="text-xs font-mono font-bold text-emerald-400">04 / RETRIEVE</span>
              <h4 className="text-base font-bold text-white mt-2 mb-1">Hybrid Retrieval</h4>
              <p className="text-xs text-slate-400">Dense vector similarity combined with full-text search yields verified source citations.</p>
            </div>
          </div>
        </div>

        {/* Security Section */}
        <div id="security" className="mt-28 p-8 sm:p-12 rounded-3xl border border-navy-800 bg-navy-900/50 text-left">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 mb-8">
            <div>
              <div className="inline-flex items-center space-x-2 text-cyan-400 text-xs font-bold uppercase tracking-wider mb-2">
                <ShieldCheck className="w-4 h-4" />
                <span>Zero-Trust Architecture</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold text-white">Security & Privacy First</h2>
            </div>
            <Link
              href="/register"
              className="px-5 py-2.5 rounded-lg bg-navy-800 hover:bg-navy-700 text-slate-200 text-sm font-semibold transition-colors"
            >
              Read Security Whitepaper
            </Link>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 text-sm">
            <div className="space-y-1">
              <h4 className="font-semibold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Tenant Isolation</span>
              </h4>
              <p className="text-xs text-slate-400">Every database query and vector retrieval strictly filters by workspace ID.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Argon2id Passwords</span>
              </h4>
              <p className="text-xs text-slate-400">State-of-the-art memory-hard password hashing with salted digests.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Prompt Injection Defense</span>
              </h4>
              <p className="text-xs text-slate-400">Untrusted document content is isolated and barred from overriding system rules.</p>
            </div>
            <div className="space-y-1">
              <h4 className="font-semibold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Permanent Deletion</span>
              </h4>
              <p className="text-xs text-slate-400">Complete GDPR-compliant data export and irreversible cascade deletion options.</p>
            </div>
          </div>
        </div>

        {/* Pricing Tiers */}
        <div id="pricing" className="mt-28">
          <h2 className="text-3xl font-bold tracking-tight text-white">Transparent, Scalable Plans</h2>
          <p className="mt-3 text-slate-400 max-w-xl mx-auto text-sm">
            Start free. Upgrade as your personal knowledge base expands.
          </p>

          <div className="mt-12 grid grid-cols-1 md:grid-cols-4 gap-6 text-left">
            {/* Free */}
            <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Free</h3>
                <p className="text-xs text-slate-400 mt-1">For exploring personal AI memory</p>
                <div className="mt-4 mb-6">
                  <span className="text-3xl font-extrabold text-white">$0</span>
                  <span className="text-xs text-slate-400"> / month</span>
                </div>
                <ul className="space-y-2.5 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Up to 100 Memories</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>5 Document Uploads (10MB max)</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>1 Workspace</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Community Support</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/register"
                className="mt-8 block text-center py-2 px-4 rounded-lg bg-navy-800 hover:bg-navy-700 text-white font-semibold text-xs transition-colors"
              >
                Get Started
              </Link>
            </div>

            {/* Personal */}
            <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Personal</h3>
                <p className="text-xs text-slate-400 mt-1">For researchers & knowledge workers</p>
                <div className="mt-4 mb-6">
                  <span className="text-3xl font-extrabold text-white">$12</span>
                  <span className="text-xs text-slate-400"> / month</span>
                </div>
                <ul className="space-y-2.5 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Unlimited Memories</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>50 Documents (25MB max)</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Knowledge Graph Explorer</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Voice Chat Mode</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/register"
                className="mt-8 block text-center py-2 px-4 rounded-lg bg-navy-800 hover:bg-navy-700 text-white font-semibold text-xs transition-colors"
              >
                Try Personal
              </Link>
            </div>

            {/* Pro */}
            <div className="p-6 rounded-2xl border-2 border-cyan-500 bg-navy-900/60 shadow-xl shadow-cyan-500/10 flex flex-col justify-between relative">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full bg-cyan-500 text-navy-950 font-bold text-[10px] uppercase tracking-wide">
                Most Popular
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Pro</h3>
                <p className="text-xs text-slate-400 mt-1">For advanced power users</p>
                <div className="mt-4 mb-6">
                  <span className="text-3xl font-extrabold text-white">$29</span>
                  <span className="text-xs text-slate-400"> / month</span>
                </div>
                <ul className="space-y-2.5 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Unlimited Memories & Docs</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Automated Research Assistant</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Custom LLM Provider Keys</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Priority Background Worker</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/register"
                className="mt-8 block text-center py-2 px-4 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold text-xs transition-colors shadow-lg shadow-cyan-500/20"
              >
                Start Pro Trial
              </Link>
            </div>

            {/* Team */}
            <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 flex flex-col justify-between">
              <div>
                <h3 className="text-lg font-bold text-white">Team</h3>
                <p className="text-xs text-slate-400 mt-1">For collaborative workspaces</p>
                <div className="mt-4 mb-6">
                  <span className="text-3xl font-extrabold text-white">$79</span>
                  <span className="text-xs text-slate-400"> / month</span>
                </div>
                <ul className="space-y-2.5 text-xs text-slate-300">
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Shared Team Workspaces</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>RBAC Role Permissions</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Audit Logs & Security Center</span>
                  </li>
                  <li className="flex items-center space-x-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-cyan-400" />
                    <span>Dedicated Support SLA</span>
                  </li>
                </ul>
              </div>
              <Link
                href="/register"
                className="mt-8 block text-center py-2 px-4 rounded-lg bg-navy-800 hover:bg-navy-700 text-white font-semibold text-xs transition-colors"
              >
                Contact Sales
              </Link>
            </div>
          </div>
        </div>

        {/* FAQ Section */}
        <div id="faq" className="mt-28 max-w-3xl mx-auto text-left">
          <h2 className="text-3xl font-bold tracking-tight text-white text-center">Frequently Asked Questions</h2>
          <div className="mt-10 space-y-6">
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <h4 className="font-bold text-white text-sm">How does AI-MemoryVerse prevent hallucinations?</h4>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                We combine hybrid vector search (pgvector) with PostgreSQL lexical search. Every claim produced by the AI is mapped to concrete chunk citations. If evidence is insufficient, the system explicitly acknowledges the gap rather than inventing facts.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <h4 className="font-bold text-white text-sm">Can other users or administrators read my private memories?</h4>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                No. Tenant isolation is enforced at the database query level with workspace and user ID foreign key constraints. Administrator roles only access aggregate system metrics, not personal memory payloads.
              </p>
            </div>
            <div className="p-5 rounded-xl border border-navy-800 bg-navy-900/30">
              <h4 className="font-bold text-white text-sm">Can I export or delete all of my data?</h4>
              <p className="text-xs text-slate-400 mt-2 leading-relaxed">
                Yes. Full data exports (JSON format) and cascade permanent deletions are available under Settings &gt; Privacy at any time.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-navy-800/80 bg-navy-950 py-12 px-4 sm:px-6 lg:px-8 text-xs text-slate-500">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
          <div className="flex items-center space-x-3">
            <div className="w-6 h-6 rounded bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain className="w-3.5 h-3.5 text-white" />
            </div>
            <span className="font-bold text-slate-300">AI-MemoryVerse</span>
            <span>&copy; {new Date().getFullYear()} All rights reserved.</span>
          </div>

          <div className="flex items-center space-x-6 text-slate-400">
            <Link href="/privacy" className="hover:text-cyan-400 transition-colors">Privacy Policy</Link>
            <Link href="/terms" className="hover:text-cyan-400 transition-colors">Terms of Service</Link>
            <Link href="/security" className="hover:text-cyan-400 transition-colors">Security Architecture</Link>
            <a href="https://github.com/BharathR/AI-MemoryVerse" target="_blank" rel="noreferrer" className="hover:text-cyan-400 transition-colors">GitHub</a>
          </div>
        </div>
      </footer>
    </div>
  );
}

