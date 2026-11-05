"use client";

import { useEffect, useState } from "react";
import {
  CreditCard,
  Check,
  AlertTriangle,
  ArrowRight,
  Sparkles,
  ShieldCheck,
  Download,
  Loader2,
  Clock,
  HardDrive,
  FileText,
  Brain,
  MessageSquare,
  Zap,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface UsageMetric {
  used: number;
  limit: number;
  percentage: number;
  unit: string;
}

interface WorkspaceUsage {
  plan_tier: string;
  memories: UsageMetric;
  documents: UsageMetric;
  storage: UsageMetric;
  ai_queries: UsageMetric;
}

interface InvoiceItem {
  id: string;
  invoice_number: string;
  amount_cents: number;
  currency: string;
  status: string;
  invoice_url?: string | null;
  paid_at?: string | null;
  created_at: string;
}

interface SubscriptionInfo {
  id: string;
  workspace_id: string;
  plan_tier: string;
  status: string;
  current_period_start: string;
  current_period_end: string;
  cancel_at_period_end: boolean;
  invoices: InvoiceItem[];
}

interface PlanCatalogItem {
  tier: string;
  name: string;
  price_monthly: number;
  currency: string;
  description: string;
  limits: {
    max_memories: number;
    max_documents: number;
    max_storage_bytes: number;
    max_ai_queries: number;
  };
  features: string[];
}

export default function BillingPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [usage, setUsage] = useState<WorkspaceUsage | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [plans, setPlans] = useState<PlanCatalogItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [upgradingTier, setUpgradingTier] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      const [usageRes, subRes, plansRes] = await Promise.all([
        api.get<WorkspaceUsage>("/billing/usage"),
        api.get<SubscriptionInfo>("/billing/subscription"),
        api.get<PlanCatalogItem[]>("/billing/plans"),
      ]);

      if (usageRes.success && usageRes.data) setUsage(usageRes.data);
      if (subRes.success && subRes.data) setSubscription(subRes.data);
      if (plansRes.success && plansRes.data) setPlans(plansRes.data);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      setIsLoading(true);
      fetchData();
    }
  }, [activeWorkspaceId]);

  const handleUpgrade = async (tier: string) => {
    setUpgradingTier(tier);
    setSuccessMsg(null);
    try {
      const res = await api.post<SubscriptionInfo>("/billing/upgrade", {
        plan_tier: tier,
      });

      if (res.success && res.data) {
        setSubscription(res.data);
        setSuccessMsg(`Successfully upgraded workspace to ${tier.toUpperCase()} plan!`);
        // Refresh usage metrics
        const usageRes = await api.get<WorkspaceUsage>("/billing/usage");
        if (usageRes.success && usageRes.data) setUsage(usageRes.data);
      }
    } finally {
      setUpgradingTier(null);
    }
  };

  const handleCancelSubscription = async () => {
    if (
      !confirm(
        "Are you sure you want to cancel your subscription? Your plan will remain active until the end of the current billing cycle."
      )
    ) {
      return;
    }

    const res = await api.post<SubscriptionInfo>("/billing/cancel");
    if (res.success && res.data) {
      setSubscription(res.data);
      setSuccessMsg("Subscription scheduled for cancellation at period end.");
    }
  };

  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 MB";
    const mb = bytes / (1024 * 1024);
    if (mb < 1024) return `${mb.toFixed(1)} MB`;
    return `${(mb / 1024).toFixed(2)} GB`;
  };

  if (isLoading) {
    return (
      <div className="p-12 text-center text-slate-500 bg-navy-900/50 border border-navy-800 rounded-xl">
        <Loader2 className="w-8 h-8 animate-spin mx-auto text-cyan-400 mb-3" />
        <p className="text-sm">Loading usage metrics and billing info...</p>
      </div>
    );
  }

  const currentPlanTier = usage?.plan_tier || subscription?.plan_tier || "free";

  return (
    <div className="space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
              <CreditCard className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Usage, Quotas & Subscriptions
              </h1>
              <p className="text-sm text-slate-400">
                Transparent real-time resource meters and multi-tier SaaS subscription management.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400 uppercase tracking-wider font-semibold">
            Active Tier:
          </span>
          <span className="px-3 py-1 rounded-full text-xs font-bold uppercase tracking-wider bg-cyan-500/20 text-cyan-400 border border-cyan-500/40">
            {currentPlanTier} Plan
          </span>
        </div>
      </div>

      {/* Success Banner */}
      {successMsg && (
        <div className="p-4 rounded-xl bg-emerald-950/40 border border-emerald-500/40 flex items-center space-x-3 text-sm text-emerald-300">
          <Check className="w-5 h-5 text-emerald-400 shrink-0" />
          <span>{successMsg}</span>
        </div>
      )}

      {/* Quota Usage Meters Grid */}
      <div>
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-4">
          Real-Time Resource Quota Utilization
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* Memory Records */}
          <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center space-x-2">
                <Brain className="w-4 h-4 text-cyan-400" />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Verified Memories
                </span>
              </div>
              <span className="font-mono text-xs text-white">
                {usage?.memories.percentage}%
              </span>
            </div>
            <div className="text-2xl font-bold text-white tracking-tight">
              {usage?.memories.used.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {usage?.memories.limit.toLocaleString()} records
              </span>
            </div>
            <div className="w-full bg-navy-950 rounded-full h-2 overflow-hidden border border-navy-800">
              <div
                className="bg-cyan-400 h-full transition-all duration-500"
                style={{ width: `${usage?.memories.percentage}%` }}
              />
            </div>
          </div>

          {/* Document Ingestion */}
          <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center space-x-2">
                <FileText className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Ingested Files
                </span>
              </div>
              <span className="font-mono text-xs text-white">
                {usage?.documents.percentage}%
              </span>
            </div>
            <div className="text-2xl font-bold text-white tracking-tight">
              {usage?.documents.used.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {usage?.documents.limit.toLocaleString()} files
              </span>
            </div>
            <div className="w-full bg-navy-950 rounded-full h-2 overflow-hidden border border-navy-800">
              <div
                className="bg-emerald-400 h-full transition-all duration-500"
                style={{ width: `${usage?.documents.percentage}%` }}
              />
            </div>
          </div>

          {/* Cloud Storage */}
          <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center space-x-2">
                <HardDrive className="w-4 h-4 text-purple-400" />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  Object Storage
                </span>
              </div>
              <span className="font-mono text-xs text-white">
                {usage?.storage.percentage}%
              </span>
            </div>
            <div className="text-2xl font-bold text-white tracking-tight">
              {formatBytes(usage?.storage.used || 0)}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {formatBytes(usage?.storage.limit || 0)}
              </span>
            </div>
            <div className="w-full bg-navy-950 rounded-full h-2 overflow-hidden border border-navy-800">
              <div
                className="bg-purple-400 h-full transition-all duration-500"
                style={{ width: `${usage?.storage.percentage}%` }}
              />
            </div>
          </div>

          {/* AI Queries */}
          <div className="p-5 bg-navy-900/70 border border-navy-800 rounded-xl space-y-3">
            <div className="flex items-center justify-between text-slate-400">
              <div className="flex items-center space-x-2">
                <MessageSquare className="w-4 h-4 text-amber-400" />
                <span className="text-xs font-semibold uppercase tracking-wider">
                  AI RAG Queries
                </span>
              </div>
              <span className="font-mono text-xs text-white">
                {usage?.ai_queries.percentage}%
              </span>
            </div>
            <div className="text-2xl font-bold text-white tracking-tight">
              {usage?.ai_queries.used.toLocaleString()}
              <span className="text-xs font-normal text-slate-400 ml-1.5">
                / {usage?.ai_queries.limit.toLocaleString()} / mo
              </span>
            </div>
            <div className="w-full bg-navy-950 rounded-full h-2 overflow-hidden border border-navy-800">
              <div
                className="bg-amber-400 h-full transition-all duration-500"
                style={{ width: `${usage?.ai_queries.percentage}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Plan Comparison & Upgrade Tiers Grid */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Subscription Tiers & Plan Upgrades
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {plans.map((plan) => {
            const isCurrent = currentPlanTier.toLowerCase() === plan.tier.toLowerCase();
            const isUpgrading = upgradingTier === plan.tier;

            return (
              <div
                key={plan.tier}
                className={`p-6 rounded-2xl border flex flex-col justify-between transition-all ${
                  isCurrent
                    ? "bg-navy-900/90 border-cyan-500 shadow-xl shadow-cyan-950/40 relative"
                    : "bg-navy-900/50 border-navy-800 hover:border-navy-700 hover:bg-navy-900/80"
                }`}
              >
                <div>
                  {isCurrent && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase bg-cyan-500 text-black shadow">
                      Current Plan
                    </span>
                  )}

                  <div className="space-y-2">
                    <h3 className="text-lg font-bold text-white tracking-tight">
                      {plan.name}
                    </h3>
                    <p className="text-xs text-slate-400 line-clamp-2">
                      {plan.description}
                    </p>
                  </div>

                  <div className="mt-5 mb-6">
                    <div className="flex items-baseline space-x-1">
                      <span className="text-3xl font-extrabold text-white">
                        ${plan.price_monthly}
                      </span>
                      <span className="text-xs text-slate-400">/ month</span>
                    </div>
                  </div>

                  {/* Feature Checklist */}
                  <div className="space-y-2.5 text-xs text-slate-300 border-t border-navy-800 pt-5">
                    {plan.features.map((feat) => (
                      <div key={feat} className="flex items-start space-x-2">
                        <Check className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
                        <span>{feat}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="mt-8 pt-4 border-t border-navy-800/80">
                  {isCurrent ? (
                    <button
                      disabled
                      className="w-full py-2 bg-navy-800 text-slate-400 rounded-lg text-xs font-semibold cursor-default"
                    >
                      Active Plan
                    </button>
                  ) : (
                    <button
                      onClick={() => handleUpgrade(plan.tier)}
                      disabled={isUpgrading}
                      className="w-full py-2 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white rounded-lg text-xs font-bold shadow-md shadow-cyan-500/20 transition flex items-center justify-center space-x-1.5 disabled:opacity-50"
                    >
                      {isUpgrading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <Zap className="w-3.5 h-3.5" />
                      )}
                      <span>Switch to {plan.name}</span>
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Subscription Details & Cancellation Controls */}
      {subscription && subscription.plan_tier !== "free" && (
        <div className="p-6 bg-navy-900/60 border border-navy-800 rounded-xl flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-white">
              Subscription Renewal & Cycle
            </h3>
            <p className="text-xs text-slate-400">
              Current period started on {formatDate(subscription.current_period_start)} and will renew on{" "}
              {formatDate(subscription.current_period_end)}.
              {subscription.cancel_at_period_end && (
                <span className="text-rose-400 ml-1 font-semibold">
                  (Scheduled to cancel at end of period)
                </span>
              )}
            </p>
          </div>

          {!subscription.cancel_at_period_end && (
            <button
              onClick={handleCancelSubscription}
              className="px-4 py-2 bg-navy-950 hover:bg-rose-950/60 border border-rose-900/60 text-rose-400 hover:text-rose-300 text-xs font-semibold rounded-lg transition shrink-0"
            >
              Cancel Subscription
            </button>
          )}
        </div>
      )}

      {/* Invoices History Table */}
      <div className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400">
          Payment Invoices & Receipts
        </h2>

        {(!subscription?.invoices || subscription.invoices.length === 0) ? (
          <div className="p-8 text-center text-slate-500 bg-navy-900/40 border border-navy-800 rounded-xl">
            <CreditCard className="w-8 h-8 mx-auto mb-2 text-slate-600" />
            <p className="text-xs">No paid invoices found. Upgrades and renewals will be logged here.</p>
          </div>
        ) : (
          <div className="bg-navy-900/70 border border-navy-800 rounded-xl overflow-hidden">
            <table className="w-full text-left text-sm">
              <thead className="bg-navy-950/80 border-b border-navy-800 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="py-3 px-4">Invoice #</th>
                  <th className="py-3 px-4">Date</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4 text-right">Receipt</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-navy-800 text-xs">
                {subscription.invoices.map((inv) => (
                  <tr key={inv.id} className="hover:bg-navy-850/50 transition">
                    <td className="py-3.5 px-4 font-mono text-cyan-300">
                      {inv.invoice_number}
                    </td>
                    <td className="py-3.5 px-4 text-slate-400">
                      {formatDate(inv.created_at)}
                    </td>
                    <td className="py-3.5 px-4 font-bold text-white">
                      ${(inv.amount_cents / 100).toFixed(2)} {inv.currency}
                    </td>
                    <td className="py-3.5 px-4">
                      <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                        <Check className="w-3 h-3 mr-1" /> Paid
                      </span>
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <span className="text-slate-500 font-mono text-[11px] cursor-pointer hover:text-cyan-400">
                        Download PDF
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
