"use client";

import { useEffect, useState } from "react";
import {
  Inbox,
  CheckCircle2,
  XCircle,
  Edit3,
  Loader2,
  AlertTriangle,
  X,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface MemoryReviewItem {
  id: string;
  workspace_id: string;
  memory_id: string;
  review_status: string;
  original_text: string;
  corrected_text?: string | null;
  review_notes?: string | null;
  created_at: string;
  memory?: {
    id: string;
    content: string;
    category: string;
    confidence: number;
    source_type: string;
    extra_metadata?: {
      conflict_detected?: boolean;
      conflict_type?: string;
      conflict_explanation?: string;
    };
  } | null;
}

export default function MemoryReviewInboxPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [reviews, setReviews] = useState<MemoryReviewItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [editingItem, setEditingItem] = useState<MemoryReviewItem | null>(null);
  const [correctedContent, setCorrectedContent] = useState("");
  const [reviewNotes, setReviewNotes] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchReviews = async () => {
    setIsLoading(true);
    const res = await api.get("/memory-reviews?status=pending");
    if (res.success && res.data) {
      setReviews(res.data.items || []);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      fetchReviews();
    }
  }, [activeWorkspaceId]);

  const handleApprove = async (reviewId: string) => {
    const res = await api.post(`/memory-reviews/${reviewId}/action`, {
      review_status: "approved",
    });
    if (res.success) {
      setReviews((prev) => prev.filter((r) => r.id !== reviewId));
    }
  };

  const handleReject = async (reviewId: string) => {
    const res = await api.post(`/memory-reviews/${reviewId}/action`, {
      review_status: "rejected",
    });
    if (res.success) {
      setReviews((prev) => prev.filter((r) => r.id !== reviewId));
    }
  };

  const openEditModal = (item: MemoryReviewItem) => {
    setEditingItem(item);
    setCorrectedContent(item.original_text);
    setReviewNotes(item.review_notes || "");
  };

  const handleCorrectAndApprove = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingItem || !correctedContent.trim()) return;

    setIsSubmitting(true);
    const res = await api.post(`/memory-reviews/${editingItem.id}/action`, {
      review_status: "corrected",
      corrected_text: correctedContent.trim(),
      review_notes: reviewNotes.trim() || "User corrected during review",
    });

    if (res.success) {
      setReviews((prev) => prev.filter((r) => r.id !== editingItem.id));
      setEditingItem(null);
    }
    setIsSubmitting(false);
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
            Human-in-the-loop review. Approve, correct, or reject candidate facts and conflicting memories.
          </p>
        </div>

        <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-navy-900 border border-navy-700 text-slate-300">
          {reviews.length} pending review
        </span>
      </div>

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-amber-400" />
          <p className="text-xs">Checking review inbox...</p>
        </div>
      ) : reviews.length === 0 ? (
        <div className="py-16 px-4 rounded-2xl border border-navy-800 bg-navy-900/20 text-center">
          <div className="w-12 h-12 rounded-xl bg-navy-900 border border-navy-700 flex items-center justify-center mx-auto mb-4 text-emerald-400">
            <CheckCircle2 className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white mb-1">Inbox is Clear</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            All extracted memories have been reviewed. New candidates will appear here during AI chats, document ingestion, or contradiction detection.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {reviews.map((item) => {
            const hasConflict =
              item.memory?.extra_metadata?.conflict_detected ||
              item.review_notes?.includes("Contradict") ||
              item.review_notes?.includes("Conflicting");
            return (
              <div
                key={item.id}
                className="p-5 rounded-2xl border border-navy-800 bg-navy-900/40 hover:border-navy-700 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div className="space-y-2 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                        hasConflict
                          ? "bg-red-950/80 border-red-500/40 text-red-400"
                          : "bg-amber-950/80 border-amber-500/30 text-amber-400"
                      }`}
                    >
                      {hasConflict ? "Contradiction Flagged" : "Candidate Fact"}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      Category: {item.memory?.category || "semantic"}
                    </span>
                    <span className="text-[10px] font-mono text-slate-400">
                      Confidence: {Math.round((item.memory?.confidence || 0.9) * 100)}%
                    </span>
                  </div>

                  <p className="text-xs sm:text-sm text-slate-100 leading-relaxed font-medium">
                    {item.original_text}
                  </p>

                  {/* Conflict Notice if present */}
                  {item.review_notes && (
                    <div className="p-2.5 rounded-lg border border-amber-500/30 bg-amber-950/20 text-amber-300 text-xs flex items-start space-x-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-amber-400" />
                      <span>{item.review_notes}</span>
                    </div>
                  )}

                  <div className="text-[11px] text-slate-500 flex items-center space-x-4">
                    <span>Source: {item.memory?.source_type || "extraction"}</span>
                    <span>Created: {formatDate(item.created_at)}</span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="flex items-center space-x-2 shrink-0">
                  <button
                    onClick={() => handleReject(item.id)}
                    className="px-3 py-1.5 rounded-lg border border-navy-700 hover:border-red-500/40 hover:bg-red-950/20 text-slate-400 hover:text-red-400 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                  >
                    <XCircle className="w-4 h-4" />
                    <span>Reject</span>
                  </button>
                  <button
                    onClick={() => openEditModal(item)}
                    className="px-3 py-1.5 rounded-lg border border-navy-700 hover:border-cyan-500/40 hover:bg-cyan-950/20 text-slate-300 hover:text-cyan-400 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                  >
                    <Edit3 className="w-4 h-4" />
                    <span>Edit & Approve</span>
                  </button>
                  <button
                    onClick={() => handleApprove(item.id)}
                    className="px-3 py-1.5 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors shadow-md shadow-emerald-500/20"
                  >
                    <CheckCircle2 className="w-4 h-4" />
                    <span>Approve</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Edit & Approve Modal */}
      {editingItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>Correct & Approve Fact</span>
              </h3>
              <button
                onClick={() => setEditingItem(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCorrectAndApprove} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Corrected Content
                </label>
                <textarea
                  required
                  rows={4}
                  value={correctedContent}
                  onChange={(e) => setCorrectedContent(e.target.value)}
                  className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Correction Reason / Note (Optional)
                </label>
                <input
                  type="text"
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                  placeholder="e.g. Corrected outdated preference."
                  className="w-full p-2.5 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-navy-800">
                <button
                  type="button"
                  onClick={() => setEditingItem(null)}
                  className="px-4 py-2 rounded-lg border border-navy-700 text-xs font-semibold text-slate-400 hover:text-white hover:bg-navy-800 transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-navy-950 font-semibold text-xs flex items-center space-x-2 shadow-md shadow-emerald-500/20 transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Approve to Vault</span>
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
