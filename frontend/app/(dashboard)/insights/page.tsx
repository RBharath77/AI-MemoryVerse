"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  AlertTriangle,
  Clock,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  X,
  RefreshCw,
  Loader2,
  ShieldAlert,
  GitFork,
  Lightbulb,
  ExternalLink,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface InsightItem {
  id: string;
  workspace_id: string;
  insight_type: string;
  title: string;
  description: string;
  suggested_action: string;
  related_entity_id?: string | null;
  related_memory_ids: string[];
  is_dismissed: boolean;
  created_at: string;
}

const INSIGHT_STYLES: Record<
  string,
  { label: string; icon: any; border: string; bg: string; text: string }
> = {
  stale_knowledge: {
    label: "Stale Knowledge",
    icon: Clock,
    border: "border-amber-500/40",
    bg: "bg-amber-500/10",
    text: "text-amber-400",
  },
  contradiction_alert: {
    label: "Conflict / Review Flag",
    icon: AlertTriangle,
    border: "border-rose-500/40",
    bg: "bg-rose-500/10",
    text: "text-rose-400",
  },
  knowledge_gap: {
    label: "Knowledge Gap",
    icon: Lightbulb,
    border: "border-indigo-500/40",
    bg: "bg-indigo-500/10",
    text: "text-indigo-400",
  },
  trending_topic: {
    label: "Central Graph Hub",
    icon: GitFork,
    border: "border-emerald-500/40",
    bg: "bg-emerald-500/10",
    text: "text-emerald-400",
  },
  consolidation_opportunity: {
    label: "Consolidation",
    icon: Sparkles,
    border: "border-purple-500/40",
    bg: "bg-purple-500/10",
    text: "text-purple-400",
  },
};

export default function SmartInsightsPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [insights, setInsights] = useState<InsightItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [showDismissed, setShowDismissed] = useState(false);

  const fetchInsights = async () => {
    setIsLoading(true);
    try {
      const endpoint = showDismissed
        ? "/research/insights?include_dismissed=true"
        : "/research/insights";
      const res = await api.get<{ items: InsightItem[]; total: number }>(endpoint);
      if (res.success && res.data) {
        setInsights(res.data.items || []);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchInsights();
  }, [activeWorkspaceId, showDismissed]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      const res = await api.post<{ items: InsightItem[]; total: number }>(
        "/research/insights/refresh"
      );
      if (res.success && res.data) {
        setInsights(res.data.items || []);
      }
    } finally {
      setIsRefreshing(false);
    }
  };

  const handleDismiss = async (id: string) => {
    try {
      const res = await api.post(`/research/insights/${id}/dismiss`);
      if (res.success) {
        setInsights((prev) => prev.filter((i) => i.id !== id));
      }
    } catch (e) {
      console.error(e);
    }
  };

  // Grouped stats
  const staleCount = insights.filter((i) => i.insight_type === "stale_knowledge").length;
  const conflictCount = insights.filter((i) => i.insight_type === "contradiction_alert").length;
  const gapCount = insights.filter((i) => i.insight_type === "knowledge_gap").length;
  const hubCount = insights.filter((i) => i.insight_type === "trending_topic").length;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Brain className="h-6 w-6 text-purple-400" />
            Smart Knowledge Insights
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Proactive observations, conflict detections, knowledge gaps, and vault hygiene recommendations.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400 flex items-center gap-2 cursor-pointer bg-slate-900 border border-slate-800 px-3 py-2 rounded-lg">
            <input
              type="checkbox"
              checked={showDismissed}
              onChange={(e) => setShowDismissed(e.target.checked)}
              className="rounded border-slate-700 bg-slate-950 text-purple-600 focus:ring-purple-500"
            />
            Show Dismissed
          </label>

          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="flex items-center gap-2 px-3.5 py-2 text-sm font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-500 transition-all shadow-lg shadow-purple-900/30 disabled:opacity-50"
          >
            {isRefreshing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Scan & Refresh
          </button>
        </div>
      </div>

      {/* KPI Ribbon */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Stale Facts
            </span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-1">{staleCount}</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Inbox Flags
            </span>
            <AlertTriangle className="h-4 w-4 text-rose-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-1">{conflictCount}</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Knowledge Gaps
            </span>
            <Lightbulb className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-1">{gapCount}</p>
        </div>

        <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/60 backdrop-blur">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400 uppercase tracking-wider">
              Graph Hubs
            </span>
            <GitFork className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="text-2xl font-bold text-white mt-1">{hubCount}</p>
        </div>
      </div>

      {/* Insights Cards Grid */}
      <div className="space-y-4">
        {isLoading ? (
          <div className="p-16 text-center">
            <Loader2 className="h-8 w-8 text-purple-400 animate-spin mx-auto" />
            <p className="text-sm text-slate-400 mt-3">Analyzing memory database...</p>
          </div>
        ) : insights.length === 0 ? (
          <div className="p-12 rounded-2xl border border-slate-800 bg-slate-950/60 text-center">
            <CheckCircle2 className="h-12 w-12 text-emerald-400 mx-auto mb-3" />
            <h3 className="text-lg font-semibold text-white">Your Knowledge Vault is Clean</h3>
            <p className="text-sm text-slate-400 max-w-md mx-auto mt-1 mb-6">
              No contradictions, stale records, or missing project documentation detected. Click 'Scan & Refresh' anytime to re-audit.
            </p>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 text-sm font-medium rounded-lg bg-slate-800 text-slate-200 border border-slate-700 hover:bg-slate-700"
            >
              Re-scan Vault
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {insights.map((ins) => {
              const style =
                INSIGHT_STYLES[ins.insight_type] || INSIGHT_STYLES.knowledge_gap;
              const Icon = style.icon;

              return (
                <div
                  key={ins.id}
                  className={`rounded-2xl border ${style.border} bg-slate-900/60 p-5 flex flex-col justify-between shadow-xl backdrop-blur relative group`}
                >
                  <div>
                    {/* Badge & Dismiss */}
                    <div className="flex items-center justify-between gap-2 mb-3">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded-full ${style.bg} ${style.text} flex items-center gap-1.5`}
                      >
                        <Icon className="h-3 w-3" />
                        {style.label}
                      </span>

                      {!ins.is_dismissed && (
                        <button
                          onClick={() => handleDismiss(ins.id)}
                          className="text-slate-500 hover:text-slate-300 p-1 rounded-lg hover:bg-slate-800 transition-all"
                          title="Dismiss insight"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      )}
                    </div>

                    <h3 className="text-base font-semibold text-white mb-1.5">{ins.title}</h3>
                    <p className="text-xs text-slate-400 leading-relaxed">{ins.description}</p>
                  </div>

                  {/* Action Banner */}
                  <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between">
                    <p className="text-[11px] font-medium text-slate-300">
                      <span className="text-purple-400 font-semibold">Suggested: </span>
                      {ins.suggested_action}
                    </p>

                    {ins.insight_type === "contradiction_alert" ? (
                      <Link
                        href="/memory-review"
                        className="flex items-center gap-1 text-xs font-semibold text-purple-400 hover:text-purple-300 whitespace-nowrap ml-3"
                      >
                        Inbox <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    ) : ins.insight_type === "trending_topic" ? (
                      <Link
                        href="/graph"
                        className="flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300 whitespace-nowrap ml-3"
                      >
                        Graph <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    ) : (
                      <Link
                        href="/memories"
                        className="flex items-center gap-1 text-xs font-semibold text-purple-400 hover:text-purple-300 whitespace-nowrap ml-3"
                      >
                        Vault <ArrowRight className="h-3.5 w-3.5" />
                      </Link>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

