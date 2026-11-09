"use client";

import { useEffect, useState } from "react";
import {
  Vault,
  Plus,
  Search,
  Filter,
  Pin,
  Trash2,
  Tag,
  Calendar,
  Sparkles,
  BookOpen,
  Briefcase,
  UserCheck,
  Loader2,
  AlertCircle,
  X,
  Check,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface Memory {
  id: string;
  content: string;
  category: "semantic" | "episodic" | "project" | "preference";
  status: string;
  importance: number;
  confidence: number;
  is_pinned: boolean;
  tags: string[];
  created_at: string;
}

const categoryIcons = {
  semantic: BookOpen,
  episodic: Calendar,
  project: Briefcase,
  preference: UserCheck,
};

const categoryColors = {
  semantic: "text-blue-400 bg-blue-950/60 border-blue-500/30",
  episodic: "text-violet-400 bg-violet-950/60 border-violet-500/30",
  project: "text-cyan-400 bg-cyan-950/60 border-cyan-500/30",
  preference: "text-emerald-400 bg-emerald-950/60 border-emerald-500/30",
};

export default function MemoryVaultPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [memories, setMemories] = useState<Memory[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Form states for creating a new memory
  const [newContent, setNewContent] = useState("");
  const [newCategory, setNewCategory] = useState<"semantic" | "episodic" | "project" | "preference">("semantic");
  const [newImportance, setNewImportance] = useState(5);
  const [newTagInput, setNewTagInput] = useState("");
  const [newTags, setNewTags] = useState<string[]>([]);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fetchMemories = async () => {
    setIsLoading(true);
    let url = "/memories?";
    if (selectedCategory !== "all") {
      url += `category=${selectedCategory}&`;
    }
    if (searchQuery.trim()) {
      url += `search=${encodeURIComponent(searchQuery.trim())}&`;
    }

    const res = await api.get(url);
    if (res.success && res.data) {
      setMemories(res.data.items || []);
      setTotal(res.data.total || 0);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      fetchMemories();
    }
  }, [activeWorkspaceId, selectedCategory, searchQuery]);

  const handleAddTag = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      const tag = newTagInput.trim().toLowerCase();
      if (tag && !newTags.includes(tag)) {
        setNewTags([...newTags, tag]);
        setNewTagInput("");
      }
    }
  };

  const removeTag = (tagToRemove: string) => {
    setNewTags(newTags.filter((t) => t !== tagToRemove));
  };

  const handleCreateMemory = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newContent.trim()) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    const res = await api.post("/memories", {
      content: newContent.trim(),
      category: newCategory,
      importance: newImportance,
      tags: newTags,
    });

    if (res.success && res.data) {
      setMemories([res.data, ...memories]);
      setTotal(total + 1);
      setIsModalOpen(false);
      setNewContent("");
      setNewTags([]);
      setNewImportance(5);
    } else {
      setErrorMessage(res.error?.message || "Failed to save memory.");
    }
    setIsSubmitting(false);
  };

  const handleDeleteMemory = async (id: string) => {
    const res = await api.delete(`/memories/${id}`);
    if (res.success) {
      setMemories(memories.filter((m) => m.id !== id));
      setTotal(Math.max(0, total - 1));
    }
  };

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <Vault className="w-6 h-6 text-[#014BAA] dark:text-cyan-400" />
            <h1 className="text-2xl font-extrabold text-[#282B4A] dark:text-white tracking-tight">
              Memory Vault
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">
            Persistent, human-in-the-loop memories verified for source-grounded retrieval.
          </p>
        </div>

        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 rounded-xl bg-[#014BAA] hover:bg-[#014BAA]/90 text-[#F8F3F0] font-bold text-xs flex items-center justify-center space-x-2 shadow-md shadow-[#014BAA]/25 transition-all"
        >
          <Plus className="w-4 h-4 text-[#F8F3F0]" />
          <span>Add Memory</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
        {/* Category Pills */}
        <div className="flex items-center space-x-2 overflow-x-auto pb-2 sm:pb-0">
          {["all", "semantic", "episodic", "project", "preference"].map((cat) => (
            <button
              key={cat}
              onClick={() => setSelectedCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors shrink-0 ${
                selectedCategory === cat
                  ? "bg-[#014BAA] text-[#F8F3F0] shadow-md shadow-[#014BAA]/20"
                  : "bg-white dark:bg-navy-900/60 border border-[#EEEBDA] dark:border-navy-800 text-slate-600 dark:text-slate-400 hover:text-[#014BAA] dark:hover:text-white"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>

        {/* Search Input */}
        <div className="relative w-full sm:w-72">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search memories or tags..."
            className="w-full pl-9 pr-4 py-2 bg-white dark:bg-navy-900/80 border border-[#EEEBDA] dark:border-navy-800 rounded-lg text-xs text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#014BAA] transition-colors"
          />
        </div>
      </div>

      {/* Memory Cards Grid */}
      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-[#014BAA] dark:text-cyan-400" />
          <p className="text-xs">Loading memory vault...</p>
        </div>
      ) : memories.length === 0 ? (
        <div className="py-16 px-4 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/20 text-center shadow-sm">
          <div className="w-12 h-12 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/20 flex items-center justify-center mx-auto mb-4 text-[#014BAA] dark:text-cyan-400">
            <Vault className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-[#282B4A] dark:text-white mb-1">No memories found</h3>
          <p className="text-xs text-slate-500 dark:text-slate-400 max-w-sm mx-auto mb-6">
            {searchQuery
              ? `No memories matched your search for "${searchQuery}".`
              : "Capture your first personal rule, project architecture context, or preference."}
          </p>
          <button
            onClick={() => setIsModalOpen(true)}
            className="px-4 py-2 rounded-xl bg-[#014BAA] hover:bg-[#014BAA]/90 text-[#F8F3F0] font-bold text-xs shadow-md shadow-[#014BAA]/25 transition-all"
          >
            Create Memory Now
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {memories.map((m) => {
            const Icon = categoryIcons[m.category] || BookOpen;
            const badgeColor = categoryColors[m.category] || categoryColors.semantic;
            return (
              <div
                key={m.id}
                className="p-5 rounded-2xl border border-[#EEEBDA] dark:border-navy-800 bg-white dark:bg-navy-900/40 hover:border-[#014BAA]/40 transition-all flex flex-col justify-between group shadow-sm"
              >
                <div>
                  {/* Card Header */}
                  <div className="flex items-center justify-between mb-3">
                    <span
                      className={`inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-md border text-[10px] font-bold uppercase tracking-wider ${badgeColor}`}
                    >
                      <Icon className="w-3 h-3" />
                      <span>{m.category}</span>
                    </span>

                    <div className="flex items-center space-x-2">
                      {m.is_pinned && (
                        <span title="Pinned memory" className="text-[#014BAA] dark:text-cyan-400">
                          <Pin className="w-3.5 h-3.5" />
                        </span>
                      )}
                      <span className="text-[10px] px-2 py-0.5 rounded bg-[#F8F3F0] dark:bg-navy-950 text-slate-600 dark:text-slate-400 border border-[#EEEBDA] dark:border-navy-800 font-mono">
                        Imp: {m.importance}/10
                      </span>
                    </div>
                  </div>

                  {/* Content */}
                  <p className="text-xs sm:text-sm text-[#282B4A] dark:text-slate-200 leading-relaxed line-clamp-4">
                    {m.content}
                  </p>
                </div>

                {/* Card Footer */}
                <div className="mt-5 pt-3 border-t border-[#EEEBDA] dark:border-navy-800/80 flex items-center justify-between text-[11px] text-slate-500">
                  <div className="flex items-center space-x-2">
                    <Calendar className="w-3 h-3" />
                    <span>{formatDate(m.created_at)}</span>
                  </div>

                  <button
                    onClick={() => handleDeleteMemory(m.id)}
                    className="p-1 rounded text-slate-400 hover:text-red-500 hover:bg-slate-100 dark:hover:bg-navy-950 transition-colors opacity-0 group-hover:opacity-100"
                    title="Delete memory"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Memory Modal Dialog */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl w-full max-w-lg p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <h3 className="text-base font-bold text-white flex items-center space-x-2">
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>Add Persistent Memory</span>
              </h3>
              <button
                onClick={() => setIsModalOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {errorMessage && (
              <div className="p-3 rounded-lg border border-red-500/30 bg-red-950/30 text-red-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{errorMessage}</span>
              </div>
            )}

            <form onSubmit={handleCreateMemory} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Memory Statement / Fact
                </label>
                <textarea
                  required
                  rows={4}
                  value={newContent}
                  onChange={(e) => setNewContent(e.target.value)}
                  placeholder="e.g. Always generate async SQLAlchemy 2.0 queries with PostgreSQL pgvector embeddings."
                  className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Category
                  </label>
                  <select
                    value={newCategory}
                    onChange={(e: any) => setNewCategory(e.target.value)}
                    className="w-full p-2 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
                  >
                    <option value="semantic">Semantic (Fact/Knowledge)</option>
                    <option value="episodic">Episodic (Event/Meeting)</option>
                    <option value="project">Project (Context/Decision)</option>
                    <option value="preference">Preference (Habit/Style)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                    Importance (1 - 10): {newImportance}
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={newImportance}
                    onChange={(e) => setNewImportance(parseInt(e.target.value))}
                    className="w-full accent-cyan-400 mt-2"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                  Tags (Press Enter to add)
                </label>
                <div className="flex flex-wrap items-center gap-1.5 p-2 bg-navy-950 border border-navy-700 rounded-lg">
                  {newTags.map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center space-x-1 px-2 py-0.5 rounded bg-cyan-950 border border-cyan-500/30 text-[10px] text-cyan-300 font-mono"
                    >
                      <span>#{tag}</span>
                      <button
                        type="button"
                        onClick={() => removeTag(tag)}
                        className="hover:text-red-400"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={newTagInput}
                    onChange={(e) => setNewTagInput(e.target.value)}
                    onKeyDown={handleAddTag}
                    placeholder="tag, enter..."
                    className="bg-transparent border-none text-xs text-white placeholder-slate-500 focus:outline-none flex-1 min-w-[80px]"
                  />
                </div>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-4 border-t border-navy-800">
                <button
                  type="button"
                  onClick={() => setIsModalOpen(false)}
                  className="px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-700 text-slate-300 text-xs font-medium transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs flex items-center space-x-2 transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving...</span>
                    </>
                  ) : (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Save Memory</span>
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
