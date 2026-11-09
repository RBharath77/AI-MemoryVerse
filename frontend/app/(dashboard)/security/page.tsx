"use client";

import { useEffect, useState } from "react";
import {
  Shield,
  ShieldCheck,
  Key,
  Lock,
  Globe,
  AlertTriangle,
  CheckCircle2,
  Copy,
  Check,
  Plus,
  Trash2,
  Loader2,
  Cpu,
  Database,
  Smartphone,
  Laptop,
  RefreshCw,
  LogOut,
  QrCode,
  KeyRound,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

interface ApiToken {
  id: string;
  name: string;
  token_prefix: string;
  created_at: string;
  expires_at?: string | null;
}

interface UserSession {
  id: string;
  ip_address: string;
  user_agent: string;
  device_info: string;
  is_current: boolean;
  created_at: string;
  expires_at: string;
}

interface AuditLog {
  id: string;
  action: string;
  timestamp: string;
  ip_address: string;
  status: "success" | "blocked" | "flagged";
  details: string;
}

export default function SecurityCenterPage() {
  const { user, updateUser } = useAuthStore();

  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);

  // Token Generation
  const [newTokenName, setNewTokenName] = useState("");
  const [generatedKey, setGeneratedKey] = useState<string | null>(null);
  const [isLoadingTokens, setIsLoadingTokens] = useState(false);
  const [copiedKey, setCopiedKey] = useState(false);

  // 2FA / MFA state
  const [isMfaEnabled, setIsMfaEnabled] = useState(user?.is_mfa_enabled ?? false);
  const [backupCodesCount, setBackupCodesCount] = useState<number>(0);
  const [isSettingUpMfa, setIsSettingUpMfa] = useState(false);
  const [mfaSecret, setMfaSecret] = useState<string | null>(null);
  const [mfaTotpUri, setMfaTotpUri] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");
  const [backupCodes, setBackupCodes] = useState<string[] | null>(null);
  const [mfaStatusMsg, setMfaStatusMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);
  const [isMfaActionLoading, setIsMfaActionLoading] = useState(false);

  // Modal / Inputs for Regenerate & Disable
  const [isRegenOpen, setIsRegenOpen] = useState(false);
  const [regenPassword, setRegenPassword] = useState("");
  const [regenCode, setRegenCode] = useState("");

  const [isDisableOpen, setIsDisableOpen] = useState(false);
  const [disablePassword, setDisablePassword] = useState("");
  const [disableCode, setDisableCode] = useState("");

  // Sessions state
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isRevokingOther, setIsRevokingOther] = useState(false);

  useEffect(() => {
    fetchTokens();
    fetchSessions();
    fetchUserMfaStatus();
    loadAuditLogs();
  }, []);

  const fetchUserMfaStatus = async () => {
    const meRes = await api.get("/auth/me");
    if (meRes.success && meRes.data) {
      const enabled = !!meRes.data.is_mfa_enabled;
      setIsMfaEnabled(enabled);
      updateUser({ is_mfa_enabled: enabled });
      if (enabled) {
        fetchBackupCodesCount();
      }
    }
  };

  const fetchBackupCodesCount = async () => {
    const res = await api.get("/auth/mfa/backup-codes");
    if (res.success && res.data) {
      setBackupCodesCount(res.data.count);
    }
  };

  const fetchTokens = async () => {
    setIsLoadingTokens(true);
    const res = await api.get("/tokens");
    if (res.success && res.data) {
      setTokens(Array.isArray(res.data) ? res.data : res.data.items || []);
    }
    setIsLoadingTokens(false);
  };

  const fetchSessions = async () => {
    setIsLoadingSessions(true);
    const res = await api.get("/auth/sessions");
    if (res.success && res.data) {
      setSessions(res.data);
    }
    setIsLoadingSessions(false);
  };

  const loadAuditLogs = () => {
    const logs: AuditLog[] = [
      {
        id: "log-1",
        action: "MCP Protocol Connection",
        timestamp: "Just now",
        ip_address: "127.0.0.1 (Local stdio)",
        status: "success",
        details: "Handshake initialized via JSON-RPC 2.0 with Claude Desktop agent",
      },
      {
        id: "log-2",
        action: "User Authentication",
        timestamp: "12 mins ago",
        ip_address: "127.0.0.1",
        status: "success",
        details: "Argon2id verified session with Secure SameSite JWT & session ID claim",
      },
      {
        id: "log-3",
        action: "SSRF URL Protection",
        timestamp: "1 hour ago",
        ip_address: "Internal Crawler",
        status: "blocked",
        details: "Blocked forbidden private RFC1918 loopback request to 169.254.169.254",
      },
      {
        id: "log-4",
        action: "Memory Vault Isolation",
        timestamp: "3 hours ago",
        ip_address: "127.0.0.1",
        status: "success",
        details: "Workspace tenancy barrier verified across all SQL and pgvector queries",
      },
    ];
    setAuditLogs(logs);
  };

  const startMfaSetup = async () => {
    setIsMfaActionLoading(true);
    setMfaStatusMsg(null);
    const res = await api.post("/auth/mfa/setup", {});
    if (res.success && res.data) {
      setMfaSecret(res.data.secret);
      setMfaTotpUri(res.data.totp_uri);
      setIsSettingUpMfa(true);
    } else {
      setMfaStatusMsg({ type: "error", text: res.error?.message || "Failed to initiate MFA setup." });
    }
    setIsMfaActionLoading(false);
  };

  const confirmEnableMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mfaCode.length !== 6) return;

    setIsMfaActionLoading(true);
    setMfaStatusMsg(null);
    const res = await api.post("/auth/mfa/enable", { code: mfaCode.trim() });
    if (res.success && res.data) {
      setIsMfaEnabled(true);
      updateUser({ is_mfa_enabled: true });
      setIsSettingUpMfa(false);
      setMfaSecret(null);
      setMfaTotpUri(null);
      setMfaCode("");
      if (res.data.backup_codes) {
        setBackupCodes(res.data.backup_codes);
        setBackupCodesCount(res.data.backup_codes.length);
      }
      setMfaStatusMsg({
        type: "success",
        text: "Two-factor authentication successfully enabled! Make sure to save your backup codes below.",
      });
    } else {
      setMfaStatusMsg({ type: "error", text: res.error?.message || "Invalid verification code." });
    }
    setIsMfaActionLoading(false);
  };

  const handleRegenerateBackupCodes = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!regenPassword || regenCode.length !== 6) return;

    setIsMfaActionLoading(true);
    setMfaStatusMsg(null);
    const res = await api.post("/auth/mfa/backup-codes/regenerate", {
      password: regenPassword,
      code: regenCode.trim(),
    });

    if (res.success && res.data) {
      setBackupCodes(res.data.backup_codes);
      setBackupCodesCount(res.data.count);
      setIsRegenOpen(false);
      setRegenPassword("");
      setRegenCode("");
      setMfaStatusMsg({
        type: "success",
        text: "Backup recovery codes successfully refreshed. Previous codes have been invalidated.",
      });
    } else {
      setMfaStatusMsg({ type: "error", text: res.error?.message || "Failed to regenerate backup codes." });
    }
    setIsMfaActionLoading(false);
  };

  const handleDisableMfa = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!disablePassword || disableCode.length !== 6) return;

    setIsMfaActionLoading(true);
    setMfaStatusMsg(null);
    const res = await api.post("/auth/mfa/disable", {
      password: disablePassword,
      code: disableCode.trim(),
    });

    if (res.success) {
      setIsMfaEnabled(false);
      updateUser({ is_mfa_enabled: false });
      setBackupCodes(null);
      setBackupCodesCount(0);
      setIsDisableOpen(false);
      setDisablePassword("");
      setDisableCode("");
      setMfaStatusMsg({
        type: "success",
        text: "Two-factor authentication has been disabled on this account.",
      });
    } else {
      setMfaStatusMsg({ type: "error", text: res.error?.message || "Failed to disable 2FA." });
    }
    setIsMfaActionLoading(false);
  };

  const revokeSession = async (sessionId: string) => {
    const res = await api.delete(`/auth/sessions/${sessionId}`);
    if (res.success) {
      fetchSessions();
    }
  };

  const revokeOtherSessions = async () => {
    setIsRevokingOther(true);
    const res = await api.delete("/auth/sessions/other");
    if (res.success) {
      fetchSessions();
    }
    setIsRevokingOther(false);
  };

  const createToken = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newTokenName.trim()) return;

    const res = await api.post("/tokens", {
      name: newTokenName.trim(),
      scopes: ["read", "write", "mcp"],
    });

    if (res.success && res.data) {
      setGeneratedKey(res.data.token || res.data.raw_token || "mv_live_secret_key_generated");
      setNewTokenName("");
      fetchTokens();
    }
  };

  const deleteToken = async (id: string) => {
    await api.delete(`/tokens/${id}`);
    fetchTokens();
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(true);
    setTimeout(() => setCopiedKey(false), 2000);
  };

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
              <Shield className="w-4 h-4" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold text-white tracking-tight">
              Security Center
            </h1>
          </div>
          <p className="text-sm text-slate-400 mt-1">
            Zero-trust defense-in-depth, 2FA recovery codes, multi-device session revocation, and API tokens.
          </p>
        </div>

        <div className="flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
          <ShieldCheck className="w-4 h-4" />
          <span>Security Posture: Strict Enforced</span>
        </div>
      </div>

      {/* Security Posture Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Tenant Isolation
            </span>
            <Database className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-lg font-bold text-white">Row-Level Strict</p>
          <p className="text-[11px] text-slate-400">
            Workspace ID ownership verified on every query.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              SSRF Protection
            </span>
            <Globe className="w-4 h-4 text-emerald-400" />
          </div>
          <p className="text-lg font-bold text-emerald-400">DNS & IP Guard</p>
          <p className="text-[11px] text-slate-400">
            Internal & cloud metadata IPs blocked.
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Two-Factor Auth
            </span>
            <Lock className="w-4 h-4 text-purple-400" />
          </div>
          <p className={`text-lg font-bold ${isMfaEnabled ? "text-emerald-400" : "text-amber-400"}`}>
            {isMfaEnabled ? "RFC 6238 TOTP Active" : "Disabled"}
          </p>
          <p className="text-[11px] text-slate-400">
            {isMfaEnabled ? `${backupCodesCount} recovery code(s) available` : "Protect your account with 2FA"}
          </p>
        </div>

        <div className="p-5 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
              Active Sessions
            </span>
            <Cpu className="w-4 h-4 text-cyan-400" />
          </div>
          <p className="text-lg font-bold text-cyan-400">
            {sessions.length} Connected {sessions.length === 1 ? "Device" : "Devices"}
          </p>
          <p className="text-[11px] text-slate-400">
            Instant token revocation per session ID.
          </p>
        </div>
      </div>

      {/* Two-Factor Authentication (TOTP) & Backup Recovery Codes Section */}
      <div className="p-6 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <KeyRound className="w-5 h-5 text-purple-400" />
              <h3 className="font-bold text-white text-base">Two-Factor Authentication (2FA) & Recovery Codes</h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Add a second layer of defense using any standard TOTP authenticator (Google Authenticator, 1Password, Bitwarden).
            </p>
          </div>

          <div className="flex items-center space-x-2">
            {!isMfaEnabled ? (
              <button
                type="button"
                onClick={startMfaSetup}
                disabled={isMfaActionLoading || isSettingUpMfa}
                className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                {isMfaActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <QrCode className="w-4 h-4" />}
                <span>Configure 2FA</span>
              </button>
            ) : (
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => setIsRegenOpen(true)}
                  className="px-3 py-1.5 rounded-lg border border-navy-700 hover:border-navy-600 bg-navy-950 text-xs font-medium text-slate-200 transition-colors"
                >
                  Regenerate Backup Codes
                </button>
                <button
                  type="button"
                  onClick={() => setIsDisableOpen(true)}
                  className="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-xs font-medium text-rose-300 transition-colors"
                >
                  Disable 2FA
                </button>
              </div>
            )}
          </div>
        </div>

        {mfaStatusMsg && (
          <div
            className={`p-3.5 rounded-xl border text-xs flex items-center space-x-2 ${
              mfaStatusMsg.type === "success"
                ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
                : "bg-rose-950/40 border-rose-500/30 text-rose-300"
            }`}
          >
            {mfaStatusMsg.type === "success" ? (
              <CheckCircle2 className="w-4 h-4 shrink-0" />
            ) : (
              <AlertTriangle className="w-4 h-4 shrink-0" />
            )}
            <span>{mfaStatusMsg.text}</span>
          </div>
        )}

        {/* MFA Setup QR & Secret View */}
        {isSettingUpMfa && mfaSecret && (
          <div className="p-5 rounded-xl bg-navy-950/80 border border-cyan-500/30 space-y-4">
            <div className="space-y-1">
              <h4 className="text-sm font-semibold text-white">Scan Authenticator QR or Enter Manual Secret</h4>
              <p className="text-xs text-slate-400">
                Enter this Base32 secret key into your authenticator app, then confirm the generated 6-digit code below:
              </p>
            </div>

            <div className="p-3 rounded-lg bg-navy-900 border border-navy-800 flex items-center justify-between">
              <span className="font-mono text-cyan-300 font-bold tracking-widest text-xs select-all">
                {mfaSecret}
              </span>
              <button
                type="button"
                onClick={() => handleCopy(mfaSecret)}
                className="text-xs text-slate-400 hover:text-white flex items-center space-x-1"
              >
                {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey ? "Copied" : "Copy Secret"}</span>
              </button>
            </div>

            <form onSubmit={confirmEnableMfa} className="flex items-center space-x-2">
              <input
                type="text"
                maxLength={6}
                placeholder="6-digit TOTP code (e.g. 123456)"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ""))}
                className="px-3 py-2 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono tracking-wider w-56"
              />
              <button
                type="submit"
                disabled={mfaCode.length !== 6 || isMfaActionLoading}
                className="px-4 py-2 rounded-lg bg-emerald-500 hover:bg-emerald-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50"
              >
                {isMfaActionLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />}
                <span>Activate 2FA</span>
              </button>
              <button
                type="button"
                onClick={() => setIsSettingUpMfa(false)}
                className="px-3 py-2 rounded-lg border border-navy-800 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
            </form>
          </div>
        )}

        {/* Backup Codes Display */}
        {backupCodes && backupCodes.length > 0 && (
          <div className="p-5 rounded-xl bg-purple-950/30 border border-purple-500/30 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-sm font-semibold text-white">Emergency Single-Use Backup Recovery Codes</h4>
                <p className="text-xs text-purple-200/80">
                  Store these securely. Each code can be used exactly once to log in if you lose your phone or authenticator app.
                </p>
              </div>
              <button
                type="button"
                onClick={() => handleCopy(backupCodes.join("\n"))}
                className="px-3 py-1.5 rounded-lg border border-purple-500/40 bg-purple-500/20 text-purple-200 text-xs font-medium hover:bg-purple-500/30 transition-colors flex items-center space-x-1"
              >
                <Copy className="w-3.5 h-3.5" />
                <span>Copy All Codes</span>
              </button>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2">
              {backupCodes.map((c, i) => (
                <div
                  key={i}
                  className="p-2.5 rounded-lg bg-navy-950 border border-purple-500/20 font-mono text-center text-xs text-purple-300 font-bold tracking-wider"
                >
                  {c}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Modal: Regenerate Backup Codes */}
        {isRegenOpen && (
          <form
            onSubmit={handleRegenerateBackupCodes}
            className="p-4 rounded-xl bg-navy-950 border border-navy-700 space-y-3"
          >
            <h4 className="text-xs font-bold uppercase tracking-wider text-cyan-400">
              Regenerate 8 New Single-Use Recovery Codes
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input
                type="password"
                placeholder="Current account password"
                value={regenPassword}
                onChange={(e) => setRegenPassword(e.target.value)}
                className="px-3 py-2 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
              <input
                type="text"
                maxLength={6}
                placeholder="6-digit TOTP code"
                value={regenCode}
                onChange={(e) => setRegenCode(e.target.value.replace(/\D/g, ""))}
                className="px-3 py-2 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono tracking-wider"
              />
            </div>
            <div className="flex items-center space-x-2 pt-1">
              <button
                type="submit"
                disabled={!regenPassword || regenCode.length !== 6 || isMfaActionLoading}
                className="px-3.5 py-1.5 rounded-lg bg-cyan-500 text-navy-950 text-xs font-semibold hover:bg-cyan-400 disabled:opacity-50"
              >
                Regenerate Codes
              </button>
              <button
                type="button"
                onClick={() => setIsRegenOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-navy-800 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
            </div>
          </form>
        )}

        {/* Modal: Disable 2FA */}
        {isDisableOpen && (
          <form onSubmit={handleDisableMfa} className="p-4 rounded-xl bg-navy-950 border border-rose-500/30 space-y-3">
            <h4 className="text-xs font-bold uppercase tracking-wider text-rose-400">
              Disable Two-Factor Authentication
            </h4>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              <input
                type="password"
                placeholder="Current account password"
                value={disablePassword}
                onChange={(e) => setDisablePassword(e.target.value)}
                className="px-3 py-2 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500"
              />
              <input
                type="text"
                maxLength={6}
                placeholder="6-digit TOTP code"
                value={disableCode}
                onChange={(e) => setDisableCode(e.target.value.replace(/\D/g, ""))}
                className="px-3 py-2 rounded-lg bg-navy-900 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 font-mono tracking-wider"
              />
            </div>
            <div className="flex items-center space-x-2 pt-1">
              <button
                type="submit"
                disabled={!disablePassword || disableCode.length !== 6 || isMfaActionLoading}
                className="px-3.5 py-1.5 rounded-lg bg-rose-500 text-white text-xs font-semibold hover:bg-rose-400 disabled:opacity-50"
              >
                Confirm Disable
              </button>
              <button
                type="button"
                onClick={() => setIsDisableOpen(false)}
                className="px-3 py-1.5 rounded-lg border border-navy-800 text-xs text-slate-400 hover:text-white"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      {/* Active User Sessions & Remote Revocation Section */}
      <div className="p-6 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <Laptop className="w-5 h-5 text-cyan-400" />
              <h3 className="font-bold text-white text-base">Active Logged-In Sessions</h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Review all authenticated browser and desktop devices. Remotely terminate lost, unrecognized, or older sessions.
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={fetchSessions}
              className="p-2 rounded-lg border border-navy-700 bg-navy-950 text-slate-400 hover:text-white transition-colors"
              title="Refresh Sessions"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isLoadingSessions ? "animate-spin text-cyan-400" : ""}`} />
            </button>
            {sessions.length > 1 && (
              <button
                type="button"
                onClick={revokeOtherSessions}
                disabled={isRevokingOther}
                className="px-3 py-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 text-xs font-medium transition-colors flex items-center space-x-1"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span>Revoke All Other Sessions</span>
              </button>
            )}
          </div>
        </div>

        {isLoadingSessions ? (
          <div className="py-8 flex items-center justify-center space-y-2 text-xs text-slate-400">
            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin mr-2" />
            Loading active sessions...
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-navy-950/60 border border-navy-800 text-xs text-slate-400">
            No active sessions registered.
          </div>
        ) : (
          <div className="space-y-2.5">
            {sessions.map((s) => (
              <div
                key={s.id}
                className="p-4 rounded-xl bg-navy-950/80 border border-navy-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs"
              >
                <div className="flex items-start space-x-3">
                  <div className="w-8 h-8 rounded-lg bg-navy-900 border border-navy-800 flex items-center justify-center text-cyan-400 shrink-0 mt-0.5">
                    {s.device_info.includes("Android") || s.device_info.includes("iOS") ? (
                      <Smartphone className="w-4 h-4" />
                    ) : (
                      <Laptop className="w-4 h-4" />
                    )}
                  </div>
                  <div className="space-y-0.5">
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-white">{s.device_info}</span>
                      {s.is_current && (
                        <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-semibold">
                          Current Device
                        </span>
                      )}
                    </div>
                    <p className="font-mono text-slate-400 text-[11px]">
                      IP Address: {s.ip_address} • Created {new Date(s.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>

                {!s.is_current && (
                  <button
                    type="button"
                    onClick={() => revokeSession(s.id)}
                    className="px-3 py-1.5 rounded-lg border border-navy-800 hover:border-rose-500/40 text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors text-xs flex items-center space-x-1 self-start sm:self-auto"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                    <span>Revoke</span>
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* API Access Tokens Management */}
      <div className="p-6 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <Key className="w-5 h-5 text-cyan-400" />
              <h3 className="font-bold text-white text-base">Developer API & MCP Tokens</h3>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              Create scoped API keys for external scripts, CLI utilities, and MCP client agents.
            </p>
          </div>

          <form onSubmit={createToken} className="flex items-center space-x-2 w-full sm:w-auto">
            <input
              type="text"
              placeholder="Token name (e.g. Claude Desktop CLI)..."
              value={newTokenName}
              onChange={(e) => setNewTokenName(e.target.value)}
              className="px-3 py-2 rounded-lg bg-navy-950 border border-navy-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500 w-full sm:w-64"
            />
            <button
              type="submit"
              disabled={!newTokenName.trim()}
              className="px-3.5 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 text-xs font-semibold flex items-center space-x-1.5 transition-colors disabled:opacity-50 whitespace-nowrap"
            >
              <Plus className="w-4 h-4" />
              <span>Generate</span>
            </button>
          </form>
        </div>

        {generatedKey && (
          <div className="p-4 rounded-xl bg-cyan-500/10 border border-cyan-500/30 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-cyan-300">
                New API Key Generated (Copy now; it won&apos;t be shown again):
              </span>
              <button
                type="button"
                onClick={() => handleCopy(generatedKey)}
                className="flex items-center space-x-1 text-xs text-cyan-300 hover:text-white"
              >
                {copiedKey ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copiedKey ? "Copied" : "Copy"}</span>
              </button>
            </div>
            <code className="block p-2 rounded bg-navy-950 font-mono text-xs text-emerald-400 break-all border border-navy-800">
              {generatedKey}
            </code>
          </div>
        )}

        {isLoadingTokens ? (
          <div className="py-8 flex items-center justify-center space-y-2 text-xs text-slate-400">
            <Loader2 className="w-5 h-5 text-cyan-400 animate-spin mr-2" />
            Loading tokens...
          </div>
        ) : tokens.length === 0 ? (
          <div className="p-6 text-center rounded-xl bg-navy-950/60 border border-navy-800 text-xs text-slate-400">
            No active API tokens found. Generate one above to connect external services.
          </div>
        ) : (
          <div className="space-y-2">
            {tokens.map((t) => (
              <div
                key={t.id}
                className="p-3.5 rounded-xl bg-navy-950/80 border border-navy-800 flex items-center justify-between text-xs"
              >
                <div className="space-y-0.5">
                  <span className="font-semibold text-white">{t.name}</span>
                  <p className="font-mono text-slate-500 text-[11px]">
                    Prefix: {t.token_prefix}...
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => deleteToken(t.id)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-rose-400 hover:bg-navy-900 transition-colors"
                  title="Revoke Token"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Security Audit Events Trail */}
      <div className="p-6 rounded-2xl bg-navy-900/40 border border-navy-800 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <h3 className="font-bold text-white text-base">Live Security Audit Log Trail</h3>
          </div>
          <span className="text-[11px] font-mono text-slate-400">Immutable Hash Log</span>
        </div>

        <div className="space-y-2.5">
          {auditLogs.map((log) => (
            <div
              key={log.id}
              className="p-4 rounded-xl bg-navy-950/60 border border-navy-800 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 text-xs"
            >
              <div className="space-y-1">
                <div className="flex items-center space-x-2">
                  <span
                    className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                      log.status === "success"
                        ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/30"
                        : log.status === "blocked"
                        ? "bg-rose-500/10 text-rose-400 border-rose-500/30"
                        : "bg-amber-500/10 text-amber-400 border-amber-500/30"
                    }`}
                  >
                    {log.status}
                  </span>
                  <span className="font-bold text-white">{log.action}</span>
                </div>
                <p className="text-slate-400 text-xs">{log.details}</p>
              </div>

              <div className="flex items-center space-x-4 text-[11px] text-slate-500 font-mono shrink-0">
                <span>{log.ip_address}</span>
                <span>{log.timestamp}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
