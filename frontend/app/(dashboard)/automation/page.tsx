"use client";

import { useEffect, useState } from "react";
import {
  Bot,
  Play,
  Globe,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  ShieldAlert,
  Terminal,
  ChevronRight,
  ChevronDown,
  RefreshCw,
  Plus,
  ArrowRight,
  Loader2,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface AgentAction {
  id: string;
  step_number: number;
  tool_name: string;
  tool_input: Record<string, any>;
  tool_output?: Record<string, any> | null;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  approval_status: "not_required" | "pending" | "approved" | "rejected";
  execution_status: "pending" | "executing" | "completed" | "failed";
  execution_latency_ms?: number | null;
  error_message?: string | null;
  created_at: string;
}

interface AgentTask {
  id: string;
  title: string;
  goal: string;
  status: "pending" | "running" | "waiting_approval" | "completed" | "failed";
  steps_taken: number;
  steps_limit: number;
  final_result?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  actions: AgentAction[];
}

interface ToolInfo {
  name: string;
  description: string;
  risk_level: "LOW" | "MEDIUM" | "HIGH";
  parameters: Record<string, any>;
}

export default function AutomationAgentsPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [tasks, setTasks] = useState<AgentTask[]>([]);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [selectedTask, setSelectedTask] = useState<AgentTask | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [expandedActions, setExpandedActions] = useState<Record<string, boolean>>({});

  // Modals state
  const [isNewTaskOpen, setIsNewTaskOpen] = useState(false);
  const [isUrlImportOpen, setIsUrlImportOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [actionProcessingId, setActionProcessingId] = useState<string | null>(null);

  // New task form state
  const [taskTitle, setTaskTitle] = useState("");
  const [taskGoal, setTaskGoal] = useState("");
  const [stepsLimit, setStepsLimit] = useState(10);
  const [executeImmediately, setExecuteImmediately] = useState(true);

  // URL import form state
  const [importUrl, setImportUrl] = useState("");
  const [importTitle, setImportTitle] = useState("");
  const [autoExtract, setAutoExtract] = useState(true);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    message: string;
    textLength?: number;
    memoriesFound?: number;
  } | null>(null);

  const fetchTasks = async () => {
    try {
      const res = await api.get<{ items: AgentTask[]; total: number }>("/agents/tasks");
      if (res.success && res.data) {
        setTasks(res.data.items || []);
        if (selectedTask) {
          const updated = res.data.items.find((t) => t.id === selectedTask.id);
          if (updated) setSelectedTask(updated);
        } else if (res.data.items.length > 0) {
          setSelectedTask(res.data.items[0]);
        }
      }
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const fetchTools = async () => {
    const res = await api.get<{ tools: ToolInfo[] }>("/agents/tools");
    if (res.success && res.data) {
      setTools(res.data.tools || []);
    }
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      setIsLoading(true);
      fetchTasks();
      fetchTools();
    }
  }, [activeWorkspaceId]);

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskTitle.trim() || !taskGoal.trim()) return;

    setIsSubmitting(true);
    try {
      const res = await api.post<AgentTask>("/agents/tasks", {
        title: taskTitle.trim(),
        goal: taskGoal.trim(),
        steps_limit: stepsLimit,
        execute_immediately: executeImmediately,
      });

      if (res.success && res.data) {
        setIsNewTaskOpen(false);
        setTaskTitle("");
        setTaskGoal("");
        await fetchTasks();
        setSelectedTask(res.data);
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleApproveAction = async (actionId: string) => {
    setActionProcessingId(actionId);
    try {
      const res = await api.post(`/agents/actions/${actionId}/approve`);
      if (res.success) {
        await fetchTasks();
      }
    } finally {
      setActionProcessingId(null);
    }
  };

  const handleRejectAction = async (actionId: string) => {
    setActionProcessingId(actionId);
    try {
      const res = await api.post(`/agents/actions/${actionId}/reject`);
      if (res.success) {
        await fetchTasks();
      }
    } finally {
      setActionProcessingId(null);
    }
  };

  const handleImportUrl = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!importUrl.trim()) return;

    setIsSubmitting(true);
    setImportResult(null);
    try {
      const res = await api.post<{
        document_id: string;
        title: string;
        url: string;
        extracted_text_length: number;
        extracted_memories_count: number;
      }>("/agents/import-url", {
        url: importUrl.trim(),
        title: importTitle.trim() || undefined,
        auto_extract_memories: autoExtract,
      });

      if (res.success && res.data) {
        setImportResult({
          success: true,
          message: `Successfully imported "${res.data.title}"`,
          textLength: res.data.extracted_text_length,
          memoriesFound: res.data.extracted_memories_count,
        });
        setImportUrl("");
        setImportTitle("");
      } else {
        setImportResult({
          success: false,
          message: res.error?.message || "URL import blocked or failed",
        });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const toggleExpandAction = (actionId: string) => {
    setExpandedActions((prev) => ({
      ...prev,
      [actionId]: !prev[actionId],
    }));
  };

  const getStatusBadge = (status: AgentTask["status"]) => {
    switch (status) {
      case "running":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
            <Loader2 className="w-3 h-3 mr-1 animate-spin" /> Running
          </span>
        );
      case "waiting_approval":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-rose-500/15 text-rose-400 border border-rose-500/40 animate-pulse">
            <ShieldAlert className="w-3 h-3 mr-1" /> Awaiting Approval
          </span>
        );
      case "completed":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
            <CheckCircle2 className="w-3 h-3 mr-1" /> Completed
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-rose-500/10 text-rose-400 border border-rose-500/30">
            <XCircle className="w-3 h-3 mr-1" /> Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-slate-500/10 text-slate-400 border border-slate-500/30">
            <Clock className="w-3 h-3 mr-1" /> Pending
          </span>
        );
    }
  };

  const getRiskBadge = (risk: "LOW" | "MEDIUM" | "HIGH") => {
    switch (risk) {
      case "HIGH":
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-rose-500/20 text-rose-400 border border-rose-500/40">
            HIGH RISK
          </span>
        );
      case "MEDIUM":
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-amber-500/20 text-amber-400 border border-amber-500/40">
            MEDIUM
          </span>
        );
      default:
        return (
          <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
            LOW RISK
          </span>
        );
    }
  };

  // Find all pending approval actions across all tasks
  const pendingApprovalActions = tasks.flatMap((t) =>
    t.actions
      .filter((a) => a.approval_status === "pending")
      .map((a) => ({ task: t, action: a }))
  );

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <Bot className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Controlled Autonomous Agents
              </h1>
              <p className="text-sm text-slate-400">
                Multi-step autonomous reasoning with strict Human-in-the-Loop checkpoints and SSRF protection.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setIsRefreshing(true);
              fetchTasks();
            }}
            disabled={isRefreshing}
            className="p-2 rounded-lg bg-navy-900 border border-navy-700 hover:border-slate-600 text-slate-300 hover:text-white transition"
            title="Refresh Tasks"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
          </button>

          <button
            onClick={() => setIsUrlImportOpen(true)}
            className="flex items-center space-x-2 px-3 py-2 bg-navy-900 border border-navy-700 hover:border-cyan-500/50 rounded-lg text-sm font-medium text-slate-200 hover:text-cyan-400 transition"
          >
            <Globe className="w-4 h-4 text-cyan-400" />
            <span>Import Webpage</span>
          </button>

          <button
            onClick={() => setIsNewTaskOpen(true)}
            className="flex items-center space-x-2 px-4 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-lg text-sm font-semibold shadow-lg shadow-cyan-500/20 transition"
          >
            <Plus className="w-4 h-4" />
            <span>Launch Task</span>
          </button>
        </div>
      </div>

      {/* Human-In-The-Loop Approval Banner */}
      {pendingApprovalActions.length > 0 && (
        <div className="bg-rose-950/40 border border-rose-500/50 rounded-xl p-5 shadow-lg shadow-rose-950/20">
          <div className="flex items-start space-x-3.5">
            <div className="p-2 rounded-lg bg-rose-500/20 text-rose-400 mt-0.5">
              <ShieldAlert className="w-6 h-6 animate-bounce" />
            </div>
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold text-rose-300">
                  Human-in-the-Loop Approval Required ({pendingApprovalActions.length})
                </h3>
                <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-rose-500 text-white">
                  ACTION PAUSED
                </span>
              </div>
              <p className="text-sm text-slate-300 mt-1">
                An autonomous agent proposed a high-consequence action that requires explicit operator authorization before proceeding.
              </p>

              <div className="mt-4 space-y-3">
                {pendingApprovalActions.map(({ task, action }) => (
                  <div
                    key={action.id}
                    className="p-4 bg-navy-900/90 border border-rose-500/30 rounded-lg flex flex-col md:flex-row md:items-center justify-between gap-4"
                  >
                    <div>
                      <div className="flex items-center space-x-2">
                        <span className="font-mono text-xs px-2 py-0.5 bg-rose-950 text-rose-400 rounded border border-rose-800">
                          {action.tool_name}
                        </span>
                        <span className="text-sm font-medium text-white">
                          Task: {task.title}
                        </span>
                        {getRiskBadge(action.risk_level)}
                      </div>
                      <div className="mt-2 text-xs font-mono text-slate-400 bg-navy-950/80 p-2 rounded border border-navy-800 overflow-x-auto max-w-xl">
                        {JSON.stringify(action.tool_input)}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2.5 shrink-0">
                      <button
                        onClick={() => handleRejectAction(action.id)}
                        disabled={actionProcessingId === action.id}
                        className="px-3.5 py-1.5 bg-navy-950 hover:bg-rose-950/80 border border-rose-800 text-rose-400 hover:text-rose-300 rounded-lg text-xs font-medium transition disabled:opacity-50"
                      >
                        Reject & Abort
                      </button>
                      <button
                        onClick={() => handleApproveAction(action.id)}
                        disabled={actionProcessingId === action.id}
                        className="flex items-center space-x-1.5 px-4 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-bold shadow-md shadow-rose-600/30 transition disabled:opacity-50"
                      >
                        {actionProcessingId === action.id ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <ShieldCheck className="w-3.5 h-3.5" />
                        )}
                        <span>Approve & Execute</span>
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Grid: Tasks List & Detail View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Tasks List */}
        <div className="lg:col-span-4 space-y-4">
          <div className="flex items-center justify-between px-1">
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
              Active & Past Tasks ({tasks.length})
            </h2>
          </div>

          {isLoading ? (
            <div className="p-8 text-center text-slate-500 bg-navy-900/50 border border-navy-800 rounded-xl">
              <Loader2 className="w-6 h-6 animate-spin mx-auto text-cyan-400 mb-2" />
              <p className="text-xs">Loading agent tasks...</p>
            </div>
          ) : tasks.length === 0 ? (
            <div className="p-8 text-center bg-navy-900/50 border border-dashed border-navy-800 rounded-xl">
              <Bot className="w-8 h-8 text-slate-600 mx-auto mb-2" />
              <p className="text-sm font-medium text-slate-300">No autonomous tasks yet</p>
              <p className="text-xs text-slate-500 mt-1">
                Launch your first agent to research, organize memories, or fetch web data.
              </p>
              <button
                onClick={() => setIsNewTaskOpen(true)}
                className="mt-4 px-3 py-1.5 bg-navy-800 hover:bg-navy-700 text-cyan-400 text-xs font-medium rounded-lg border border-cyan-500/30 transition"
              >
                + Launch Agent Task
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {tasks.map((task) => {
                const isSelected = selectedTask?.id === task.id;
                return (
                  <div
                    key={task.id}
                    onClick={() => setSelectedTask(task)}
                    className={`p-4 rounded-xl border transition cursor-pointer ${
                      isSelected
                        ? "bg-navy-800/90 border-cyan-500/60 shadow-lg shadow-cyan-950/30"
                        : "bg-navy-900/60 border-navy-800 hover:border-navy-700 hover:bg-navy-900"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <h3 className="text-sm font-semibold text-white line-clamp-1">
                        {task.title}
                      </h3>
                      {getStatusBadge(task.status)}
                    </div>

                    <p className="text-xs text-slate-400 mt-1 line-clamp-2">
                      {task.goal}
                    </p>

                    <div className="flex items-center justify-between mt-3 text-[11px] text-slate-500 font-mono">
                      <span>
                        Steps: {task.steps_taken} / {task.steps_limit}
                      </span>
                      <span>{formatDate(task.created_at)}</span>
                    </div>

                    {/* Progress Bar */}
                    <div className="w-full bg-navy-950 rounded-full h-1.5 mt-2 overflow-hidden border border-navy-800">
                      <div
                        className={`h-full transition-all duration-500 ${
                          task.status === "completed"
                            ? "bg-emerald-400"
                            : task.status === "failed"
                            ? "bg-rose-400"
                            : task.status === "waiting_approval"
                            ? "bg-amber-400"
                            : "bg-cyan-400"
                        }`}
                        style={{
                          width: `${Math.min(
                            100,
                            (task.steps_taken / Math.max(1, task.steps_limit)) * 100
                          )}%`,
                        }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Available Registered Tools Card */}
          <div className="p-4 bg-navy-900/60 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center space-x-2">
              <Zap className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Registered Tool Registry ({tools.length})
              </h3>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Every tool execution is audited. High-risk actions automatically halt for human consent.
            </p>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {tools.map((t) => (
                <div
                  key={t.name}
                  className="p-2 bg-navy-950/70 border border-navy-800/80 rounded-lg flex items-center justify-between text-xs"
                >
                  <div className="font-mono text-[11px] text-cyan-300">{t.name}</div>
                  {getRiskBadge(t.risk_level)}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Selected Task Audit Trail & Execution Steps */}
        <div className="lg:col-span-8">
          {selectedTask ? (
            <div className="bg-navy-900/70 border border-navy-800 rounded-xl p-6 space-y-6">
              {/* Task Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-navy-800">
                <div>
                  <div className="flex items-center space-x-3">
                    <h2 className="text-xl font-bold text-white tracking-tight">
                      {selectedTask.title}
                    </h2>
                    {getStatusBadge(selectedTask.status)}
                  </div>
                  <p className="text-xs font-mono text-slate-400 mt-1">
                    Task ID: {selectedTask.id} • Created: {formatDate(selectedTask.created_at)}
                  </p>
                </div>
              </div>

              {/* Goal Description */}
              <div className="p-4 bg-navy-950/60 border border-navy-800 rounded-lg">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400 block mb-1">
                  Agent Directive & Goal
                </span>
                <p className="text-sm text-slate-200 leading-relaxed">
                  {selectedTask.goal}
                </p>
              </div>

              {/* Final Synthesis / Result */}
              {selectedTask.final_result && (
                <div className="p-4 bg-emerald-950/30 border border-emerald-500/30 rounded-lg">
                  <div className="flex items-center space-x-2 text-emerald-400 mb-1.5">
                    <CheckCircle2 className="w-4 h-4" />
                    <span className="text-xs font-bold uppercase tracking-wider">
                      Synthesized Task Conclusion
                    </span>
                  </div>
                  <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
                    {selectedTask.final_result}
                  </p>
                </div>
              )}

              {/* Action Trail */}
              <div>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-2">
                    <Terminal className="w-4 h-4 text-cyan-400" />
                    <h3 className="text-sm font-semibold text-white">
                      Execution Action Audit Trail ({selectedTask.actions?.length || 0})
                    </h3>
                  </div>
                  <span className="text-xs text-slate-400">
                    Step {selectedTask.steps_taken} of {selectedTask.steps_limit}
                  </span>
                </div>

                {(!selectedTask.actions || selectedTask.actions.length === 0) ? (
                  <div className="p-8 text-center text-slate-500 bg-navy-950/40 rounded-lg border border-navy-800">
                    <Clock className="w-6 h-6 mx-auto mb-2 text-slate-600" />
                    <p className="text-xs">No tool actions executed yet.</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {selectedTask.actions.map((act) => {
                      const isExpanded = !!expandedActions[act.id];
                      return (
                        <div
                          key={act.id}
                          className="bg-navy-950/80 border border-navy-800 rounded-lg overflow-hidden transition"
                        >
                          {/* Step summary bar */}
                          <div
                            onClick={() => toggleExpandAction(act.id)}
                            className="p-3.5 flex items-center justify-between cursor-pointer hover:bg-navy-800/40 select-none"
                          >
                            <div className="flex items-center space-x-3">
                              <span className="w-6 h-6 rounded-full bg-navy-800 border border-navy-700 text-xs font-mono text-cyan-400 flex items-center justify-center shrink-0">
                                {act.step_number}
                              </span>
                              <div>
                                <div className="flex items-center space-x-2">
                                  <span className="font-mono text-xs font-bold text-white">
                                    {act.tool_name}
                                  </span>
                                  {getRiskBadge(act.risk_level)}
                                  {act.approval_status === "pending" && (
                                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">
                                      AWAITING HUMAN APPROVAL
                                    </span>
                                  )}
                                  {act.approval_status === "approved" && (
                                    <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-emerald-500/20 text-emerald-300">
                                      APPROVED
                                    </span>
                                  )}
                                  {act.approval_status === "rejected" && (
                                    <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-rose-500/20 text-rose-300">
                                      REJECTED
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center space-x-3">
                              {act.execution_latency_ms && (
                                <span className="text-[11px] font-mono text-slate-500">
                                  {act.execution_latency_ms}ms
                                </span>
                              )}
                              {act.execution_status === "completed" ? (
                                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                              ) : act.execution_status === "failed" ? (
                                <XCircle className="w-4 h-4 text-rose-400" />
                              ) : (
                                <Loader2 className="w-4 h-4 text-amber-400 animate-spin" />
                              )}
                              {isExpanded ? (
                                <ChevronDown className="w-4 h-4 text-slate-400" />
                              ) : (
                                <ChevronRight className="w-4 h-4 text-slate-400" />
                              )}
                            </div>
                          </div>

                          {/* Expandable Inputs & Outputs Drawer */}
                          {isExpanded && (
                            <div className="p-4 border-t border-navy-800 bg-navy-950/90 space-y-3 text-xs">
                              <div>
                                <span className="font-semibold text-slate-400 block mb-1">
                                  Input Parameters:
                                </span>
                                <pre className="p-2.5 rounded bg-black/50 border border-navy-800 font-mono text-cyan-300 overflow-x-auto">
                                  {JSON.stringify(act.tool_input, null, 2)}
                                </pre>
                              </div>

                              {act.tool_output && (
                                <div>
                                  <span className="font-semibold text-slate-400 block mb-1">
                                    Tool Output / Response:
                                  </span>
                                  <pre className="p-2.5 rounded bg-black/50 border border-navy-800 font-mono text-emerald-300 overflow-x-auto max-h-60">
                                    {JSON.stringify(act.tool_output, null, 2)}
                                  </pre>
                                </div>
                              )}

                              {act.error_message && (
                                <div className="p-2.5 rounded bg-rose-950/40 border border-rose-500/30 text-rose-300">
                                  <span className="font-bold">Error:</span> {act.error_message}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="h-full flex items-center justify-center p-12 bg-navy-900/40 border border-navy-800 rounded-xl text-center text-slate-500">
              Select a task from the list to view its audit trail.
            </div>
          )}
        </div>
      </div>

      {/* Modal: Launch Autonomous Task */}
      {isNewTaskOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <div className="flex items-center space-x-2">
                <Bot className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">Launch Autonomous Agent</h3>
              </div>
              <button
                onClick={() => setIsNewTaskOpen(false)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateTask} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Task Title
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Audit workspace memory conflicts and extract updates"
                  value={taskTitle}
                  onChange={(e) => setTaskTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Agent Goal / Instruction
                </label>
                <textarea
                  required
                  rows={4}
                  placeholder="Describe what the agent should accomplish. The agent will plan and execute steps using available tools (search, knowledge graph, web fetch, propose memories)."
                  value={taskGoal}
                  onChange={(e) => setTaskGoal(e.target.value)}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500 resize-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                    Max Steps Limit
                  </label>
                  <input
                    type="number"
                    min={1}
                    max={25}
                    value={stepsLimit}
                    onChange={(e) => setStepsLimit(parseInt(e.target.value) || 10)}
                    className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                  />
                </div>

                <div className="flex items-center space-x-2 mt-6">
                  <input
                    type="checkbox"
                    id="exec-now"
                    checked={executeImmediately}
                    onChange={(e) => setExecuteImmediately(e.target.checked)}
                    className="rounded bg-navy-950 border-navy-700 text-cyan-500 focus:ring-0"
                  />
                  <label htmlFor="exec-now" className="text-xs text-slate-300 select-none">
                    Execute immediately
                  </label>
                </div>
              </div>

              <div className="p-3 bg-navy-950/80 border border-navy-800 rounded-lg text-xs text-slate-400 flex items-start space-x-2">
                <ShieldCheck className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                <span>
                  High-risk actions like memory deletion or external webhooks will automatically pause for your approval before execution.
                </span>
              </div>

              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={() => setIsNewTaskOpen(false)}
                  className="px-4 py-2 bg-navy-800 hover:bg-navy-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center space-x-2 px-5 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-bold rounded-lg shadow-md transition disabled:opacity-50"
                >
                  {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Start Agent</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Import Webpage URL */}
      {isUrlImportOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
            <div className="flex items-center justify-between pb-3 border-b border-navy-800">
              <div className="flex items-center space-x-2">
                <Globe className="w-5 h-5 text-cyan-400" />
                <h3 className="text-lg font-bold text-white">Import Webpage into Knowledge</h3>
              </div>
              <button
                onClick={() => {
                  setIsUrlImportOpen(false);
                  setImportResult(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleImportUrl} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Public Web URL
                </label>
                <input
                  type="url"
                  required
                  placeholder="https://example.com/article"
                  value={importUrl}
                  onChange={(e) => setImportUrl(e.target.value)}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-slate-300 mb-1">
                  Document Title (Optional)
                </label>
                <input
                  type="text"
                  placeholder="Leave empty to extract page title automatically"
                  value={importTitle}
                  onChange={(e) => setImportTitle(e.target.value)}
                  className="w-full px-3 py-2 bg-navy-950 border border-navy-700 rounded-lg text-sm text-white focus:outline-none focus:border-cyan-500"
                />
              </div>

              <div className="flex items-center space-x-2">
                <input
                  type="checkbox"
                  id="auto-extract"
                  checked={autoExtract}
                  onChange={(e) => setAutoExtract(e.target.checked)}
                  className="rounded bg-navy-950 border-navy-700 text-cyan-500 focus:ring-0"
                />
                <label htmlFor="auto-extract" className="text-xs text-slate-300 select-none">
                  Automatically extract candidate memories from webpage content
                </label>
              </div>

              {/* SSRF Security Notice */}
              <div className="p-3 bg-navy-950/80 border border-navy-800 rounded-lg text-xs text-slate-400 flex items-start space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <span>
                  SSRF Protection Active: Localhost, private RFC 1918 networks, and cloud metadata services (169.254.169.254) are strictly blocked.
                </span>
              </div>

              {/* Status/Result Banner */}
              {importResult && (
                <div
                  className={`p-3 rounded-lg text-xs flex items-center space-x-2 ${
                    importResult.success
                      ? "bg-emerald-950/40 border border-emerald-500/30 text-emerald-300"
                      : "bg-rose-950/40 border border-rose-500/30 text-rose-300"
                  }`}
                >
                  {importResult.success ? (
                    <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
                  )}
                  <div>
                    <p className="font-semibold">{importResult.message}</p>
                    {importResult.success && (
                      <p className="text-[11px] text-slate-400 mt-0.5">
                        Cleaned Text: {importResult.textLength} chars • Extracted Memories: {importResult.memoriesFound}
                      </p>
                    )}
                  </div>
                </div>
              )}

              <div className="flex justify-end space-x-3 pt-3">
                <button
                  type="button"
                  onClick={() => {
                    setIsUrlImportOpen(false);
                    setImportResult(null);
                  }}
                  className="px-4 py-2 bg-navy-800 hover:bg-navy-700 text-slate-300 text-xs font-medium rounded-lg transition"
                >
                  Close
                </button>
                <button
                  type="submit"
                  disabled={isSubmitting}
                  className="flex items-center space-x-2 px-5 py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white text-xs font-bold rounded-lg shadow-md transition disabled:opacity-50"
                >
                  {isSubmitting && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>Fetch & Ingest</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

