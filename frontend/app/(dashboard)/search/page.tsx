"use client";

import { useState } from "react";
import {
  Search,
  Sparkles,
  Vault,
  FileText,
  SlidersHorizontal,
  ArrowRight,
  Loader2,
  Copy,
  Check,
  GitFork,
  CheckCircle2,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";

interface SearchResultItem {
  source_type: "memory" | "document";
  id: string;
  title: string;
  content: string;
  score: number;
  category?: string | null;
  section_title?: string | null;
  metadata?: Record<string, any>;
}

export default function GlobalSearchPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResultItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const [includeDocs, setIncludeDocs] = useState(true);
  const [includeMems, setIncludeMems] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const handleSearch = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setHasSearched(true);

    const payload = {
      query: query.trim(),
      top_k: 15,
      filter_category: filterCategory === "all" ? null : filterCategory,
      include_documents: includeDocs,
      include_memories: includeMems,
    };

    const res = await api.post("/search/hybrid", payload);
    if (res.success && res.data?.results) {
      setResults(res.data.results);
    } else {
      setResults([]);
    }
    setIsLoading(false);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="p-6 sm:p-8 max-w-5xl mx-auto space-y-8">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto space-y-3 pt-4">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center text-white mx-auto shadow-lg shadow-cyan-500/20">
          <Search className="w-5 h-5" />
        </div>
        <h1 className="text-3xl font-extrabold text-white tracking-tight">
          Unified Hybrid Search
        </h1>
        <p className="text-sm text-slate-400">
          Reciprocal Rank Fusion combining BM25 keyword matching and dense vector embeddings
          across all memories and uploaded documents.
        </p>
      </div>

      {/* Search Input Form */}
      <form onSubmit={handleSearch} className="space-y-4">
        <div className="relative">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search anything in your vault... (e.g. system architecture, team preferences, meeting notes)"
            className="w-full pl-12 pr-28 py-3.5 rounded-2xl bg-navy-900/60 border border-navy-700 hover:border-cyan-500/50 focus:border-cyan-500 text-sm text-white placeholder-slate-500 focus:outline-none transition-all shadow-xl shadow-black/30"
          />
          <Search className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" />
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="absolute right-2 top-1/2 -translate-y-1/2 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-40"
          >
            {isLoading ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <>
                <Sparkles className="w-3.5 h-3.5" />
                <span>Search</span>
              </>
            )}
          </button>
        </div>

        {/* Filters and Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 p-3 rounded-xl bg-navy-900/30 border border-navy-800 text-xs text-slate-300">
          <div className="flex items-center space-x-2">
            <span className="text-slate-500 font-medium">Categories:</span>
            {["all", "semantic", "episodic", "project", "preference"].map((cat) => (
              <button
                type="button"
                key={cat}
                onClick={() => setFilterCategory(cat)}
                className={`px-2.5 py-1 rounded-lg capitalize transition-colors ${
                  filterCategory === cat
                    ? "bg-cyan-500/20 text-cyan-300 font-semibold border border-cyan-500/30"
                    : "text-slate-400 hover:text-white"
                }`}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="flex items-center space-x-4">
            <label className="flex items-center space-x-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={includeMems}
                onChange={(e) => setIncludeMems(e.target.checked)}
                className="rounded border-navy-700 bg-navy-950 text-cyan-500 focus:ring-0"
              />
              <span className="text-slate-300 text-xs">Memories</span>
            </label>
            <label className="flex items-center space-x-1.5 cursor-pointer">
              <input
                type="checkbox"
                checked={includeDocs}
                onChange={(e) => setIncludeDocs(e.target.checked)}
                className="rounded border-navy-700 bg-navy-950 text-cyan-500 focus:ring-0"
              />
              <span className="text-slate-300 text-xs">Documents</span>
            </label>
          </div>
        </div>
      </form>

      {/* Results Section */}
      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <p className="text-xs text-slate-400">Executing reciprocal rank fusion search...</p>
        </div>
      ) : hasSearched && results.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-navy-800 bg-navy-900/20 space-y-3">
          <Search className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-base font-semibold text-white">No matching results found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Try adjusting your query terms, selecting different categories, or adding new memories.
          </p>
        </div>
      ) : results.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between text-xs text-slate-400 px-1">
            <span>Found {results.length} relevant matches for &ldquo;{query}&rdquo;</span>
            <span className="font-mono text-[11px] text-cyan-400">Hybrid RRF Scored</span>
          </div>

          <div className="space-y-3">
            {results.map((r, i) => {
              const isMemory = r.source_type === "memory";
              return (
                <div
                  key={`${r.id}-${i}`}
                  className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 hover:border-cyan-500/40 transition-all space-y-3 shadow-sm"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center space-x-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border flex items-center space-x-1 ${
                          isMemory
                            ? "bg-cyan-500/10 text-cyan-400 border-cyan-500/20"
                            : "bg-blue-500/10 text-blue-400 border-blue-500/20"
                        }`}
                      >
                        {isMemory ? <Vault className="w-3 h-3 mr-1" /> : <FileText className="w-3 h-3 mr-1" />}
                        {r.source_type}
                      </span>
                      {r.category && (
                        <span className="text-[10px] text-slate-400 font-mono bg-navy-950 px-2 py-0.5 rounded border border-navy-800 uppercase">
                          {r.category}
                        </span>
                      )}
                      {r.section_title && (
                        <span className="text-[10px] text-slate-400 truncate max-w-xs">
                          {r.section_title}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-3 text-xs">
                      <div className="flex items-center space-x-1 text-slate-400 font-mono text-[11px]">
                        <span>Score:</span>
                        <span className="text-cyan-400 font-bold">{r.score.toFixed(3)}</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleCopy(r.id, r.content)}
                        className="p-1 rounded text-slate-400 hover:text-white hover:bg-navy-800 transition-colors"
                        title="Copy content"
                      >
                        {copiedId === r.id ? (
                          <Check className="w-3.5 h-3.5 text-emerald-400" />
                        ) : (
                          <Copy className="w-3.5 h-3.5" />
                        )}
                      </button>
                    </div>
                  </div>

                  <p className="text-sm text-slate-200 leading-relaxed font-normal whitespace-pre-line">
                    {r.content}
                  </p>

                  <div className="flex items-center justify-between pt-2 border-t border-navy-800/60 text-xs">
                    <span className="text-slate-500 text-[11px] font-mono truncate">
                      ID: {r.id}
                    </span>
                    <Link
                      href={isMemory ? "/memories" : "/documents"}
                      className="text-cyan-400 hover:text-cyan-300 font-medium flex items-center space-x-1 text-[11px]"
                    >
                      <span>{isMemory ? "Open Vault" : "View Document"}</span>
                      <ArrowRight className="w-3 h-3" />
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

