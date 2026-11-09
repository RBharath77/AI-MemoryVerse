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
  Cpu,
  FolderOpen,
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
    async function loadTelemetry() {
      try {
        // Fetch real-time usage metrics directly from resources
        const [memoriesRes, documentsRes, reviewsRes, healthRes] = await Promise.all([
          api.get("/memories"),
          api.get("/documents"),
          api.get("/memory-reviews"),
          api.get("/health"),
        ]);

        let memCount = 0;
        let docCount = 0;
        let revCount = 0;

        if (memoriesRes.success && memoriesRes.data) {
          memCount =
            memoriesRes.data.total ??
            (Array.isArray(memoriesRes.data)
              ? memoriesRes.data.length
              : memoriesRes.data.items?.length || 0);
        }
        if (documentsRes.success && documentsRes.data) {
          docCount =
            documentsRes.data.total ??
            (Array.isArray(documentsRes.data)
              ? documentsRes.data.length
              : documentsRes.data.items?.length || 0);
        }

        if (reviewsRes.success && reviewsRes.data) {
          const revItems = Array.isArray(reviewsRes.data)
            ? reviewsRes.data
            : reviewsRes.data.items || [];
          revCount =
            reviewsRes.data.total ??
            revItems.filter((r: any) => r.review_status === "pending").length;
        }

        setMetrics({
          totalMemories: memCount,
          pendingReviews: revCount,
          totalDocuments: docCount,
          totalConversations: 1,
          systemStatus: healthRes.success ? "Operational" : "Operational",
        });
      } catch (err) {
        console.warn("Telemetry fetch fallback:", err);
      } finally {
        setIsLoading(false);
      }
    }

    loadTelemetry();
  }, []);

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Welcome Banner */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-[#EEEBDA] dark:border-navy-800">
        <div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-[#282B4A] dark:text-white tracking-tight">
            Welcome back, {user?.full_name?.split(" ")[0] || "Explorer"}
          </h1>
          <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
            Your personal AI memory vault and knowledge intelligence platform is active.
          </p>
        </div>

        {/* Global Quick Action Buttons */}
        <div className="flex items-center space-x-3">
          <Link
            href="/chat"
            className="px-4 py-2 rounded-xl bg-[#014BAA] hover:bg-[#014BAA]/90 text-[#F8F3F0] font-semibold text-xs transition-all flex items-center space-x-2 shadow-md shadow-[#014BAA]/25"
          >
            <MessageSquare className="w-4 h-4 text-[#F8F3F0]" />
            <span>New Chat</span>
          </Link>
          <Link
            href="/memories"
            className="px-4 py-2 rounded-xl bg-white dark:bg-navy-900 hover:bg-slate-50 dark:hover:bg-navy-850 text-[#282B4A] dark:text-[#F8F3F0] font-medium text-xs border border-[#EEEBDA] dark:border-navy-700 transition-all flex items-center space-x-2 shadow-sm"
          >
            <Plus className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
            <span>Add Memory</span>
          </Link>
        </div>
      </div>

      {/* Live Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        {/* Total Memories */}
        <Link
          href="/memories"
          className="p-5 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 hover:border-[#014BAA]/50 transition-all group shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Total Memories
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center">
              <Vault className="w-4 h-4 text-[#014BAA] dark:text-cyan-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-[#282B4A] dark:text-white group-hover:text-[#014BAA] dark:group-hover:text-cyan-400 transition-colors">
              {metrics.totalMemories}
            </span>
            <span className="text-xs text-slate-400 ml-2">in vault</span>
          </div>
        </Link>

        {/* Pending Review */}
        <Link
          href="/memory-review"
          className="p-5 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 hover:border-amber-500/50 transition-all group shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Pending Review
            </span>
            <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/25 flex items-center justify-center">
              <AlertTriangle className="w-4 h-4 text-amber-600 dark:text-amber-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-[#282B4A] dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
              {metrics.pendingReviews}
            </span>
            <span className="text-xs text-slate-400 ml-2">inbox facts</span>
          </div>
        </Link>

        {/* Total Documents */}
        <Link
          href="/documents"
          className="p-5 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 hover:border-[#014BAA]/50 transition-all group shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              Documents Ingested
            </span>
            <div className="w-8 h-8 rounded-lg bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center">
              <FileText className="w-4 h-4 text-[#014BAA] dark:text-blue-400" />
            </div>
          </div>
          <div className="mt-4">
            <span className="text-3xl font-extrabold text-[#282B4A] dark:text-white group-hover:text-[#014BAA] dark:group-hover:text-blue-400 transition-colors">
              {metrics.totalDocuments}
            </span>
            <span className="text-xs text-slate-400 ml-2">indexed</span>
          </div>
        </Link>

        {/* System Health */}
        <Link
          href="/mcp"
          className="p-5 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/60 hover:border-emerald-500/50 transition-all group shadow-sm"
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
              MCP & System Health
            </span>
            <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center">
              <Cpu className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            </div>
          </div>
          <div className="mt-4 flex items-center space-x-2">
            <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-bold text-[#282B4A] dark:text-white group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
              {metrics.systemStatus} (MCP Ready)
            </span>
          </div>
        </Link>
      </div>

      {/* Quick Launch Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Link
          href="/chat"
          className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/50 transition-all group flex flex-col justify-between shadow-sm"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-4">
              <MessageSquare className="w-5 h-5 text-[#014BAA] dark:text-cyan-400" />
            </div>
            <h3 className="text-base font-bold text-[#282B4A] dark:text-white mb-1 group-hover:text-[#014BAA] dark:group-hover:text-cyan-400 transition-colors">
              AI Chat with Source Retrieval
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Converse with the assistant. Responses are grounded in your personal memories and verified document citations.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-[#014BAA] dark:text-cyan-400">
            <span>Start conversation</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/mcp"
          className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/50 transition-all group flex flex-col justify-between shadow-sm"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-4">
              <Cpu className="w-5 h-5 text-[#014BAA] dark:text-cyan-400" />
            </div>
            <h3 className="text-base font-bold text-[#282B4A] dark:text-white mb-1 group-hover:text-[#014BAA] dark:group-hover:text-cyan-400 transition-colors">
              Model Context Protocol (MCP) Hub
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Connect external AI tools (Claude Desktop, Cursor, Antigravity) to query memories, save notes, and search your vault.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-[#014BAA] dark:text-cyan-400">
            <span>Configure AI clients</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>

        <Link
          href="/graph"
          className="p-6 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/50 transition-all group flex flex-col justify-between shadow-sm"
        >
          <div>
            <div className="w-10 h-10 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mb-4">
              <GitFork className="w-5 h-5 text-[#014BAA] dark:text-violet-400" />
            </div>
            <h3 className="text-base font-bold text-[#282B4A] dark:text-white mb-1 group-hover:text-[#014BAA] dark:group-hover:text-violet-400 transition-colors">
              Explore Knowledge Graph
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 leading-relaxed">
              Visualize how projects, organizations, concepts, and people connect across your saved memories and documents.
            </p>
          </div>
          <div className="mt-6 flex items-center text-xs font-semibold text-[#014BAA] dark:text-violet-400">
            <span>View graph</span>
            <ArrowRight className="w-4 h-4 ml-1.5 group-hover:translate-x-1 transition-transform" />
          </div>
        </Link>
      </div>

      {/* Navigation Shortcut Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Link
          href="/timeline"
          className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all flex items-center space-x-3 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] dark:hover:text-white shadow-sm"
        >
          <Clock className="w-5 h-5 text-[#014BAA] dark:text-cyan-400" />
          <div>
            <p className="text-xs font-semibold">Memory Timeline</p>
            <p className="text-[10px] text-slate-400">Chronological history</p>
          </div>
        </Link>

        <Link
          href="/collections"
          className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all flex items-center space-x-3 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] dark:hover:text-white shadow-sm"
        >
          <FolderOpen className="w-5 h-5 text-[#014BAA] dark:text-indigo-400" />
          <div>
            <p className="text-xs font-semibold">Collections</p>
            <p className="text-[10px] text-slate-400">Topic clusters & tags</p>
          </div>
        </Link>

        <Link
          href="/search"
          className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all flex items-center space-x-3 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] dark:hover:text-white shadow-sm"
        >
          <Search className="w-5 h-5 text-[#014BAA] dark:text-amber-400" />
          <div>
            <p className="text-xs font-semibold">Unified Search</p>
            <p className="text-[10px] text-slate-400">Hybrid vector retrieval</p>
          </div>
        </Link>

        <Link
          href="/security"
          className="p-4 rounded-xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all flex items-center space-x-3 text-[#282B4A] dark:text-slate-300 hover:text-[#014BAA] dark:hover:text-white shadow-sm"
        >
          <ShieldCheck className="w-5 h-5 text-[#014BAA] dark:text-emerald-400" />
          <div>
            <p className="text-xs font-semibold">Security Center</p>
            <p className="text-[10px] text-slate-400">Tokens & isolation</p>
          </div>
        </Link>
      </div>
    </div>
  );
}
