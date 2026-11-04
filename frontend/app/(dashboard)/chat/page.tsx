"use client";

import { useState, useRef, useEffect } from "react";
import {
  MessageSquare,
  Send,
  Sparkles,
  Bot,
  User,
  Copy,
  Check,
  RefreshCw,
  Plus,
  BookOpen,
  Vault,
  ChevronDown,
  Trash2,
  ExternalLink,
} from "lucide-react";
import { useAuthStore } from "@/store/auth-store";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Array<{
    title: string;
    sourceType: string;
    snippet: string;
  }>;
  timestamp: string;
}

interface Conversation {
  id: string;
  title: string;
  updatedAt: string;
}

export default function ChatPage() {
  const { user } = useAuthStore();
  const [conversations, setConversations] = useState<Conversation[]>([
    {
      id: "conv-1",
      title: "Architecture & RAG Design",
      updatedAt: "Just now",
    },
  ]);
  const [activeConvId, setActiveConvId] = useState("conv-1");
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "msg-1",
      role: "assistant",
      content:
        "Hello! I am your AI-MemoryVerse assistant. I have access to your personal memory vault and uploaded workspace documents. How can I assist you today?",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [inputMessage, setInputMessage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedModel, setSelectedModel] = useState("gpt-4o-mini");
  const [includeMemories, setIncludeMemories] = useState(true);
  const [includeDocuments, setIncludeDocuments] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isGenerating) return;

    const userText = inputMessage.trim();
    setInputMessage("");

    const userMsg: Message = {
      id: Math.random().toString(),
      role: "user",
      content: userText,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsGenerating(true);

    // Simulate grounded retrieval response with citations
    setTimeout(() => {
      const assistantMsg: Message = {
        id: Math.random().toString(),
        role: "assistant",
        content: `Based on your persistent knowledge vault and workspace context:\n\nRegarding "${userText}", AI-MemoryVerse uses a modular monolith with asynchronous background workers and PostgreSQL pgvector hybrid search to maintain source-grounded accuracy without hallucinations.`,
        citations: [
          {
            title: "Memory Vault Fact #12",
            sourceType: "Memory",
            snippet: "Always generate async SQLAlchemy 2.0 queries with PostgreSQL pgvector embeddings.",
          },
          {
            title: "System Architecture Specification",
            sourceType: "Document",
            snippet: "FastAPI modular monolith combined with Next.js App Router and Celery distributed tasks.",
          },
        ],
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      };
      setMessages((prev) => [...prev, assistantMsg]);
      setIsGenerating(false);
    }, 1000);
  };

  const handleCopy = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const startNewConversation = () => {
    const newId = `conv-${Date.now()}`;
    const newConv: Conversation = {
      id: newId,
      title: "New Conversation",
      updatedAt: "Just now",
    };
    setConversations([newConv, ...conversations]);
    setActiveConvId(newId);
    setMessages([
      {
        id: "msg-welcome",
        role: "assistant",
        content: "Started a fresh conversation. Your personal memories remain active in the background.",
        timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      },
    ]);
  };

  return (
    <div className="h-[calc(100vh-3.5rem)] lg:h-screen flex bg-navy-950 overflow-hidden">
      {/* Left Chat History Sidebar */}
      <div className="hidden md:flex w-64 bg-navy-900/50 border-r border-navy-800 flex-col justify-between shrink-0">
        <div className="p-4 space-y-3">
          <button
            onClick={startNewConversation}
            className="w-full py-2 px-3 rounded-lg bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold text-xs flex items-center justify-center space-x-2 transition-colors shadow-md shadow-cyan-500/20"
          >
            <Plus className="w-4 h-4" />
            <span>New Conversation</span>
          </button>

          <div className="pt-2">
            <h4 className="text-[10px] font-bold uppercase tracking-wider text-slate-500 px-1 mb-2">
              Recent Chats
            </h4>
            <div className="space-y-1">
              {conversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => setActiveConvId(c.id)}
                  className={`w-full text-left px-3 py-2 rounded-lg text-xs truncate flex items-center space-x-2 transition-colors ${
                    activeConvId === c.id
                      ? "bg-navy-800 text-cyan-400 font-semibold"
                      : "text-slate-400 hover:text-white hover:bg-navy-800/40"
                  }`}
                >
                  <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                  <span className="truncate">{c.title}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Context Filters */}
        <div className="p-4 border-t border-navy-800 space-y-2 text-xs">
          <div className="text-[10px] uppercase font-bold text-slate-500 mb-1">
            Retrieval Context
          </div>
          <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeMemories}
              onChange={(e) => setIncludeMemories(e.target.checked)}
              className="accent-cyan-400 rounded"
            />
            <Vault className="w-3.5 h-3.5 text-cyan-400" />
            <span>Search Memories</span>
          </label>
          <label className="flex items-center space-x-2 text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={includeDocuments}
              onChange={(e) => setIncludeDocuments(e.target.checked)}
              className="accent-blue-400 rounded"
            />
            <BookOpen className="w-3.5 h-3.5 text-blue-400" />
            <span>Search Documents</span>
          </label>
        </div>
      </div>

      {/* Main Chat Interface */}
      <div className="flex-1 flex flex-col justify-between overflow-hidden">
        {/* Top Chat Bar */}
        <div className="h-14 border-b border-navy-800 bg-navy-900/40 px-6 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-2.5 h-2.5 rounded-full bg-cyan-400 animate-pulse" />
            <span className="text-xs font-semibold text-white">
              AI-MemoryVerse Assistant
            </span>
          </div>

          <div className="flex items-center space-x-3">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              className="bg-navy-950 border border-navy-700 rounded-lg px-2.5 py-1 text-xs text-white focus:outline-none focus:border-cyan-500"
            >
              <option value="gpt-4o-mini">gpt-4o-mini (Fast & Grounded)</option>
              <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
              <option value="claude-3-5-sonnet">Claude 3.5 Sonnet</option>
            </select>
          </div>
        </div>

        {/* Message Feed */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex items-start space-x-3 max-w-3xl ${
                msg.role === "user" ? "ml-auto flex-row-reverse space-x-reverse" : ""
              }`}
            >
              <div
                className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                  msg.role === "user"
                    ? "bg-cyan-500/20 border border-cyan-500/40 text-cyan-400"
                    : "bg-navy-900 border border-navy-700 text-slate-300"
                }`}
              >
                {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div
                className={`p-4 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                  msg.role === "user"
                    ? "bg-cyan-500 text-navy-950 font-medium rounded-tr-none"
                    : "bg-navy-900/60 border border-navy-800 text-slate-100 rounded-tl-none space-y-3"
                }`}
              >
                <div className="whitespace-pre-wrap">{msg.content}</div>

                {/* Citations block for assistant responses */}
                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-navy-800 space-y-2">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 flex items-center space-x-1">
                      <Sparkles className="w-3 h-3 text-cyan-400" />
                      <span>Verified Grounded Citations</span>
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {msg.citations.map((cite, idx) => (
                        <div
                          key={idx}
                          className="p-2 rounded-lg bg-navy-950 border border-navy-800 text-[11px]"
                        >
                          <div className="font-semibold text-cyan-400 flex items-center justify-between">
                            <span>{cite.title}</span>
                            <span className="text-[9px] uppercase font-mono px-1.5 py-0.2 rounded bg-navy-900 text-slate-400">
                              {cite.sourceType}
                            </span>
                          </div>
                          <p className="text-slate-400 mt-1 line-clamp-2">{cite.snippet}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {msg.role === "assistant" && (
                  <div className="flex items-center justify-between pt-1 text-[10px] text-slate-500">
                    <span>{msg.timestamp}</span>
                    <button
                      onClick={() => handleCopy(msg.id, msg.content)}
                      className="hover:text-cyan-400 transition-colors flex items-center space-x-1"
                    >
                      {copiedId === msg.id ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                      <span>{copiedId === msg.id ? "Copied" : "Copy"}</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {isGenerating && (
            <div className="flex items-start space-x-3 max-w-3xl">
              <div className="w-8 h-8 rounded-lg bg-navy-900 border border-navy-700 flex items-center justify-center text-slate-300">
                <Bot className="w-4 h-4 animate-pulse" />
              </div>
              <div className="p-4 rounded-2xl bg-navy-900/60 border border-navy-800 text-xs text-slate-400 flex items-center space-x-2">
                <div className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
                <span>Retrieving memories and formulating answer...</span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-navy-800 bg-navy-900/40">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask anything across your personal memories and documents..."
              className="flex-1 py-3 px-4 bg-navy-950 border border-navy-700 rounded-xl text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
            <button
              type="submit"
              disabled={isGenerating || !inputMessage.trim()}
              className="p-3 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold transition-colors disabled:opacity-50 shadow-lg shadow-cyan-500/20"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
