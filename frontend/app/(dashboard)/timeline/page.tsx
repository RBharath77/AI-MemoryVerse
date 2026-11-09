"use client";

import { useEffect, useState } from "react";
import {
  Clock,
  Calendar,
  Filter,
  Search,
  Sparkles,
  Tag,
  Star,
  Pin,
  Plus,
  Loader2,
  ChevronRight,
  BookOpen,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface MemoryItem {
  id: string;
  content: string;
  category: string;
  importance: number;
  confidence: number;
  is_pinned: boolean;
  tags: string[];
  created_at: string;
  source_type: string;
}

export default function MemoryTimelinePage() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchMemories();
  }, []);

  const fetchMemories = async () => {
    setIsLoading(true);
    const res = await api.get("/memories");
    if (res.success && res.data) {
      const items: MemoryItem[] = Array.isArray(res.data)
        ? res.data
        : res.data.items || [];
      // Sort chronologically descending
      const sorted = [...items].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
      setMemories(sorted);
    }
    setIsLoading(false);
  };

  const filtered = memories.filter((m) => {
    const matchesCat = filterCategory === "all" || m.category === filterCategory;
    const matchesQuery =
      !searchQuery ||
      m.content.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.tags?.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()));
    return matchesCat && matchesQuery;
  });

  const getCategoryColor = (cat: string) => {
    switch (cat.toLowerCase()) {
      case "episodic":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "project":
        return "bg-indigo-500/10 text-indigo-400 border-indigo-500/30";
      case "preference":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      default:
        return "bg-cyan-500/10 text-cyan-400 border-cyan-500/30";
    }
  };

  return (
    <div className="p-6 sm:p-8 max-w-5xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Clock className="w-4 h-4" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Memory Timeline
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Chronological evolution of your personal memories, events, preferences, and knowledge.
          </p>
        </div>

        <Link
          href="/memories"
          className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs transition-colors flex items-center space-x-2 w-fit shadow-lg shadow-cyan-500/20"
        >
          <Plus className="w-4 h-4" />
          <span>New Memory</span>
        </Link>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 p-4 rounded-xl bg-navy-900/40 border border-navy-800">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            placeholder="Search timeline..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-lg bg-navy-950 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center space-x-1.5 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {["all", "semantic", "episodic", "project", "preference"].map((cat) => (
            <button
              key={cat}
              onClick={() => setFilterCategory(cat)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-colors whitespace-nowrap ${
                filterCategory === cat
                  ? "bg-cyan-500 text-navy-950 font-semibold"
                  : "bg-navy-950 text-slate-400 hover:text-white border border-navy-800"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Timeline Feed */}
      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <p className="text-xs text-slate-400">Loading chronological timeline...</p>
        </div>
      ) : filtered.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-navy-800 bg-navy-900/20 space-y-3">
          <Clock className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-base font-semibold text-white">No timeline events found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            {searchQuery
              ? `No memories matched "${searchQuery}". Try adjusting your filters.`
              : "Start recording memories or chatting with your AI to populate your timeline."}
          </p>
        </div>
      ) : (
        <div className="relative pl-6 sm:pl-8 border-l-2 border-navy-800 space-y-8 my-6">
          {filtered.map((mem) => (
            <div key={mem.id} className="relative group">
              {/* Timeline Dot Node */}
              <div className="absolute -left-[31px] sm:-left-[39px] top-1.5 w-4 h-4 rounded-full bg-navy-950 border-2 border-cyan-400 flex items-center justify-center group-hover:scale-125 transition-transform shadow-md shadow-cyan-400/30">
                <div className="w-1.5 h-1.5 rounded-full bg-cyan-400" />
              </div>

              {/* Memory Card */}
              <div className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 hover:border-cyan-500/40 transition-all space-y-3 shadow-lg shadow-black/20">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span
                      className={`text-[11px] font-semibold uppercase px-2.5 py-0.5 rounded-full border ${getCategoryColor(
                        mem.category
                      )}`}
                    >
                      {mem.category}
                    </span>
                    {mem.is_pinned && (
                      <span className="flex items-center space-x-1 text-[11px] text-amber-400 font-medium">
                        <Pin className="w-3 h-3" />
                        <span>Pinned</span>
                      </span>
                    )}
                  </div>
                  <div className="flex items-center space-x-3 text-xs text-slate-400 font-mono">
                    <span className="flex items-center space-x-1">
                      <Star className="w-3.5 h-3.5 text-amber-400 fill-amber-400/20" />
                      <span>{mem.importance}/10</span>
                    </span>
                    <span>{formatDate(mem.created_at)}</span>
                  </div>
                </div>

                <p className="text-sm text-slate-200 leading-relaxed font-normal">
                  {mem.content}
                </p>

                {mem.tags && mem.tags.length > 0 && (
                  <div className="flex flex-wrap items-center gap-1.5 pt-2 border-t border-navy-800/60">
                    <Tag className="w-3 h-3 text-slate-500 mr-1" />
                    {mem.tags.map((tag) => (
                      <span
                        key={tag}
                        className="text-[10px] bg-navy-950 text-slate-400 px-2 py-0.5 rounded border border-navy-800 font-mono"
                      >
                        #{tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

