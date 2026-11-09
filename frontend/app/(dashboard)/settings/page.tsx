"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Settings,
  User,
  Brain,
  Shield,
  Download,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  Lock,
  Palette,
  Sun,
  Moon,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";
import { useThemeStore } from "@/store/theme-store";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { BrainLoader } from "@/components/ui/brain-loader";

export default function SettingsPage() {
  const router = useRouter();
  const { user, updateUser, logout } = useAuthStore();

  const [activeTab, setActiveTab] = useState<"profile" | "ai" | "appearance" | "privacy">("profile");
  const { theme, setTheme } = useThemeStore();

  // Profile Form state
  const [fullName, setFullName] = useState(user?.full_name || "");
  const [bio, setBio] = useState(user?.profile?.bio || "");
  const [aiInstructions, setAiInstructions] = useState(
    user?.profile?.ai_custom_instructions ||
      "Be concise, source-grounded, and maintain persistent memory context."
  );

  const [isSaving, setIsSaving] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Deletion modal state
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Live Brain Loader preview state
  const [previewLoaderTheme, setPreviewLoaderTheme] = useState<"dark" | "light" | null>(null);
  const [showEmbeddedLoader, setShowEmbeddedLoader] = useState(false);

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSaving(true);
    setSuccessMessage(null);
    setErrorMessage(null);

    const res = await api.patch("/users/me", {
      full_name: fullName,
      profile: {
        bio,
        ai_custom_instructions: aiInstructions,
      },
    });

    if (res.success && res.data) {
      updateUser({
        full_name: fullName,
        profile: {
          bio,
          avatar_url: res.data.profile?.avatar_url || "",
          ai_custom_instructions: aiInstructions,
          preferences: res.data.profile?.preferences || {},
        },
      });
      setSuccessMessage("Settings updated successfully!");
      setTimeout(() => setSuccessMessage(null), 3000);
    } else {
      setErrorMessage(res.error?.message || "Failed to update profile.");
    }
    setIsSaving(false);
  };

  const handleExportData = async () => {
    // Collect memories and user data for export
    const memRes = await api.get("/memories?page_size=100");
    const exportData = {
      export_date: new Date().toISOString(),
      user: {
        id: user?.id,
        email: user?.email,
        full_name: user?.full_name,
      },
      memories: memRes.data?.items || [],
    };

    const dataStr =
      "data:text/json;charset=utf-8," +
      encodeURIComponent(JSON.stringify(exportData, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute(
      "download",
      `memoryverse-export-${new Date().toISOString().split("T")[0]}.json`
    );
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  const handleDeleteAccount = async () => {
    setIsDeleting(true);
    const res = await api.delete("/users/me");
    if (res.success) {
      logout();
      router.push("/");
    } else {
      setErrorMessage(res.error?.message || "Failed to delete account.");
      setIsDeleting(false);
      setIsDeleteModalOpen(false);
    }
  };

  return (
    <>
      {previewLoaderTheme && (
        <BrainLoader
          variant="fullscreen"
          theme={previewLoaderTheme}
          showThemeToggle={true}
          showReplay={true}
          autoDismiss={false}
          onDismiss={() => setPreviewLoaderTheme(null)}
          onComplete={() => {}}
          clickToDismiss={true}
        />
      )}

      <div className="p-6 sm:p-8 max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="pb-6 border-b border-navy-800">
        <div className="flex items-center space-x-2">
          <Settings className="w-6 h-6 text-cyan-400" />
          <h1 className="text-2xl font-extrabold text-white tracking-tight">
            Settings & Preferences
          </h1>
        </div>
        <p className="text-xs sm:text-sm text-slate-400 mt-1">
          Manage your personal external brain profile, AI instructions, and data privacy.
        </p>
      </div>

      {successMessage && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/40 text-emerald-300 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{successMessage}</span>
        </div>
      )}

      {errorMessage && (
        <div className="p-4 rounded-xl border border-red-500/30 bg-red-950/40 text-red-300 text-xs flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* Tabs */}
      <div className="flex items-center space-x-2 border-b border-navy-800">
        <button
          onClick={() => setActiveTab("profile")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
            activeTab === "profile"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <User className="w-4 h-4" />
          <span>Profile</span>
        </button>

        <button
          onClick={() => setActiveTab("ai")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
            activeTab === "ai"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Brain className="w-4 h-4" />
          <span>AI Personality</span>
        </button>

        <button
          onClick={() => setActiveTab("appearance")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
            activeTab === "appearance"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Palette className="w-4 h-4" />
          <span>Theme & Palette</span>
        </button>

        <button
          onClick={() => setActiveTab("privacy")}
          className={`px-4 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center space-x-2 ${
            activeTab === "privacy"
              ? "border-cyan-400 text-cyan-400"
              : "border-transparent text-slate-400 hover:text-white"
          }`}
        >
          <Shield className="w-4 h-4" />
          <span>Privacy & GDPR</span>
        </button>
      </div>

      {/* Profile Tab */}
      {activeTab === "profile" && (
        <form onSubmit={handleSaveProfile} className="space-y-5 bg-navy-900/40 p-6 rounded-2xl border border-navy-800">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Full Name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              className="w-full p-2.5 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Email Address
            </label>
            <input
              type="email"
              disabled
              value={user?.email || ""}
              className="w-full p-2.5 bg-navy-950/50 border border-navy-800 rounded-lg text-xs text-slate-500 cursor-not-allowed"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Personal Bio / Role
            </label>
            <textarea
              rows={3}
              value={bio}
              onChange={(e) => setBio(e.target.value)}
              placeholder="e.g. Principal AI Software Architect"
              className="w-full p-2.5 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            <span>Save Profile</span>
          </button>
        </form>
      )}

      {/* AI Personality Tab */}
      {activeTab === "ai" && (
        <form onSubmit={handleSaveProfile} className="space-y-5 bg-navy-900/40 p-6 rounded-2xl border border-navy-800">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Persistent AI Custom Instructions
            </label>
            <p className="text-xs text-slate-400 mb-2">
              These guidelines are injected into the context of every AI conversation and RAG generation.
            </p>
            <textarea
              rows={5}
              value={aiInstructions}
              onChange={(e) => setAiInstructions(e.target.value)}
              placeholder="e.g. Be concise, verify citations against retrieved chunks, write clean PEP 8 Python."
              className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
            />
          </div>

          <button
            type="submit"
            disabled={isSaving}
            className="px-4 py-2 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-semibold text-xs transition-colors flex items-center space-x-2 disabled:opacity-50"
          >
            {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
            <span>Save AI Instructions</span>
          </button>
        </form>
      )}

      {/* Appearance & Theme Tab */}
      {activeTab === "appearance" && (
        <div className="space-y-6">
          <div className="p-6 bg-navy-900/40 border border-navy-800 rounded-2xl space-y-5">
            <div>
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Palette className="w-4 h-4 text-cyan-400" />
                <span>Interface Theme & Palette</span>
              </h3>
              <p className="text-xs text-slate-400 mt-1">
                Choose between Light (Warm Alabaster) and Dark (Nocturne Indigo) mode with our signature 4-tone palette.
              </p>
            </div>

            {/* Quick Toggle Component */}
            <div className="p-4 rounded-xl bg-navy-950 border border-navy-800 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-xs font-semibold text-white">Active Theme Mode</p>
                <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                  Currently running: <span className="text-cyan-400 font-bold uppercase">{theme} MODE</span>
                </p>
              </div>
              <ThemeToggle variant="pill" showLabels={true} />
            </div>

            {/* Theme Mode Cards */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              {/* Light Mode Card */}
              <div
                onClick={() => setTheme("light")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  theme === "light"
                    ? "border-[#014BAA] ring-2 ring-[#014BAA]/40 bg-[#F8F3F0]/90 text-[#282B4A]"
                    : "border-navy-800 bg-navy-950/60 hover:border-slate-700 text-slate-300"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <Sun className="w-4 h-4 text-amber-500" />
                    <span className="text-xs font-bold">Light (Warm Alabaster)</span>
                  </div>
                  {theme === "light" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#014BAA] text-white">
                      Active
                    </span>
                  )}
                </div>
                <div className="p-3 rounded-lg bg-[#F8F3F0] border border-[#EEEBDA] text-[#282B4A] space-y-1.5 shadow-sm">
                  <div className="h-2 w-20 rounded bg-[#014BAA]" />
                  <p className="text-[11px] font-semibold text-[#282B4A]">Editorial Clarity</p>
                  <p className="text-[10px] text-[#5A5D7A]">Canvas: #F8F3F0 • Cards: White • Text: #282B4A</p>
                </div>
              </div>

              {/* Dark Mode Card */}
              <div
                onClick={() => setTheme("dark")}
                className={`p-4 rounded-xl border cursor-pointer transition-all ${
                  theme === "dark"
                    ? "border-[#014BAA] ring-2 ring-[#014BAA]/40 bg-[#282B4A]/90 text-white"
                    : "border-navy-800 bg-navy-950/60 hover:border-slate-700 text-slate-300"
                }`}
              >
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <Moon className="w-4 h-4 text-cyan-400" />
                    <span className="text-xs font-bold">Dark (Nocturne Indigo)</span>
                  </div>
                  {theme === "dark" && (
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#014BAA] text-white">
                      Active
                    </span>
                  )}
                </div>
                <div className="p-3 rounded-lg bg-[#282B4A] border border-indigo-500/20 text-white space-y-1.5 shadow-sm">
                  <div className="h-2 w-20 rounded bg-[#014BAA]" />
                  <p className="text-[11px] font-semibold text-[#F8F3F0]">Deep Twilight Contrast</p>
                  <p className="text-[10px] text-[#EEEBDA]">Canvas: #181A2C • Surface: #282B4A • Text: #F8F3F0</p>
                </div>
              </div>
            </div>

            {/* Signature Color Swatches */}
            <div className="pt-3 border-t border-navy-800">
              <p className="text-xs font-bold text-white mb-2">Palette Specification</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center space-x-2.5">
                  <div className="w-6 h-6 rounded-md shadow-inner" style={{ backgroundColor: "#014BAA" }} />
                  <div>
                    <p className="text-[11px] font-bold text-white">#014BAA</p>
                    <p className="text-[9px] text-slate-400">Cobalt Accent</p>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center space-x-2.5">
                  <div className="w-6 h-6 rounded-md border border-black/10 shadow-inner" style={{ backgroundColor: "#F8F3F0" }} />
                  <div>
                    <p className="text-[11px] font-bold text-white">#F8F3F0</p>
                    <p className="text-[9px] text-slate-400">Alabaster White</p>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center space-x-2.5">
                  <div className="w-6 h-6 rounded-md shadow-inner" style={{ backgroundColor: "#282B4A" }} />
                  <div>
                    <p className="text-[11px] font-bold text-white">#282B4A</p>
                    <p className="text-[9px] text-slate-400">Nocturne Indigo</p>
                  </div>
                </div>

                <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 flex items-center space-x-2.5">
                  <div className="w-6 h-6 rounded-md border border-black/10 shadow-inner" style={{ backgroundColor: "#EEEBDA" }} />
                  <div>
                    <p className="text-[11px] font-bold text-white">#EEEBDA</p>
                    <p className="text-[9px] text-slate-400">Warm Linen</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Live Real Neural Brain Loader Showcase */}
            <div className="pt-4 border-t border-navy-800 space-y-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div>
                  <h4 className="text-xs font-bold text-white flex items-center space-x-2">
                    <Brain className="w-4 h-4 text-pink-400" />
                    <span>Real Neural Brain Loader (Dual-Theme Live Showcase)</span>
                  </h4>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Experience the photorealistic 3D cortical synaptic loader adapted for Dark & Light modes.
                  </p>
                </div>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPreviewLoaderTheme("dark")}
                    className="px-3 py-1.5 rounded-lg bg-indigo-950/80 hover:bg-indigo-900 text-pink-300 border border-pink-500/30 text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition-all active:scale-95"
                  >
                    <Moon className="w-3.5 h-3.5 text-pink-400" />
                    <span>Preview Dark Theme</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setPreviewLoaderTheme("light")}
                    className="px-3 py-1.5 rounded-lg bg-[#EEEBDA] hover:bg-[#F8F3F0] text-[#014BAA] border border-[#014BAA]/30 text-xs font-semibold flex items-center space-x-1.5 shadow-sm transition-all active:scale-95"
                  >
                    <Sun className="w-3.5 h-3.5 text-amber-600" />
                    <span>Preview Light Theme</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setShowEmbeddedLoader(!showEmbeddedLoader)}
                    className="px-3 py-1.5 rounded-lg bg-navy-800 hover:bg-navy-700 text-cyan-300 border border-cyan-500/30 text-xs font-semibold flex items-center space-x-1.5 transition-all"
                  >
                    <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
                    <span>{showEmbeddedLoader ? "Hide Live Canvas" : "Show Embedded Canvas"}</span>
                  </button>
                </div>
              </div>

              {showEmbeddedLoader && (
                <div className="mt-4 pt-2">
                  <BrainLoader
                    variant="embedded"
                    theme={theme === "light" ? "light" : "dark"}
                    showThemeToggle={true}
                    showReplay={true}
                    autoDismiss={false}
                  />
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Privacy Tab */}
      {activeTab === "privacy" && (
        <div className="space-y-6">
          {/* Data Export */}
          <div className="p-6 bg-navy-900/40 border border-navy-800 rounded-2xl space-y-3">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Download className="w-4 h-4 text-cyan-400" />
              <span>Export Personal Knowledge Data</span>
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Download a complete JSON export of all your stored memories, tags, categories, and account metadata.
            </p>
            <button
              onClick={handleExportData}
              className="px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-700 text-slate-200 text-xs font-semibold flex items-center space-x-2 transition-colors border border-navy-700"
            >
              <Download className="w-4 h-4" />
              <span>Download JSON Archive</span>
            </button>
          </div>

          {/* Account Deletion */}
          <div className="p-6 bg-red-950/20 border border-red-500/30 rounded-2xl space-y-3">
            <h3 className="text-sm font-bold text-red-400 flex items-center space-x-2">
              <Trash2 className="w-4 h-4 text-red-400" />
              <span>Permanent Account & Data Deletion</span>
            </h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Permanently delete your user profile, active workspaces, long-term memories, and uploaded document chunks. This action cannot be undone.
            </p>
            <button
              onClick={() => setIsDeleteModalOpen(true)}
              className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-semibold flex items-center space-x-2 transition-colors"
            >
              <Trash2 className="w-4 h-4" />
              <span>Delete Account Permanently</span>
            </button>
          </div>
        </div>
      )}

      {/* Deletion Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm">
          <div className="bg-navy-900 border border-red-500/40 rounded-2xl w-full max-w-md p-6 shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-red-400">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="text-base font-bold">Are you absolutely sure?</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              This will irreversibly purge your account, memory vault, and documents across all connected databases.
            </p>
            <div className="flex items-center justify-end space-x-3 pt-4 border-t border-navy-800">
              <button
                type="button"
                onClick={() => setIsDeleteModalOpen(false)}
                className="px-4 py-2 rounded-lg bg-navy-800 text-slate-300 text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteAccount}
                disabled={isDeleting}
                className="px-4 py-2 rounded-lg bg-red-600 hover:bg-red-500 text-white text-xs font-bold transition-colors disabled:opacity-50"
              >
                {isDeleting ? "Purging data..." : "Yes, Purge My Data"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
    </>
  );
}

