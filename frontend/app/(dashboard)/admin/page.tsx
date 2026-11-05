"use client";

import { useEffect, useState } from "react";
import {
  ShieldAlert,
  Server,
  Database,
  Layers,
  Activity,
  Users,
  Building,
  Brain,
  FileText,
  Clock,
  RefreshCw,
  Loader2,
  CheckCircle2,
  Terminal,
  ShieldCheck,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface SystemOverview {
  total_users: number;
  total_workspaces: number;
  total_memories: number;
  total_documents: number;
  plans_distribution: Record<string, number>;
  health: {
    database: {
      status: string;
      latency_ms: number;
      engine: string;
    };
    redis_cache: {
      status: string;
      mode: string;
    };
    storage_provider: {
      status: string;
      provider: string;
      bucket: string;
    };
    background_worker: {
      status: string;
      framework: string;
      queues: string[];
    };
  };
}

interface AuditEvent {
  id: string;
  workspace_id?: string | null;
  user_id?: string | null;
  action: string;
  ip_address?: string | null;
  user_agent?: string | null;
  details: Record<string, any>;
  created_at: string;
}

export default function AdminPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [overview, setOverview] = useState<SystemOverview | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedLogId, setExpandedLogId] = useState<string | null>(null);

  const fetchAdminData = async () => {
    try {
      const [overviewRes, logsRes] = await Promise.all([
        api.get<SystemOverview>("/admin/overview"),
        api.get<AuditEvent[]>("/admin/audit-logs?limit=50"),
      ]);

      if (overviewRes.success && overviewRes.data) setOverview(overviewRes.data);
      if (logsRes.success && logsRes.data) setAuditLogs(logsRes.data);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAdminData();
  }, [activeWorkspaceId]);

  const toggleExpandLog = (id: string) => {
    setExpandedLogId((prev) => (prev === id ? null : id));
  };

  if (isLoading) {
    return (
      <div className="p-12 text-center text-slate-500 bg-navy-900/50 border border-navy-800 rounded-xl">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-cyan-400 mb-3" />
        <p className="text-sm">Querying system telemetry and health probes...</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Admin Console & Infrastructure Telemetry
              </h1>
              <p className="text-sm text-slate-400">
                System health metrics, background worker diagnostics, and security audit log stream.
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            setIsRefreshing(true);
            fetchAdminData();
          }}
          disabled={isRefreshing}
          className="flex items-center space-x-2 px-3.5 py-2 bg-navy-900 border border-navy-700 hover:border-slate-600 rounded-lg text-xs font-semibold text-slate-200 hover:text-white transition"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin" : ""}`} />
          <span>Refresh Probes</span>
        </button>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Total Users
            </span>
            <Users className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {overview?.total_users.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-500">Registered SaaS accounts</p>
        </div>

        <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Active Workspaces
            </span>
            <Building className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {overview?.total_workspaces.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-500">Multi-tenant isolated brains</p>
        </div>

        <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Ingested Memories
            </span>
            <Brain className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {overview?.total_memories.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-500">Vector-indexed facts</p>
        </div>

        <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">
              Parsed Documents
            </span>
            <FileText className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-3xl font-extrabold text-white">
            {overview?.total_documents.toLocaleString() || 0}
          </div>
          <p className="text-[11px] text-slate-500">Chunked & embedded files</p>
        </div>
      </div>

      {/* Infrastructure Telemetry Probes */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">
          Live Service Telemetry & Connectivity
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Database */}
          <div className="p-5 bg-navy-900/60 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-white font-semibold text-sm">
                <Database className="w-4 h-4 text-cyan-400" />
                <span>PostgreSQL & pgvector</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                {overview?.health.database.status}
              </span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>Engine: {overview?.health.database.engine}</div>
              <div className="font-mono text-cyan-300">
                Ping Latency: {overview?.health.database.latency_ms} ms
              </div>
            </div>
          </div>

          {/* Redis */}
          <div className="p-5 bg-navy-900/60 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-white font-semibold text-sm">
                <Layers className="w-4 h-4 text-rose-400" />
                <span>Redis / Key Value</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                {overview?.health.redis_cache.status}
              </span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>Mode: {overview?.health.redis_cache.mode}</div>
              <div>State: In-memory broker active</div>
            </div>
          </div>

          {/* S3 Storage */}
          <div className="p-5 bg-navy-900/60 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-white font-semibold text-sm">
                <Server className="w-4 h-4 text-purple-400" />
                <span>Object Storage</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                {overview?.health.storage_provider.status}
              </span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>Adapter: {overview?.health.storage_provider.provider}</div>
              <div>Bucket: {overview?.health.storage_provider.bucket}</div>
            </div>
          </div>

          {/* Celery Background Workers */}
          <div className="p-5 bg-navy-900/60 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2 text-white font-semibold text-sm">
                <Activity className="w-4 h-4 text-amber-400" />
                <span>Celery Workers</span>
              </div>
              <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase bg-emerald-500/20 text-emerald-400 border border-emerald-500/40">
                {overview?.health.background_worker.status}
              </span>
            </div>
            <div className="text-xs text-slate-400 space-y-1">
              <div>Framework: {overview?.health.background_worker.framework}</div>
              <div>Queues: {overview?.health.background_worker.queues.join(", ")}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Subscription Breakdown */}
      {overview?.plans_distribution && (
        <div className="p-6 bg-navy-900/60 border border-navy-800 rounded-xl space-y-4">
          <h3 className="text-sm font-semibold text-white">
            Workspace Subscription Tier Distribution
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {Object.entries(overview.plans_distribution).map(([tier, count]) => (
              <div
                key={tier}
                className="p-3 bg-navy-950/70 border border-navy-800 rounded-lg flex items-center justify-between"
              >
                <span className="text-xs font-bold uppercase text-slate-300">
                  {tier}
                </span>
                <span className="font-mono text-sm font-extrabold text-cyan-400">
                  {count} workspaces
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Security Audit Log Stream */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Terminal className="w-4 h-4 text-cyan-400" />
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-300">
              Security & Compliance Audit Trail ({auditLogs.length})
            </h2>
          </div>
          <span className="text-xs text-slate-500">Last 50 recorded events</span>
        </div>

        {auditLogs.length === 0 ? (
          <div className="p-8 text-center text-slate-500 bg-navy-900/40 border border-navy-800 rounded-xl">
            <ShieldCheck className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            <p className="text-xs">No audit events recorded yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {auditLogs.map((log) => {
              const isExpanded = expandedLogId === log.id;
              return (
                <div
                  key={log.id}
                  className="bg-navy-900/70 border border-navy-800 rounded-xl overflow-hidden transition"
                >
                  <div
                    onClick={() => toggleExpandLog(log.id)}
                    className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-navy-800/40 select-none text-xs"
                  >
                    <div className="flex items-center space-x-3">
                      <span className="px-2 py-0.5 rounded bg-cyan-950 border border-cyan-800 text-[11px] font-mono text-cyan-300">
                        {log.action}
                      </span>
                      <span className="text-slate-400">
                        {log.workspace_id ? `Workspace: ${log.workspace_id.slice(0, 8)}...` : "System-wide"}
                      </span>
                    </div>

                    <div className="flex items-center space-x-4">
                      {log.ip_address && (
                        <span className="text-slate-500 font-mono text-[11px]">
                          IP: {log.ip_address}
                        </span>
                      )}
                      <span className="text-slate-400">{formatDate(log.created_at)}</span>
                      {isExpanded ? (
                        <ChevronDown className="w-4 h-4 text-slate-400" />
                      ) : (
                        <ChevronRight className="w-4 h-4 text-slate-400" />
                      )}
                    </div>
                  </div>

                  {isExpanded && (
                    <div className="p-4 border-t border-navy-800 bg-navy-950/90 text-xs space-y-2">
                      <span className="font-semibold text-slate-400 block">
                        Event Metadata & Payload:
                      </span>
                      <pre className="p-2.5 rounded bg-black/60 border border-navy-800 font-mono text-cyan-300 overflow-x-auto">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
