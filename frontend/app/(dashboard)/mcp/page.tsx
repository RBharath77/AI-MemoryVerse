"use client";

import { useEffect, useState } from "react";
import {
  Cpu,
  Check,
  Copy,
  Terminal,
  Play,
  Loader2,
  Sparkles,
  Search,
  Plus,
  GitFork,
  FileText,
  Activity,
  Inbox,
  Code2,
  ShieldCheck,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";

interface ToolDef {
  name: string;
  description: string;
  inputSchema: {
    type: string;
    properties: Record<string, any>;
    required?: string[];
  };
}

export default function MCPHubPage() {
  const [activeTab, setActiveTab] = useState<"claude" | "cursor" | "http">("claude");
  const [copied, setCopied] = useState(false);
  const [tools, setTools] = useState<ToolDef[]>([]);
  const [selectedTool, setSelectedTool] = useState("memoryverse_get_stats");
  const [toolInputs, setToolInputs] = useState<Record<string, any>>({
    query: "AI architecture memories",
    content: "Testing MCP memory creation directly from browser sandbox.",
    category: "project",
    importance: 8,
    limit: 5,
  });
  const [isRunning, setIsRunning] = useState(false);
  const [toolOutput, setToolOutput] = useState<string | null>(null);
  const [rawRpcResponse, setRawRpcResponse] = useState<any>(null);
  const [configData, setConfigData] = useState<any>(null);

  useEffect(() => {
    // Fetch tool catalog and client configs
    api.get("/mcp/tools").then((res) => {
      if (res.data?.tools) {
        setTools(res.data.tools);
      }
    });

    api.get("/mcp/config").then((res) => {
      if (res.data) {
        setConfigData(res.data);
      }
    });
  }, []);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const executeSandboxTool = async () => {
    setIsRunning(true);
    setToolOutput(null);
    setRawRpcResponse(null);

    let args: Record<string, any> = {};
    if (selectedTool === "memoryverse_search") {
      args = { query: toolInputs.query || "general", limit: Number(toolInputs.limit) || 5 };
    } else if (selectedTool === "memoryverse_add_memory") {
      args = {
        content: toolInputs.content || "Important external brain note.",
        category: toolInputs.category || "semantic",
        importance: Number(toolInputs.importance) || 5,
        tags: ["mcp", "manual"],
      };
    } else if (selectedTool === "memoryverse_get_graph") {
      args = { limit: Number(toolInputs.limit) || 20 };
    } else if (selectedTool === "memoryverse_list_documents") {
      args = { limit: Number(toolInputs.limit) || 10 };
    } else if (selectedTool === "memoryverse_review_inbox") {
      args = { limit: Number(toolInputs.limit) || 10 };
    }

    const rpcPayload = {
      jsonrpc: "2.0",
      id: Date.now(),
      method: "tools/call",
      params: {
        name: selectedTool,
        arguments: args,
      },
    };

    try {
      const res: any = await api.post("/mcp", rpcPayload);
      const rpcData = res?.data || res;
      setRawRpcResponse(rpcData);
      if (rpcData?.result?.content?.[0]?.text) {
        setToolOutput(rpcData.result.content[0].text);
      } else if (rpcData?.error) {
        setToolOutput(`Error (${rpcData.error.code || "RPC"}): ${rpcData.error.message}`);
      } else {
        setToolOutput(JSON.stringify(rpcData, null, 2));
      }
    } catch (err: any) {
      setToolOutput(`Request failed: ${err.message || String(err)}`);
    } finally {
      setIsRunning(false);
    }
  };

  const claudeConfigSnippet = JSON.stringify(
    configData?.claude_desktop || {
      mcpServers: {
        "ai-memoryverse": {
          command: "/Users/BharathR/AI-MemoryVerse/backend/.venv/bin/python",
          args: ["/Users/BharathR/AI-MemoryVerse/mcp_server.py"],
          env: {
            PYTHONPATH: "/Users/BharathR/AI-MemoryVerse/backend",
          },
        },
      },
    },
    null,
    2
  );

  const cursorConfigSnippet = JSON.stringify(
    configData?.cursor || {
      mcpServers: {
        "ai-memoryverse": {
          command: "/Users/BharathR/AI-MemoryVerse/backend/.venv/bin/python",
          args: ["/Users/BharathR/AI-MemoryVerse/mcp_server.py"],
        },
      },
    },
    null,
    2
  );

  const httpSnippet = JSON.stringify(
    {
      name: "ai-memoryverse",
      transport: "http-sse",
      sse_endpoint: "http://localhost:8000/api/v1/mcp/sse",
      rpc_endpoint: "http://localhost:8000/api/v1/mcp",
      protocolVersion: "2024-11-05",
    },
    null,
    2
  );

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Cpu className="w-4 h-4" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Model Context Protocol (MCP) Hub
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1 max-w-2xl">
            Anthropic open-standard connector enabling Claude Desktop, Cursor, and Antigravity to
            seamlessly query memories, save thoughts, navigate knowledge graphs, and search your vault.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <div className="px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center space-x-2 text-emerald-400 text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            <span>MCP Server Active (JSON-RPC 2.0)</span>
          </div>
        </div>
      </div>

      {/* Quick Setup Cards Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        {/* Left Col: Client Configurator */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/40 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Terminal className="w-5 h-5 text-cyan-400" />
                <h3 className="font-semibold text-white text-base">Client Connection Config</h3>
              </div>
              <div className="flex items-center space-x-1 p-1 bg-navy-950 rounded-lg border border-navy-800">
                <button
                  type="button"
                  onClick={() => setActiveTab("claude")}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    activeTab === "claude"
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Claude Desktop
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("cursor")}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    activeTab === "cursor"
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  Cursor
                </button>
                <button
                  type="button"
                  onClick={() => setActiveTab("http")}
                  className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                    activeTab === "http"
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "text-slate-400 hover:text-white"
                  }`}
                >
                  HTTP / SSE
                </button>
              </div>
            </div>

            <p className="text-xs text-slate-400">
              {activeTab === "claude" && (
                <>
                  Paste into{" "}
                  <code className="text-cyan-300 font-mono text-[11px] bg-navy-950 px-1 py-0.5 rounded">
                    ~/Library/Application Support/Claude/claude_desktop_config.json
                  </code>{" "}
                  then restart Claude Desktop.
                </>
              )}
              {activeTab === "cursor" && (
                <>
                  Add to your project root under{" "}
                  <code className="text-cyan-300 font-mono text-[11px] bg-navy-950 px-1 py-0.5 rounded">
                    .cursor/mcp.json
                  </code>{" "}
                  or Cursor Settings → Features → MCP.
                </>
              )}
              {activeTab === "http" && (
                <>Connect any remote AI agent using the standard HTTP / SSE protocol endpoints.</>
              )}
            </p>

            <div className="relative group">
              <pre className="p-4 rounded-xl bg-navy-950 border border-navy-800 font-mono text-xs text-slate-300 overflow-x-auto max-h-72">
                {activeTab === "claude" && claudeConfigSnippet}
                {activeTab === "cursor" && cursorConfigSnippet}
                {activeTab === "http" && httpSnippet}
              </pre>
              <button
                type="button"
                onClick={() =>
                  handleCopy(
                    activeTab === "claude"
                      ? claudeConfigSnippet
                      : activeTab === "cursor"
                      ? cursorConfigSnippet
                      : httpSnippet
                  )
                }
                className="absolute top-3 right-3 px-2.5 py-1.5 rounded-lg bg-navy-800/80 hover:bg-navy-700 text-slate-300 text-xs flex items-center space-x-1.5 border border-navy-700 transition-all opacity-80 group-hover:opacity-100"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span className="text-emerald-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5 text-slate-300" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Right Col: Live Interactive Tool Sandbox */}
        <div className="lg:col-span-6 space-y-4">
          <div className="p-6 rounded-2xl border border-navy-800 bg-navy-900/40 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Code2 className="w-5 h-5 text-cyan-400" />
                <h3 className="font-semibold text-white text-base">Live MCP Tool Tester</h3>
              </div>
              <span className="text-[11px] font-mono text-slate-400 uppercase">
                Interactive Sandbox
              </span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">
                  Select MCP Tool to Execute
                </label>
                <select
                  value={selectedTool}
                  onChange={(e) => setSelectedTool(e.target.value)}
                  className="w-full bg-navy-950 border border-navy-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
                >
                  <option value="memoryverse_get_stats">memoryverse_get_stats — Vault Telemetry</option>
                  <option value="memoryverse_search">memoryverse_search — Hybrid Vector/Keyword</option>
                  <option value="memoryverse_add_memory">memoryverse_add_memory — Save Long-Term Fact</option>
                  <option value="memoryverse_get_graph">memoryverse_get_graph — Knowledge Graph</option>
                  <option value="memoryverse_list_documents">memoryverse_list_documents — Ingested Files</option>
                  <option value="memoryverse_review_inbox">memoryverse_review_inbox — Candidate Facts</option>
                </select>
              </div>

              {selectedTool === "memoryverse_search" && (
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Search Query
                  </label>
                  <input
                    type="text"
                    value={toolInputs.query || ""}
                    onChange={(e) => setToolInputs({ ...toolInputs, query: e.target.value })}
                    placeholder="e.g. project architecture or personal preferences"
                    className="w-full bg-navy-950 border border-navy-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>
              )}

              {selectedTool === "memoryverse_add_memory" && (
                <>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1">
                      Memory Content
                    </label>
                    <textarea
                      rows={2}
                      value={toolInputs.content || ""}
                      onChange={(e) => setToolInputs({ ...toolInputs, content: e.target.value })}
                      placeholder="Enter the fact to store..."
                      className="w-full bg-navy-950 border border-navy-700 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-cyan-500 resize-none"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Category
                      </label>
                      <select
                        value={toolInputs.category || "semantic"}
                        onChange={(e) => setToolInputs({ ...toolInputs, category: e.target.value })}
                        className="w-full bg-navy-950 border border-navy-700 rounded-lg px-3 py-2 text-xs text-white"
                      >
                        <option value="semantic">Semantic (Knowledge)</option>
                        <option value="episodic">Episodic (Event)</option>
                        <option value="project">Project / Task</option>
                        <option value="preference">Personal Preference</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-300 mb-1">
                        Importance (1-10)
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        value={toolInputs.importance || 5}
                        onChange={(e) =>
                          setToolInputs({ ...toolInputs, importance: e.target.value })
                        }
                        className="w-full bg-navy-950 border border-navy-700 rounded-lg px-3 py-2 text-xs text-white"
                      />
                    </div>
                  </div>
                </>
              )}

              <button
                type="button"
                onClick={executeSandboxTool}
                disabled={isRunning}
                className="w-full py-2.5 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs flex items-center justify-center space-x-2 transition-colors disabled:opacity-50"
              >
                {isRunning ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Executing JSON-RPC Method...</span>
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4 fill-current" />
                    <span>Execute MCP Tool</span>
                  </>
                )}
              </button>

              {toolOutput && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
                      MCP Output Result
                    </span>
                    <span className="text-[10px] text-emerald-400 font-mono">Status: 200 OK</span>
                  </div>
                  <pre className="p-3 rounded-xl bg-navy-950 border border-navy-800 text-xs text-slate-200 font-mono whitespace-pre-wrap max-h-56 overflow-y-auto">
                    {toolOutput}
                  </pre>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Available Tools Catalog Section */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white">Registered MCP Tools Specification</h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {tools.map((t) => {
            const reqProps = t.inputSchema?.required || [];
            return (
              <div
                key={t.name}
                className="p-5 rounded-2xl border border-navy-800 bg-navy-900/30 hover:border-cyan-500/40 transition-colors flex flex-col justify-between"
              >
                <div className="space-y-2.5">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-bold text-cyan-400 bg-cyan-500/10 px-2 py-1 rounded border border-cyan-500/20">
                      {t.name}
                    </span>
                    <ShieldCheck className="w-4 h-4 text-emerald-400" />
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed">{t.description}</p>
                </div>

                <div className="mt-4 pt-3 border-t border-navy-800/80">
                  <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider block mb-1">
                    Input Parameters
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.keys(t.inputSchema?.properties || {}).map((prop) => {
                      const isReq = reqProps.includes(prop);
                      return (
                        <span
                          key={prop}
                          className={`text-[10px] font-mono px-2 py-0.5 rounded border ${
                            isReq
                              ? "bg-amber-500/10 text-amber-400 border-amber-500/30 font-semibold"
                              : "bg-navy-950 text-slate-400 border-navy-800"
                          }`}
                        >
                          {prop}
                          {isReq ? " *" : ""}
                        </span>
                      );
                    })}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
