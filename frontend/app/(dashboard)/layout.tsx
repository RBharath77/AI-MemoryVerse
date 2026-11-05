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
  CreditCard,
  Shield,
  Settings,
  ShieldAlert,
  LogOut,
  ChevronDown,
  Menu,
  X,
  Plus,
} from "lucide-react";
import { useAuthStore } from "@/store/auth-store";
import { api } from "@/lib/api";

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
      { name: "Integrations", href: "/integrations", icon: Blocks },
      { name: "Usage & Billing", href: "/billing", icon: CreditCard },
      { name: "Admin Telemetry", href: "/admin", icon: ShieldAlert },
      { name: "Security Center", href: "/security", icon: Shield },
      { name: "Settings", href: "/settings", icon: Settings },
    ],
  },
];

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

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push("/login");
    }
  }, [isLoading, isAuthenticated, router]);

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
    logout();
    router.push("/login");
  };

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-navy-950 flex items-center justify-center text-slate-400">
        <div className="flex flex-col items-center space-y-4">
          <Brain className="w-10 h-10 text-cyan-400 animate-pulse" />
          <p className="text-sm">Accessing personal external brain...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-navy-950 flex">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:flex w-64 bg-navy-900/70 border-r border-navy-800 flex-col justify-between shrink-0">
        <div className="flex flex-col h-full">
          {/* Brand & Workspace Switcher */}
          <div className="p-4 border-b border-navy-800">
            <div className="flex items-center space-x-2.5 mb-4">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center shadow-md shadow-cyan-500/20">
                <Brain className="w-5 h-5 text-white" />
              </div>
              <span className="font-bold text-base tracking-tight text-white">
                AI-MemoryVerse
              </span>
            </div>

            {/* Workspace dropdown */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setWorkspaceDropdownOpen(!workspaceDropdownOpen)}
                className="w-full flex items-center justify-between px-3 py-2 rounded-lg bg-navy-950 border border-navy-700 hover:border-cyan-500/50 text-left transition-colors"
              >
                <div className="truncate">
                  <p className="text-xs font-semibold text-white truncate">
                    {activeWorkspace?.name || "My Workspace"}
                  </p>
                  <p className="text-[10px] text-cyan-400 font-mono uppercase tracking-wider">
                    {activeWorkspace?.plan_tier || "free"} plan
                  </p>
                </div>
                <ChevronDown className="w-4 h-4 text-slate-400 shrink-0 ml-2" />
              </button>

              {workspaceDropdownOpen && (
                <div className="absolute top-full left-0 right-0 mt-1.5 p-1 bg-navy-900 border border-navy-700 rounded-lg shadow-xl z-50">
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
                          ? "bg-cyan-500/10 text-cyan-400 font-medium"
                          : "text-slate-300 hover:bg-navy-800"
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
          <div className="flex-1 overflow-y-auto px-3 py-4 space-y-6">
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
                        className={`flex items-center space-x-3 px-3 py-2 rounded-lg text-xs font-medium transition-colors ${
                          isActive
                            ? "bg-cyan-500/15 text-cyan-400 border border-cyan-500/20"
                            : "text-slate-400 hover:text-slate-200 hover:bg-navy-800/60"
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

          {/* User Profile & Logout */}
          <div className="p-3 border-t border-navy-800">
            <div className="flex items-center justify-between p-2 rounded-lg bg-navy-950/60 border border-navy-800">
              <div className="flex items-center space-x-2.5 truncate">
                <div className="w-7 h-7 rounded-full bg-cyan-500/20 border border-cyan-500/30 flex items-center justify-center text-cyan-400 text-xs font-bold">
                  {user?.full_name?.charAt(0) || user?.email?.charAt(0) || "U"}
                </div>
                <div className="truncate">
                  <p className="text-xs font-medium text-white truncate">
                    {user?.full_name || "User"}
                  </p>
                  <p className="text-[10px] text-slate-400 truncate">{user?.email}</p>
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

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile Header */}
        <header className="lg:hidden h-14 border-b border-navy-800 bg-navy-950/90 flex items-center justify-between px-4 sticky top-0 z-40">
          <div className="flex items-center space-x-2">
            <div className="w-7 h-7 rounded bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-sm text-white">AI-MemoryVerse</span>
          </div>
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-1.5 rounded text-slate-400 hover:text-white"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </header>

        {/* Dynamic Page Content */}
        <main className="flex-1 overflow-y-auto bg-navy-950">
          {children}
        </main>
      </div>
    </div>
  );
}

