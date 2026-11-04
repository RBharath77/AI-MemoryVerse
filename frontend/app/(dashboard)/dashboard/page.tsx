"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Brain,
  Vault,
  FileText,
  MessageSquare,
  Sparkles,
  ArrowRight,
  Plus,
  Search,
  Upload,
  GitFork,
  Clock,
  AlertTriangle,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

interface OverviewMetrics {
  totalMemories: number;
  pendingReviews: number;
  totalDocuments: number;
  totalConversations: number;
  systemStatus: string;
}

export default function DashboardOverviewPage() {
  const { user } = useAuthStore();
  const [metrics, setMetrics] = useState<OverviewMetrics>({
    totalMemories: 0,
    pendingReviews: 0,
    totalDocuments: 0,
    totalConversations: 0,
    systemStatus: "Operational",
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // In Phase 1/2, fetch readiness and initial counts
    api.get("/ready").then((res) => {
      if (res.success && res.data) {
        setMetrics((prev) => ({
          ...prev,
          systemStatus: res.data.database === "connected" ? "Operational" : "Degraded",
        }));
      }
      setIsLoading(false);
    });
  }, []);

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
            Welcome back, {user?.full_name?.split(" ")[0] || "Explorer"}
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Your personal AI memory vault and knowledge graph is active.
          </p>
        </div>

        {/* Global Quick Action Buttons */}
        <div className="flex items-center space-x-3">
          <Link
            href="/chat"
            className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs transition-colors flex items-center space-x-2 shadow-lg shadow-cyan-500/20"
          >
            <MessageSquare className="w-4 h-4" />
            <span>New Chat</span>
          </Link>
          <Link
            href="/memories"
            className="px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-700 text-white font-medium text-xs border border-navy-700 transition-colors flex items-center space-x-2"
          >
            <Plus className="w-4 h-4 text-cyan-400" />
            <span>Add Memory</span>
          </Link>
        </div>
      </div>

      {/* Live Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Memories */}
        <div className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Total Memories
            </span>
            <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center">
              <Vault className="w-4 h-4 text-cyan-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-white">
              {metrics.totalMemories}
            </span>
            <span className="text-xs text-slate-400 ml-2">in vault</span>
          </div>
        </div>

        {/* Pending Review */}
        <div className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Pending Review
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-950/80 border border-amber-500/30 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4 text-amber-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-white">
              {metrics.pendingReviews}
            </span>
            <span className="text-xs text-slate-400 ml-2">inbox facts</span>
          </div>
        </div>

        {/* Total Documents */}
        <div className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Documents Ingested
            </span>
            <div className="w-8 h-8 rounded-lg bg-blue-950/80 border border-blue-500/30 flex items-center justify-center">
              <FileText className="w-4 h-4 text-blue-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-white">
              {metrics.totalDocuments}
            </span>
            <span className="text-xs text-slate-400 ml-2">indexed</span>
          </div>
        </div>

        {/* System Health */}
        <div className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              System Health
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-950/80 border border-emerald-500/30 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
            </div>
          </div>
          <div className="mt-4 flex items-center space-x-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-sm font-bold text-white">
              {metrics.systemStatus}
            </span>
          </div>
        </div>
      </div>

      {/* Quick Launch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          href="/chat"
          className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 hover:border-cyan-500/40 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-500/30 flex items-center justify-center mb-4">
              <MessageSquare className="w-5 h-5 text-cyan-400" />
            </div>
            <h3 className="text-base font-bold text-white mb-1 group-hover:text-cyan-400 transition-colors">
              AI Chat with Source Retrieval
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Converse with the assistant. Responses are grounded in your personal memories and verified document citations.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-cyan-400">
            <span>Start conversation</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/documents"
          className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 hover:border-blue-500/40 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-blue-950/80 border border-blue-500/30 flex items-center justify-center mb-4">
              <Upload className="w-5 h-5 text-blue-400" />
            </div>
            <h3 className="text-base font-bold text-white mb-1 group-hover:text-blue-400 transition-colors">
              Ingest Documents
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Upload PDF, Word, spreadsheets, and markdown files. Background workers extract chunks and generate vector embeddings.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-blue-400">
            <span>Open library</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/graph"
          className="p-6 rounded-2xl border border-navy-800 bg-navy-900/30 hover:border-violet-500/40 transition-all group flex flex-col justify-between"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-violet-950/80 border border-violet-500/30 flex items-center justify-center mb-4">
              <GitFork className="w-5 h-5 text-violet-400" />
            </div>
            <h3 className="text-base font-bold text-white mb-1 group-hover:text-violet-400 transition-colors">
              Explore Knowledge Graph
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Visualize how projects, organizations, concepts, and people connect across your saved memories and documents.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-violet-400">
            <span>View graph</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>
      </div>

      {/* Empty State / Quick Instructions for New Users */}
      <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/20 text-left">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2 mb-3">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <span>Getting Started with AI-MemoryVerse</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-400">
          <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/80">
            <p className="font-semibold text-slate-200 mb-1">1. Add First Memory</p>
            <p>Save personal preferences, project context, or architectural decisions into the vault.</p>
          </div>
          <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/80">
            <p className="font-semibold text-slate-200 mb-1">2. Upload Source Documents</p>
            <p>Ingest notes or reference documents to enable hybrid retrieval and citation verification.</p>
          </div>
          <div className="p-3 rounded-lg bg-navy-950/60 border border-navy-800/80">
            <p className="font-semibold text-slate-200 mb-1">3. Ask Anything</p>
            <p>Query your external brain and get grounded, source-attributed answers across sessions.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
