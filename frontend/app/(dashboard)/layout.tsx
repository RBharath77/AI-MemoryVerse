"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Brain,
  MessageSquare,
  Vault,
  Inbox,
  FileText,
  Search,
  GitFork,
  Clock,
  FolderOpen,
  LineChart,
  Mic,
  BookOpen,
  FileBarChart,
  Blocks,
  Bot,
  Shield,
  Settings,
  ShieldAlert,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Cpu,
} from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { api } from "@/lib/api";
import { AnimatedLoader } from "@/components/ui/animated-loader";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { Logo } from "@/components/ui/logo";

interface Workspace {
  id: string;
  name: string;
  slug: string;
  plan_tier: string;
}

const navSections = [
  {
    title: "Knowledge & Memory",
    items: [
      { name: "Overview", href: "/dashboard", icon: LineChart },
      { name: "Memory Vault", href: "/memories", icon: Vault },
      { name: "Review Inbox", href: "/memory-review", icon: Inbox },
      { name: "Document Library", href: "/documents", icon: FileText },
      { name: "Knowledge Graph", href: "/graph", icon: GitFork },
      { name: "Memory Timeline", href: "/timeline", icon: Clock },
      { name: "Collections", href: "/collections", icon: FolderOpen },
      { name: "Global Search", href: "/search", icon: Search },
    ],
  },
  {
    title: "AI Intelligence",
    items: [
      { name: "AI Chat", href: "/chat", icon: MessageSquare },
      { name: "Voice Assistant", href: "/voice", icon: Mic },
      { name: "Research Lab", href: "/research", icon: BookOpen },
      { name: "Smart Insights", href: "/insights", icon: Brain },
      { name: "Reports & Summaries", href: "/reports", icon: FileBarChart },
      { name: "Controlled Agents", href: "/automation", icon: Bot },
    ],
  },
  {
    title: "Management & System",
    items: [
      { name: "MCP Protocol", href: "/mcp", icon: Cpu },
      { name: "Integrations", href: "/integrations", icon: Blocks },
      { name: "Admin Telemetry", href: "/admin", icon: ShieldAlert },
      { name: "Security Center", href: "/security", icon: Shield },
      { name: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

const MODULE_METADATA: Record<string, { title: string; subtitle: string }> = {
  "/dashboard": {
    title: "Overview Dashboard",
    subtitle: "Synchronizing system telemetry & activity stream",
  },
  "/memories": {
    title: "Memory Vault",
    subtitle: "Retrieving episodic & semantic memory vectors",
  },
  "/memory-review": {
    title: "Review Inbox",
    subtitle: "Scanning pending memory candidates & extractions",
  },
  "/documents": {
    title: "Document Library",
    subtitle: "Indexing file chunks & storage vectors",
  },
  "/graph": {
    title: "Knowledge Graph",
    subtitle: "Traversing entity relationships & ontological nodes",
  },
  "/timeline": {
    title: "Memory Timeline",
    subtitle: "Reconstructing chronological memory milestones",
  },
  "/collections": {
    title: "Memory Collections",
    subtitle: "Clustering topical tags & semantic categories",
  },
  "/search": {
    title: "Unified Hybrid Search",
    subtitle: "Warming Reciprocal Rank Fusion & dense index",
  },
  "/chat": {
    title: "AI Intelligence Chat",
    subtitle: "Initializing conversational RAG & citation engine",
  },
  "/voice": {
    title: "Voice Assistant",
    subtitle: "Calibrating speech synthesis & audio transcription",
  },
  "/research": {
    title: "Research Lab",
    subtitle: "Synthesizing multi-source intelligence reports",
  },
  "/insights": {
    title: "Smart Insights",
    subtitle: "Detecting knowledge gaps, drift & contradictions",
  },
  "/reports": {
    title: "Reports & Summaries",
    subtitle: "Compiling executive digests & operational metrics",
  },
  "/automation": {
    title: "Controlled Agents",
    subtitle: "Loading agent sandbox & human-in-the-loop gates",
  },
  "/mcp": {
    title: "MCP Protocol Hub",
    subtitle: "Connecting Model Context Protocol tools & schemas",
  },
  "/integrations": {
    title: "API Integrations",
    subtitle: "Authenticating developer tokens & webhook endpoints",
  },
  "/admin": {
    title: "Admin Telemetry",
    subtitle: "Loading system health, audit logs & worker queues",
  },
  "/security": {
    title: "Security Center",
    subtitle: "Enforcing MFA, active sessions & cryptographic vault",
  },
  "/settings": {
    title: "System Settings",
    subtitle: "Loading workspace configuration & theme preferences",
  },
  "/onboarding": {
    title: "Welcome Onboarding",
    subtitle: "Configuring personalized memory space",
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated, isLoading, logout, activeWorkspaceId, setActiveWorkspace } =
    useAuthStore();

  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [workspaceDropdownOpen, setWorkspaceDropdownOpen] = useState(false);

  // Full Initial Boot Loader (guarantees full progressive 0-100% load)
  const [showInitialLoader, setShowInitialLoader] = useState(true);
  const [initialBootDone, setInitialBootDone] = useState(false);

  // Module Transition Loader (triggers on every page/module change)
  const [prevPath, setPrevPath] = useState(pathname);
  const [isModuleTransitioning, setIsModuleTransitioning] = useState(false);

  const activeMeta = MODULE_METADATA[pathname] || {
    title: "Neural Engine",
    subtitle: "Syncing MemoryVerse workspace...",
  };

  const handleInitialLoaderComplete = () => {
    setInitialBootDone(true);
    setTimeout(() => {
      setShowInitialLoader(false);
    }, 350);
  };

  // Safety fallback for initial boot
  useEffect(() => {
    const fallbackTimer = setTimeout(() => {
      setInitialBootDone(true);
      setShowInitialLoader(false);
    }, 4500);
    return () => clearTimeout(fallbackTimer);
  }, []);

  // Detect module/route changes and trigger the neural transition loader
  useEffect(() => {
    if (pathname !== prevPath) {
      setPrevPath(pathname);
      setIsModuleTransitioning(true);
    }
  }, [pathname, prevPath]);

  // Close mobile drawer on route transition
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (isAuthenticated) {
      api.get("/workspaces").then((res) => {
        if (res.success && res.data) {
          setWorkspaces(res.data);
          if (!activeWorkspaceId && res.data.length > 0) {
            setActiveWorkspace(res.data[0].id);
          }
        }
      });
    }
  }, [isAuthenticated, activeWorkspaceId, setActiveWorkspace]);

  const activeWorkspace =
    workspaces.find((w) => w.id === activeWorkspaceId) || workspaces[0];

  const handleLogout = async () => {
    await api.post("/auth/logout");
    if (typeof window !== "undefined") {
      sessionStorage.removeItem("memoryverse_booted");
    }
    logout();
    router.push("/login");
  };

  const renderNavList = () => (
    <div className="space-y-6">
      {navSections.map((section) => (
        <div key={section.title}>
          <h4 className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-2">
            {section.title}
          </h4>
          <nav className="space-y-1">
            {section.items.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                    isActive
                      ? "bg-[#014BAA]/10 text-[#014BAA] dark:bg-[#014BAA]/25 dark:text-[#F8F3F0] border border-[#014BAA]/30 font-semibold shadow-sm"
                      : "text-slate-500 dark:text-slate-400 hover:text-[#014BAA] dark:hover:text-[#F8F3F0] hover:bg-black/5 dark:hover:bg-white/5"
                  }`}
                >
                  <Icon className="w-4 h-4 shrink-0" />
                  <span className="truncate">{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      ))}
    </div>
  );

  return (
    <>
      {/* Full Initial Boot Neural Loader */}
      {showInitialLoader && (
        <AnimatedLoader
          size="fullscreen"
          durationMs={1800}
          label="Connecting to AI-MemoryVerse Brain..."
          sublabel="Authorizing multi-tenant workspace & neural index"
          onComplete={handleInitialLoaderComplete}
        />
      )}

      {/* Module Transition Neural Loader (triggers on every module change) */}
      {!showInitialLoader && isModuleTransitioning && (
        <AnimatedLoader
          key={pathname}
          size="fullscreen"
          durationMs={950}
          moduleName={activeMeta.title}
          label={`Synchronizing ${activeMeta.title}...`}
          sublabel={activeMeta.subtitle}
          onComplete={() => {
            setIsModuleTransitioning(false);
          }}
        />
      )}

      <div
        className={`min-h-screen bg-[#F8F3F0] dark:bg-navy-950 flex transition-opacity duration-300 ${
          initialBootDone ? "opacity-100" : "opacity-0"
        }`}
      >
        {/* Desktop Sidebar */}
        <aside className="hidden lg:flex w-64 bg-white/95 dark:bg-navy-900/70 border-r border-[#EEEBDA] dark:border-navy-800 flex-col justify-between shrink-0 transition-colors">
          <div className="flex flex-col h-full">
            {/* Brand, Workspace Switcher & Theme Quick Toggle */}
            <div className="p-4 border-b border-[#EEEBDA] dark:border-navy-800">
              <div className="flex items-center justify-between mb-4">
                <Logo size="md" />
                <ThemeToggle variant="icon" />
              </div>

              {/* Workspace dropdown */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-white dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 hover:border-[#014BAA]/50 text-left transition-colors shadow-xs"
                >
                  <div className="truncate">
                    <p className="text-xs font-bold text-[#282B4A] dark:text-white truncate">
                      {activeWorkspace?.name || "Personal Workspace"}
                    </p>
                    <p className="text-[10px] text-[#014BAA] dark:text-cyan-400 font-mono uppercase tracking-wider font-semibold">
                      Personal External Brain
                    </p>
                  </div>
                  <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
                </button>

                {workspaceDropdownOpen && (
                  <div className="absolute top-full left-0 right-0 mt-1.5 p-1 bg-white dark:bg-navy-900 border border-[#EEEBDA] dark:border-navy-700 rounded-lg shadow-xl z-50">
                    <div className="px-2 py-1 text-[10px] uppercase font-bold text-slate-500">
                      Switch Workspace
                    </div>
                    {workspaces.map((ws) => (
                      <button
                        key={ws.id}
                        onClick={() => {
                          setActiveWorkspace(ws.id);
                          setWorkspaceDropdownOpen(false);
                        }}
                        className={`w-full text-left px-2.5 py-1.5 rounded text-xs truncate flex items-center justify-between ${
                          ws.id === activeWorkspace?.id
                            ? "bg-[#014BAA]/10 text-[#014BAA] dark:text-cyan-400 font-semibold"
                            : "text-[#282B4A] dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-navy-800"
                        }`}
                      >
                        <span className="truncate">{ws.name}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Navigation Links */}
            <div className="flex-1 overflow-y-auto px-3 py-4">
              {renderNavList()}
            </div>

            {/* Theme Toggle Pill Segment in Sidebar Footer */}
            <div className="px-4 py-2.5 border-t border-[#EEEBDA] dark:border-navy-800 flex items-center justify-between bg-white/50 dark:bg-navy-950/40">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                Theme
              </span>
              <ThemeToggle variant="pill" showLabels={true} />
            </div>

            {/* User Profile & Logout */}
            <div className="p-3 border-t border-[#EEEBDA] dark:border-navy-800">
              <div className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-navy-950/60 border border-[#EEEBDA] dark:border-navy-800 shadow-xs">
                <div className="flex items-center space-x-2.5 truncate">
                  <div className="w-7 h-7 rounded-full bg-[#014BAA]/15 border border-[#014BAA]/30 flex items-center justify-center text-[#014BAA] dark:text-[#F8F3F0] text-xs font-bold">
                    {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
                  </div>
                  <div className="truncate">
                    <p className="text-xs font-semibold text-[#282B4A] dark:text-white truncate">
                      {user?.full_name || "User"}
                    </p>
                    <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  title="Log out"
                  className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-navy-800 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </aside>

        {/* Mobile Slide-Out Drawer & Overlay */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-50 lg:hidden">
            {/* Backdrop blur overlay */}
            <div
              className="fixed inset-0 bg-black/70 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileMenuOpen(false)}
            />

            {/* Slide-out Sidebar Drawer */}
            <div className="fixed inset-y-0 left-0 w-72 bg-white dark:bg-navy-900 border-r border-[#EEEBDA] dark:border-navy-800 flex flex-col justify-between shadow-2xl z-50 animate-in slide-in-from-left duration-200">
              <div className="flex flex-col h-full">
                {/* Header inside drawer with close button */}
                <div className="p-4 border-b border-[#EEEBDA] dark:border-navy-800 flex items-center justify-between">
                  <Logo size="md" />
                  <button
                    type="button"
                    onClick={() => setMobileMenuOpen(false)}
                    className="p-1.5 rounded-lg text-slate-500 hover:text-[#282B4A] dark:text-slate-400 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-navy-800 transition-colors"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                {/* Navigation list */}
                <div className="flex-1 overflow-y-auto px-3 py-4">
                  {renderNavList()}
                </div>

                {/* Theme Selector in Mobile Drawer */}
                <div className="px-4 py-2.5 border-t border-[#EEEBDA] dark:border-navy-800 flex items-center justify-between bg-white/50 dark:bg-navy-950/40">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">
                    Theme
                  </span>
                  <ThemeToggle variant="pill" showLabels={true} />
                </div>

                {/* User footer */}
                <div className="p-3 border-t border-[#EEEBDA] dark:border-navy-800">
                  <div className="flex items-center justify-between p-2 rounded-lg bg-white dark:bg-navy-950/60 border border-[#EEEBDA] dark:border-navy-800 shadow-xs">
                    <div className="flex items-center space-x-2.5 truncate">
                      <div className="w-7 h-7 rounded-full bg-[#014BAA]/15 border border-[#014BAA]/30 flex items-center justify-center text-[#014BAA] dark:text-[#F8F3F0] text-xs font-bold">
                        {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
                      </div>
                      <div className="truncate">
                        <p className="text-xs font-semibold text-[#282B4A] dark:text-white truncate">
                          {user?.full_name || "User"}
                        </p>
                        <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{user?.email}</p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={handleLogout}
                      title="Log out"
                      className="p-1.5 rounded text-slate-400 hover:text-red-400 hover:bg-navy-800 transition-colors"
                    >
                      <LogOut className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
          {/* Mobile Top Header */}
          <header className="lg:hidden h-14 border-b border-[#EEEBDA] dark:border-navy-800 bg-white/90 dark:bg-navy-950/90 flex items-center justify-between px-4 sticky top-0 z-40 backdrop-blur-md">
            <Logo size="sm" />
            <div className="flex items-center space-x-2">
              <ThemeToggle variant="icon" />
              <button
                type="button"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="p-2 rounded-lg text-slate-600 dark:text-slate-300 hover:text-[#014BAA] dark:hover:text-white hover:bg-slate-100 dark:hover:bg-navy-800/80 transition-colors"
              >
                {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
            </div>
          </header>

          {/* Dynamic Page Content */}
          <main className="flex-1 overflow-y-auto bg-[#F8F3F0] dark:bg-navy-950 transition-colors">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
