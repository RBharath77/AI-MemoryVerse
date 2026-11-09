"use client";

import { useEffect, useState } from "react";
import {
  FolderOpen,
  Tag,
  Hash,
  Vault,
  Search,
  Sparkles,
  ArrowRight,
  Plus,
  Loader2,
  Layers,
  ChevronRight,
} from "lucide-react";
import Link from "next/link";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

interface MemoryItem {
  id: string;
  content: string;
  category: string;
  importance: number;
  tags: string[];
  created_at: string;
}

interface CollectionTag {
  name: string;
  count: number;
  memories: MemoryItem[];
}

export default function CollectionsPage() {
  const [memories, setMemories] = useState<MemoryItem[]>([]);
  const [collections, setCollections] = useState<CollectionTag[]>([]);
  const [selectedTag, setSelectedTag] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true);
    const res = await api.get("/memories");
    if (res.success && res.data) {
      const allMems: MemoryItem[] = Array.isArray(res.data)
        ? res.data
        : res.data.items || [];
      setMemories(allMems);

      // Group by tag
      const tagMap: Record<string, MemoryItem[]> = {};
      allMems.forEach((m) => {
        const itemTags = m.tags && m.tags.length > 0 ? m.tags : [m.category || "general"];
        itemTags.forEach((t) => {
          const norm = t.toLowerCase().trim();
          if (!tagMap[norm]) tagMap[norm] = [];
          tagMap[norm].push(m);
        });
      });

      const collList: CollectionTag[] = Object.entries(tagMap)
        .map(([name, memList]) => ({
          name,
          count: memList.length,
          memories: memList,
        }))
        .sort((a, b) => b.count - a.count);

      setCollections(collList);
      if (collList.length > 0 && !selectedTag) {
        setSelectedTag(collList[0].name);
      }
    }
    setIsLoading(false);
  };

  const activeCollection = collections.find((c) => c.name === selectedTag);

  const filteredMemories =
    activeCollection?.memories.filter((m) =>
      !searchQuery ? true : m.content.toLowerCase().includes(searchQuery.toLowerCase())
    ) || [];

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <FolderOpen className="w-4 h-4" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Memory Collections
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Topic clusters, thematic collections, and categorized memory notebooks.
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

      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center space-y-3">
          <Loader2 className="w-8 h-8 text-cyan-400 animate-spin" />
          <p className="text-xs text-slate-400">Indexing collections and topic clusters...</p>
        </div>
      ) : collections.length === 0 ? (
        <div className="p-12 text-center rounded-2xl border border-navy-800 bg-navy-900/20 space-y-3">
          <Layers className="w-10 h-10 text-slate-500 mx-auto" />
          <h3 className="text-base font-semibold text-white">No collections found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto">
            Add tags to your memories in the vault to automatically generate collections.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
          {/* Left: Collections Sidebar List */}
          <div className="lg:col-span-4 space-y-3">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider block mb-2">
              Topic Clusters ({collections.length})
            </span>
            <div className="space-y-1.5 max-h-[600px] overflow-y-auto pr-1">
              {collections.map((c) => {
                const isSelected = selectedTag === c.name;
                return (
                  <button
                    key={c.name}
                    type="button"
                    onClick={() => setSelectedTag(c.name)}
                    className={`w-full p-3.5 rounded-xl border flex items-center justify-between text-left transition-all ${
                      isSelected
                        ? "bg-cyan-500/15 border-cyan-500/40 text-cyan-300 shadow-md shadow-cyan-500/10"
                        : "bg-navy-900/40 border-navy-800 text-slate-300 hover:bg-navy-800/60 hover:text-white"
                    }`}
                  >
                    <div className="flex items-center space-x-2.5 truncate">
                      <Hash
                        className={`w-4 h-4 shrink-0 ${
                          isSelected ? "text-cyan-400" : "text-slate-500"
                        }`}
                      />
                      <span className="text-xs font-semibold truncate capitalize">{c.name}</span>
                    </div>
                    <span
                      className={`text-[11px] px-2 py-0.5 rounded-full font-mono font-medium ${
                        isSelected
                          ? "bg-cyan-500/20 text-cyan-300"
                          : "bg-navy-950 text-slate-400 border border-navy-800"
                      }`}
                    >
                      {c.count}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: Items in Active Collection */}
          <div className="lg:col-span-8 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 p-4 rounded-xl bg-navy-900/40 border border-navy-800">
              <div className="flex items-center space-x-2">
                <Hash className="w-5 h-5 text-cyan-400" />
                <h3 className="font-bold text-white text-base capitalize">
                  {selectedTag} Collection
                </h3>
                <span className="text-xs text-slate-400 font-mono">
                  ({filteredMemories.length} memories)
                </span>
              </div>
              <div className="relative w-full sm:w-60">
                <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                <input
                  type="text"
                  placeholder="Filter this collection..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-navy-950 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <div className="space-y-3">
              {filteredMemories.length === 0 ? (
                <div className="p-8 text-center rounded-xl border border-navy-800 bg-navy-900/20 text-slate-400 text-xs">
                  No memories match this search query in #{selectedTag}.
                </div>
              ) : (
                filteredMemories.map((m) => (
                  <div
                    key={m.id}
                    className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 hover:border-cyan-500/30 transition-all space-y-2.5 shadow-sm"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span className="font-semibold uppercase tracking-wider text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                        {m.category}
                      </span>
                      <span className="font-mono">{formatDate(m.created_at)}</span>
                    </div>
                    <p className="text-sm text-slate-200 leading-relaxed font-normal">{m.content}</p>
                    {m.tags && m.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1.5 pt-1">
                        {m.tags.map((t) => (
                          <span
                            key={t}
                            className={`text-[10px] px-2 py-0.5 rounded font-mono ${
                              t.toLowerCase() === selectedTag?.toLowerCase()
                                ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-semibold"
                                : "bg-navy-950 text-slate-400 border border-navy-800"
                            }`}
                          >
                            #{t}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

