"use client";

import { useEffect, useState } from "react";
import {
  Inbox,
  CheckCircle2,
  XCircle,
  Edit3,
  Sparkles,
  BookOpen,
  Calendar,
  Briefcase,
  UserCheck,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface CandidateMemory {
  id: string;
  content: string;
  category: string;
  confidence: number;
  source_type: string;
  source_id?: string;
  created_at: string;
}

export default function MemoryReviewInboxPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [candidates, setCandidates] = useState<CandidateMemory[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // In Phase 2, query memories pending review
    setIsLoading(true);
    api.get("/memories?status=pending_review").then((res) => {
      if (res.success && res.data) {
        setCandidates(res.data.items || []);
      }
      setIsLoading(false);
    });
  }, [activeWorkspaceId]);

  const handleApprove = async (id: string) => {
    const res = await api.patch(`/memories/${id}`, { status: "approved" });
    if (res.success) {
      setCandidates(candidates.filter((c) => c.id !== id));
    }
  };

  const handleReject = async (id: string) => {
    const res = await api.delete(`/memories/${id}`);
    if (res.success) {
      setCandidates(candidates.filter((c) => c.id !== id));
    }
  };

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <Inbox className="w-6 h-6 text-amber-400" />
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Memory Review Inbox
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Human-in-the-loop review. Approve or discard candidate facts automatically extracted by AI.
          </p>
        </div>

        <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-navy-900 border border-navy-700 text-slate-300">
          {candidates.length} pending review
        </span>
      </div>

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
          <p className="text-xs">Checking review inbox...</p>
        </div>
      ) : candidates.length === 0 ? (
        <div className="py-16 px-4 rounded-2xl border border-navy-800 bg-navy-900/20 text-center">
          <div className="w-12 h-12 rounded-xl bg-navy-900 border border-navy-700 flex items-center justify-center mx-auto mb-4 text-emerald-400">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white mb-1">Inbox is Clear</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            All extracted memories have been reviewed and approved. New candidates will appear here during conversations and document ingestion.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {candidates.map((candidate) => (
            <div
              key={candidate.id}
              className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40 hover:border-navy-700 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
            >
              <div className="space-y-2 flex-1">
                <div className="flex items-center space-x-2">
                  <span className="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded bg-amber-950/80 border border-amber-500/30 text-amber-400">
                    Candidate Fact
                  </span>
                  <span className="text-[10px] font-mono text-slate-400">
                    Confidence: {Math.round((candidate.confidence || 0.9) * 100)}%
                  </span>
                </div>
                <p className="text-xs sm:text-sm text-slate-100 leading-relaxed">
                  {candidate.content}
                </p>
                <div className="text-[11px] text-slate-500 flex items-center space-x-4">
                  <span>Source: {candidate.source_type}</span>
                  <span>Extracted: {formatDate(candidate.created_at)}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center space-x-2 shrink-0">
                <button
                  onClick={() => handleReject(candidate.id)}
                  className="px-3 py-1.5 rounded-lg border border-navy-700 hover:border-red-500/40 hover:bg-red-950/20 text-slate-400 hover:text-red-400 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                >
                  <XCircle className="w-4 h-4" />
                  <span>Reject</span>
                </button>
                <button
                  onClick={() => handleApprove(candidate.id)}
                  className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-md shadow-emerald-500/20"
                >
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Approve to Vault</span>
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
