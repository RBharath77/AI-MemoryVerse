"use client";

import { useEffect, useState } from "react";
import {
  Key,
  Plus,
  Trash2,
  Copy,
  Check,
  ShieldAlert,
  Code2,
  ExternalLink,
  Lock,
  Globe,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Blocks,
  FileCode,
  Terminal,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface APIToken {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  expires_at?: string | null;
  last_used_at?: string | null;
  created_at: string;
}

interface NewTokenResult {
  id: string;
  name: string;
  token_prefix: string;
  scopes: string[];
  expires_at?: string | null;
  plaintext_token: string;
}

const AVAILABLE_SCOPES = [
  { id: "memories:read", label: "Read Memories", desc: "Access memory vault and search facts" },
  { id: "memories:write", label: "Write Memories", desc: "Create, extract, and update memories" },
  { id: "search", label: "Hybrid Search & RAG", desc: "Execute semantic and hybrid RAG queries" },
  { id: "graph:read", label: "Knowledge Graph", desc: "Access entities and relationship graphs" },
  { id: "documents:read", label: "Read Documents", desc: "Access document library and chunks" },
];

export default function IntegrationsPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [tokens, setTokens] = useState<APIToken[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"keys" | "docs">("keys");

  // Modal states
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [newKeyName, setNewKeyName] = useState("");
  const [selectedScopes, setSelectedScopes] = useState<string[]>([
    "memories:read",
    "memories:write",
    "search",
  ]);
  const [expiresInDays, setExpiresInDays] = useState<number>(90);

  // Newly created token secret display modal
  const [createdTokenResult, setCreatedTokenResult] = useState<NewTokenResult | null>(null);
  const [hasCopied, setHasCopied] = useState(false);

  const fetchTokens = async () => {
    try {
      const res = await api.get<any>("/tokens");
      if (res.success && res.data) {
        const list = Array.isArray(res.data) ? res.data : res.data.items || [];
        setTokens(list);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      setIsLoading(true);
      fetchTokens();
    }
  }, [activeWorkspaceId]);

  const handleCreateToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || selectedScopes.length === 0) return;

    setIsSubmitting(true);
    try {
      const res = await api.post<NewTokenResult>("/tokens", {
        name: newKeyName.trim(),
        scopes: selectedScopes,
        expires_in_days: expiresInDays > 0 ? expiresInDays : undefined,
      });

      if (res.success && res.data) {
        setCreatedTokenResult(res.data);
        setIsCreateOpen(false);
        setNewKeyName("");
        await fetchTokens();
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleRevokeToken = async (tokenId: string) => {
    if (!confirm("Are you sure you want to revoke this API key? Any integration using this key will immediately stop working.")) {
      return;
    }

    const res = await api.delete(`/tokens/${tokenId}`);
    if (res.success) {
      setTokens((prev) => prev.filter((t) => t.id !== tokenId));
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setHasCopied(true);
    setTimeout(() => setHasCopied(false), 2500);
  };

  const toggleScope = (scopeId: string) => {
    setSelectedScopes((prev) =>
      prev.includes(scopeId) ? prev.filter((s) => s !== scopeId) : [...prev, scopeId]
    );
  };

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Blocks className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Integrations & Developer API Keys
              </h1>
              <p className="text-sm text-slate-400">
                Secure programmatic access to AI-MemoryVerse via SHA-256 hashed API tokens and REST webhooks.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-cyan-500/20 transition self-start sm:self-auto"
        >
          <Plus className="w-4 h-4" />
          <span>Create New API Key</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-navy-800 space-x-8 text-sm font-medium">
        <button
          onClick={() => setActiveTab("keys")}
          className={`pb-3 flex items-center space-x-2 border-b-2 transition ${
            activeTab === "keys"
              ? "border-cyan-400 text-cyan-400 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Key className="w-4 h-4" />
          <span>Active API Keys ({tokens.length})</span>
        </button>

        <button
          onClick={() => setActiveTab("docs")}
          className={`pb-3 flex items-center space-x-2 border-b-2 transition ${
            activeTab === "docs"
              ? "border-cyan-400 text-cyan-400 font-semibold"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>REST API Quickstart & Examples</span>
        </button>
      </div>

      {/* Tab 1: API Keys Management */}
      {activeTab === "keys" && (
        <div className="space-y-6">
          {isLoading ? (
            <div className="p-12 text-center text-slate-500 bg-navy-900/50 border border-navy-800 rounded-xl">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-cyan-400 mb-2" />
              <p className="text-sm">Loading API tokens...</p>
            </div>
          ) : tokens.length === 0 ? (
            <div className="p-12 text-center bg-navy-900/50 border border-dashed border-navy-800 rounded-xl">
              <Key className="w-10 h-10 text-slate-600 mx-auto mb-3" />
              <h3 className="text-base font-medium text-white">No API Keys Generated</h3>
              <p className="text-sm text-slate-400 mt-1 max-w-md mx-auto">
                Generate an API key to connect external applications, Raycast extensions, Obsidian plugins, or custom scripts to your MemoryVerse workspace.
              </p>
              <button
                onClick={() => setIsCreateOpen(true)}
                className="mt-5 px-4 py-2 bg-navy-800 hover:bg-navy-700 text-cyan-400 text-xs font-semibold rounded-lg border border-cyan-500/30 transition"
              >
                + Generate First API Key
              </button>
            </div>
          ) : (
            <div className="bg-navy-900/70 border border-navy-800 rounded-xl overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-navy-950/80 border-b border-navy-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="py-3 px-4">Key Name</th>
                      <th className="py-3 px-4">Token Prefix</th>
                      <th className="py-3 px-4">Granted Scopes</th>
                      <th className="py-3 px-4">Created / Expires</th>
                      <th className="py-3 px-4">Last Used</th>
                      <th className="py-3 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-navy-800 text-xs">
                    {tokens.map((token) => (
                      <tr key={token.id} className="hover:bg-navy-850/50 transition">
                        <td className="py-3.5 px-4 font-semibold text-white">
                          <div className="flex items-center space-x-2">
                            <Key className="w-4 h-4 text-cyan-400 shrink-0" />
                            <span>{token.name}</span>
                          </div>
                        </td>

                        <td className="py-3.5 px-4 font-mono text-cyan-300">
                          {token.token_prefix}••••••••
                        </td>

                        <td className="py-3.5 px-4">
                          <div className="flex flex-wrap gap-1">
                            {token.scopes.map((scope) => (
                              <span
                                key={scope}
                                className="px-2 py-0.5 rounded bg-navy-950 border border-navy-700 text-[11px] text-slate-300 font-mono"
                              >
                                {scope}
                              </span>
                            ))}
                          </div>
                        </td>

                        <td className="py-3.5 px-4 text-slate-400">
                          <div>{formatDate(token.created_at)}</div>
                          <div className="text-[11px] text-slate-500">
                            {token.expires_at ? `Exp: ${formatDate(token.expires_at)}` : "No expiration"}
                          </div>
                        </td>

                        <td className="py-3.5 px-4 text-slate-400">
                          {token.last_used_at ? formatDate(token.last_used_at) : "Never"}
                        </td>

                        <td className="py-3.5 px-4 text-right">
                          <button
                            onClick={() => handleRevokeToken(token.id)}
                            className="p-1.5 rounded hover:bg-rose-950/40 text-slate-500 hover:text-rose-400 transition"
                            title="Revoke Token"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Security Information Box */}
          <div className="p-4 bg-navy-950/60 border border-navy-800 rounded-xl flex items-start space-x-3 text-xs text-slate-400">
            <Lock className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <span className="font-semibold text-slate-200">
                Cryptographic Token Protection
              </span>
              <p className="leading-relaxed">
                Tokens are hashed with SHA-256 before storage in PostgreSQL. Only the masked prefix is retained for identification. Never share or commit your secret API keys to version control.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tab 2: REST API Documentation & Quickstart */}
      {activeTab === "docs" && (
        <div className="space-y-6">
          <div className="bg-navy-900/70 border border-navy-800 rounded-xl p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-white tracking-tight">
                Authentication & Headers
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Pass your API key in the standard <code className="text-cyan-300 font-mono">Authorization: Bearer</code> header along with your workspace ID:
              </p>
            </div>

            <pre className="p-4 rounded-xl bg-black/60 border border-navy-800 font-mono text-xs text-cyan-300 overflow-x-auto">
{`# Required Request Headers
Authorization: Bearer mv_live_YOUR_API_KEY
X-Workspace-ID: ${activeWorkspaceId || "YOUR_WORKSPACE_ID"}
Content-Type: application/json`}
            </pre>

            <div className="space-y-4 pt-4 border-t border-navy-800">
              <h3 className="text-sm font-bold text-white">
                1. Perform Hybrid RAG Search
              </h3>
              <p className="text-xs text-slate-400">
                Query verified facts and ingested documents using hybrid BM25 + pgvector similarity:
              </p>

              <pre className="p-4 rounded-xl bg-black/60 border border-navy-800 font-mono text-xs text-emerald-300 overflow-x-auto">
{`curl -X POST "http://localhost:8000/api/v1/search/hybrid" \\
  -H "Authorization: Bearer mv_live_YOUR_API_KEY" \\
  -H "X-Workspace-ID: ${activeWorkspaceId || "YOUR_WORKSPACE_ID"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "query": "What are our project deadlines and cloud architecture?",
    "top_k": 5,
    "include_memories": true,
    "include_documents": true
  }'`}
              </pre>
            </div>

            <div className="space-y-4 pt-4 border-t border-navy-800">
              <h3 className="text-sm font-bold text-white">
                2. Ingest Memory Fact Programmatically
              </h3>
              <p className="text-xs text-slate-400">
                Push a structured memory directly into the workspace vault:
              </p>

              <pre className="p-4 rounded-xl bg-black/60 border border-navy-800 font-mono text-xs text-emerald-300 overflow-x-auto">
{`curl -X POST "http://localhost:8000/api/v1/memories" \\
  -H "Authorization: Bearer mv_live_YOUR_API_KEY" \\
  -H "X-Workspace-ID: ${activeWorkspaceId || "YOUR_WORKSPACE_ID"}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "content": "Production deployment scheduled for Monday at 10:00 UTC",
    "category": "project",
    "importance_score": 8,
    "confidence_score": 0.95,
    "source_type": "api_integration"
  }'`}
              </pre>
            </div>

            <div className="space-y-4 pt-4 border-t border-navy-800">
              <h3 className="text-sm font-bold text-white">
                3. Query Knowledge Graph Triples
              </h3>
              <p className="text-xs text-slate-400">
                Retrieve entities and connected relationships for visualization:
              </p>

              <pre className="p-4 rounded-xl bg-black/60 border border-navy-800 font-mono text-xs text-emerald-300 overflow-x-auto">
{`curl -X GET "http://localhost:8000/api/v1/graph/visualize?limit=50" \\
  -H "Authorization: Bearer mv_live_YOUR_API_KEY" \\
  -H "X-Workspace-ID: ${activeWorkspaceId || "YOUR_WORKSPACE_ID"}"`}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Create API Key */}
      {isCreateOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <div className="flex items-center space-x-2">
                <Key className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">Create New API Key</h3>
              </div>
              <button
                onClick={() => setIsCreateOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateToken} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Key Description / Name
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Raycast Integration, CLI Sync Script, Obsidian Sync"
                  value={newKeyName}
                  onChange={(e) => setNewKeyName(e.target.value)}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-2">
                  Select Permission Scopes
                </label>
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {AVAILABLE_SCOPES.map((scope) => {
                    const isChecked = selectedScopes.includes(scope.id);
                    return (
                      <div
                        key={scope.id}
                        onClick={() => toggleScope(scope.id)}
                        className={`p-2.5 rounded-lg border cursor-pointer select-none transition flex items-center justify-between ${
                          isChecked
                            ? "bg-cyan-950/30 border-cyan-500/50"
                            : "bg-navy-950 border-navy-800 hover:border-navy-700"
                        }`}
                      >
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="text-xs font-bold text-white">
                              {scope.label}
                            </span>
                            <span className="font-mono text-[10px] text-cyan-400">
                              {scope.id}
                            </span>
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            {scope.desc}
                          </p>
                        </div>
                        <div
                          className={`w-4 h-4 rounded border flex items-center justify-center shrink-0 ${
                            isChecked
                              ? "bg-cyan-500 border-cyan-500 text-white"
                              : "border-slate-600"
                          }`}
                        >
                          {isChecked && <Check className="w-3 h-3 stroke-[3]" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Key Expiration
                </label>
                <select
                  value={expiresInDays}
                  onChange={(e) => setExpiresInDays(parseInt(e.target.value))}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value={30}>30 Days</option>
                  <option value={60}>60 Days</option>
                  <option value={90}>90 Days (Recommended)</option>
                  <option value={365}>1 Year</option>
                  <option value={0}>Never Expire</option>
                </select>
              </div>

              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={() => setIsCreateOpen(false)}
                  className="px-4 py-2 bg-navy-800 hover:bg-navy-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting || selectedScopes.length === 0}
                  className="flex items-center space-x-2 px-5 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-bold rounded-lg shadow-md transition disabled:opacity-50"
                >
                  {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Generate Key</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Display Plaintext Token Once */}
      {createdTokenResult && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-md p-4">
          <div className="bg-navy-900 border border-emerald-500/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center space-x-2 text-emerald-400">
              <CheckCircle2 className="w-6 h-6" />
              <h3 className="text-lg font-bold text-white">API Key Created Successfully</h3>
            </div>

            <div className="p-3 bg-rose-950/40 border border-rose-500/40 rounded-xl flex items-start space-x-2.5 text-xs text-rose-300">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <span>
                Please copy your secret API key now. For your security, this key will never be shown again once you close this window.
              </span>
            </div>

            <div>
              <span className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Secret API Key ({createdTokenResult.name})
              </span>
              <div className="relative">
                <input
                  type="text"
                  readOnly
                  value={createdTokenResult.plaintext_token}
                  className="w-full pl-3 pr-24 py-2.5 bg-black/70 border border-navy-700 rounded-lg font-mono text-xs text-cyan-300 select-all focus:outline-none"
                />
                <button
                  type="button"
                  onClick={() => copyToClipboard(createdTokenResult.plaintext_token)}
                  className="absolute right-1.5 top-1.5 bottom-1.5 px-3 bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-bold rounded flex items-center space-x-1.5 transition"
                >
                  {hasCopied ? (
                    <>
                      <Check className="w-3.5 h-3.5" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <button
                type="button"
                onClick={() => setCreatedTokenResult(null)}
                className="px-5 py-2 bg-navy-800 hover:bg-navy-700 text-white text-xs font-bold rounded-lg transition"
              >
                I Have Saved My Key
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

