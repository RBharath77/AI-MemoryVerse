"use client";

import { useEffect, useState } from "react";
import {
  BookOpen,
  Sparkles,
  Calendar,
  FileText,
  Clock,
  Plus,
  Trash2,
  Download,
  CheckCircle2,
  Layers,
  ArrowRight,
  Loader2,
  X,
  FileCheck,
  ChevronRight,
  Filter,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface ResearchReportItem {
  id: string;
  workspace_id: string;
  user_id: string;
  title: string;
  topic: string;
  report_type: string;
  status: string;
  content_markdown: string;
  key_findings: string[];
  action_items: string[];
  sources_used: Array<{ source_id: string; title: string; type: string; score: number }>;
  created_at: string;
}

export default function ResearchLabPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [reports, setReports] = useState<ResearchReportItem[]>([]);
  const [selectedReport, setSelectedReport] = useState<ResearchReportItem | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [filterType, setFilterType] = useState<string>("all");

  // Modal
  const [isGenerateOpen, setIsGenerateOpen] = useState(false);
  const [newReport, setNewReport] = useState({
    topic: "",
    report_type: "topic_research",
    days_back: 30,
  });

  const fetchReports = async () => {
    setIsLoading(true);
    try {
      const endpoint =
        filterType === "all"
          ? "/research/reports"
          : `/research/reports?report_type=${filterType}`;
      const res = await api.get<{ items: ResearchReportItem[]; total: number }>(endpoint);
      if (res.success && res.data) {
        setReports(res.data.items || []);
        if (res.data.items.length > 0 && !selectedReport) {
          setSelectedReport(res.data.items[0]);
        }
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchReports();
  }, [activeWorkspaceId, filterType]);

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newReport.topic.trim()) return;

    setIsGenerating(true);
    try {
      const res = await api.post("/research/generate", newReport);
      if (res.success && res.data) {
        setIsGenerateOpen(false);
        setNewReport({ topic: "", report_type: "topic_research", days_back: 30 });
        await fetchReports();
        setSelectedReport(res.data);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDelete = async (reportId: string) => {
    if (!confirm("Are you sure you want to delete this research report?")) return;
    try {
      const res = await api.delete(`/research/reports/${reportId}`);
      if (res.success) {
        if (selectedReport?.id === reportId) {
          setSelectedReport(null);
        }
        await fetchReports();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const downloadMarkdown = (report: ResearchReportItem) => {
    const element = document.createElement("a");
    const file = new Blob([report.content_markdown], { type: "text/markdown" });
    element.href = URL.createObjectURL(file);
    element.download = `${report.topic.toLowerCase().replace(/\s+/g, "_")}_report.md`;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <BookOpen className="h-6 w-6 text-purple-400" />
            Research Lab & Knowledge Reports
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Automated multi-document syntheses, daily executive digests, and deep-dive topic briefs.
          </p>
        </div>

        <button
          onClick={() => setIsGenerateOpen(true)}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-500 transition-all shadow-lg shadow-purple-900/30"
        >
          <Sparkles className="h-4 w-4" />
          Generate New Report
        </button>
      </div>

      {/* Main Layout: Reports List & Detail View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Reports List */}
        <div className="lg:col-span-4 space-y-4">
          {/* Filter Bar */}
          <div className="flex items-center justify-between p-2 rounded-xl bg-slate-900/60 border border-slate-800">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider px-2">
              Filter:
            </span>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-2.5 py-1 text-xs text-slate-300 focus:outline-none focus:border-purple-500"
            >
              <option value="all">All Reports</option>
              <option value="topic_research">Topic Research</option>
              <option value="daily_digest">Daily Digests</option>
              <option value="weekly_summary">Weekly Summaries</option>
              <option value="project_brief">Project Briefs</option>
            </select>
          </div>

          {/* List items */}
          <div className="space-y-2 max-h-[680px] overflow-y-auto pr-1">
            {isLoading ? (
              <div className="p-8 text-center">
                <Loader2 className="h-6 w-6 text-purple-400 animate-spin mx-auto" />
              </div>
            ) : reports.length === 0 ? (
              <div className="p-8 rounded-xl border border-slate-800 bg-slate-950/40 text-center">
                <FileText className="h-8 w-8 text-slate-600 mx-auto mb-2" />
                <p className="text-sm font-medium text-slate-300">No reports generated yet</p>
                <p className="text-xs text-slate-500 mt-1">
                  Click 'Generate New Report' to synthesize your knowledge vault.
                </p>
              </div>
            ) : (
              reports.map((r) => {
                const isSelected = selectedReport?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => setSelectedReport(r)}
                    className={`p-3.5 rounded-xl border cursor-pointer transition-all ${
                      isSelected
                        ? "bg-purple-950/30 border-purple-500/50 shadow-lg shadow-purple-900/10"
                        : "bg-slate-900/50 border-slate-800/80 hover:border-slate-700"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="text-[10px] uppercase font-bold tracking-wider px-2 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20">
                        {r.report_type.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] text-slate-500">
                        {formatDate(r.created_at)}
                      </span>
                    </div>

                    <h4 className="text-sm font-semibold text-white truncate">{r.title}</h4>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                      {r.key_findings?.[0] || "Synthesis across verified memory facts and documents."}
                    </p>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Active Report Viewer */}
        <div className="lg:col-span-8">
          {selectedReport ? (
            <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-6 space-y-6 shadow-2xl">
              {/* Report Header Bar */}
              <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b border-slate-800">
                <div>
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className="text-xs uppercase font-bold tracking-wider px-2.5 py-0.5 rounded-full bg-purple-500/15 text-purple-300 border border-purple-500/30">
                      {selectedReport.report_type.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-slate-400 flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      Generated {formatDate(selectedReport.created_at)}
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white">{selectedReport.title}</h2>
                </div>

                <div className="flex items-center gap-2">
                  <button
                    onClick={() => downloadMarkdown(selectedReport)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-900 border border-slate-800 text-slate-200 hover:text-white hover:bg-slate-800 transition-all"
                  >
                    <Download className="h-3.5 w-3.5" />
                    Download MD
                  </button>
                  <button
                    onClick={() => handleDelete(selectedReport.id)}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg text-rose-400 bg-rose-500/10 border border-rose-500/20 hover:bg-rose-500/20 transition-all"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Delete
                  </button>
                </div>
              </div>

              {/* Key Findings Ribbon */}
              {selectedReport.key_findings && selectedReport.key_findings.length > 0 && (
                <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-500/20 space-y-2">
                  <h4 className="text-xs font-bold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Sparkles className="h-3.5 w-3.5 text-purple-400" />
                    Key Executive Findings
                  </h4>
                  <ul className="space-y-1.5">
                    {selectedReport.key_findings.map((f, i) => (
                      <li key={i} className="text-xs text-slate-200 flex items-start gap-2">
                        <span className="text-purple-400 font-bold">•</span>
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Markdown Content */}
              <div className="prose prose-invert prose-purple max-w-none text-sm leading-relaxed text-slate-200 whitespace-pre-wrap">
                {selectedReport.content_markdown}
              </div>

              {/* Action Items */}
              {selectedReport.action_items && selectedReport.action_items.length > 0 && (
                <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                  <h4 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                    Recommended Action Items
                  </h4>
                  <div className="space-y-1.5">
                    {selectedReport.action_items.map((action, i) => (
                      <label key={i} className="flex items-start gap-2 text-xs text-slate-300">
                        <input
                          type="checkbox"
                          className="mt-0.5 rounded border-slate-700 bg-slate-900 text-purple-600 focus:ring-purple-500"
                        />
                        <span>{action}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}

              {/* Sources Used */}
              {selectedReport.sources_used && selectedReport.sources_used.length > 0 && (
                <div className="pt-2">
                  <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">
                    Verified Sources Consulted ({selectedReport.sources_used.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedReport.sources_used.map((s, i) => (
                      <span
                        key={i}
                        className="text-[11px] px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center gap-1.5"
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                        <span className="font-medium text-white">{s.title}</span>
                        <span className="text-slate-500 font-mono">[{s.type}]</span>
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-12 text-center h-full flex flex-col items-center justify-center">
              <BookOpen className="h-10 w-10 text-slate-600 mb-3" />
              <h3 className="text-lg font-semibold text-white">Select a Research Report</h3>
              <p className="text-sm text-slate-400 max-w-sm mt-1">
                Choose a report from the list on the left or create a new automated topic report.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* MODAL: Generate Report */}
      {isGenerateOpen && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-2xl">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-purple-400" />
                Synthesize Knowledge Report
              </h3>
              <button
                onClick={() => setIsGenerateOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleGenerate} className="mt-4 space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Topic or Subject *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. System Architecture, Project Apollo, Security Audit"
                  value={newReport.topic}
                  onChange={(e) => setNewReport({ ...newReport, topic: e.target.value })}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Report Type *
                </label>
                <select
                  value={newReport.report_type}
                  onChange={(e) =>
                    setNewReport({ ...newReport, report_type: e.target.value })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                >
                  <option value="topic_research">Topic Research Synthesis</option>
                  <option value="daily_digest">Daily Knowledge Digest</option>
                  <option value="weekly_summary">Weekly Executive Summary</option>
                  <option value="project_brief">Project Architecture Brief</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Timeframe (Days Back)
                </label>
                <input
                  type="number"
                  min={1}
                  max={365}
                  value={newReport.days_back}
                  onChange={(e) =>
                    setNewReport({ ...newReport, days_back: Number(e.target.value) })
                  }
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-sm text-white focus:outline-none focus:border-purple-500"
                />
                <span className="text-[10px] text-slate-500 mt-1 block">
                  Pulls memories and documents created or updated within the last {newReport.days_back} days.
                </span>
              </div>

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsGenerateOpen(false)}
                  className="px-4 py-2 text-sm text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isGenerating || !newReport.topic.trim()}
                  className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg bg-purple-600 text-white hover:bg-purple-500 disabled:opacity-50"
                >
                  {isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Synthesizing...
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      Generate Report
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
