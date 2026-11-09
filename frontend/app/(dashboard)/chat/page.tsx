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
  Plus,
  BookOpen,
  Vault,
  Trash2,
  ThumbsUp,
  ThumbsDown,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface CitationItem {
  citation_index: number;
  marker: string;
  source_type: string;
  source_id: string;
  title: string;
  snippet: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  token_count?: number;
  citations?: CitationItem[];
  feedback?: number | null;
  created_at?: string;
}

interface ConversationItem {
  id: string;
  title: string;
  model: string;
  message_count: number;
  updated_at: string;
}

export default function ChatPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [conversations, setConversations] = useState<ConversationItem[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputMessage, setInputMessage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isLoadingConvs, setIsLoadingConvs] = useState(true);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [activeCitation, setActiveCitation] = useState<CitationItem | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isGenerating]);

  // Load conversations on workspace change
  useEffect(() => {
    if (activeWorkspaceId) {
      loadConversations();
    }
  }, [activeWorkspaceId]);

  const loadConversations = async () => {
    setIsLoadingConvs(true);
    const res = await api.get("/chat/conversations");
    if (res.success && res.data?.items) {
      setConversations(res.data.items);
      if (res.data.items.length > 0 && !activeConvId) {
        selectConversation(res.data.items[0].id);
      } else if (res.data.items.length === 0) {
        // Automatically create a conversation if none exists
        handleNewConversation();
      }
    }
    setIsLoadingConvs(false);
  };

  const selectConversation = async (convId: string) => {
    setActiveConvId(convId);
    const res = await api.get(`/chat/conversations/${convId}/messages`);
    if (res.success && res.data) {
      setMessages(res.data);
    }
  };

  const handleNewConversation = async () => {
    const res = await api.post("/chat/conversations", {
      title: "New Conversation",
    });
    if (res.success && res.data) {
      setConversations((prev) => [res.data, ...prev]);
      setActiveConvId(res.data.id);
      setMessages([]);
    }
  };

  const handleDeleteConversation = async (e: React.MouseEvent, convId: string) => {
    e.stopPropagation();
    const res = await api.delete(`/chat/conversations/${convId}`);
    if (res.success) {
      const remaining = conversations.filter((c) => c.id !== convId);
      setConversations(remaining);
      if (activeConvId === convId) {
        if (remaining.length > 0) {
          selectConversation(remaining[0].id);
        } else {
          setActiveConvId(null);
          setMessages([]);
        }
      }
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMessage.trim() || isGenerating) return;

    let convId = activeConvId;
    if (!convId) {
      const convRes = await api.post("/chat/conversations", { title: "New Conversation" });
      if (convRes.success && convRes.data) {
        convId = convRes.data.id;
        setActiveConvId(convId);
        setConversations((prev) => [convRes.data, ...prev]);
      } else {
        return;
      }
    }

    if (!convId) return;
    const currentConvId: string = convId;

    const userText = inputMessage.trim();
    setInputMessage("");

    // Optimistic user message
    const tempUserMsg: Message = {
      id: "temp-" + Date.now(),
      role: "user",
      content: userText,
      created_at: new Date().toISOString(),
    };

    // Optimistic streaming assistant message
    const streamAssistantId = "stream-" + Date.now();
    const streamAssistantMsg: Message = {
      id: streamAssistantId,
      role: "assistant",
      content: "",
      created_at: new Date().toISOString(),
      citations: [],
    };

    setMessages((prev) => [...prev, tempUserMsg, streamAssistantMsg]);
    setIsGenerating(true);

    try {
      await api.streamChat(currentConvId, userText, {
        onCitations: (citations) => {
          setMessages((prev) =>
            prev.map((m) => (m.id === streamAssistantId ? { ...m, citations } : m))
          );
        },
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === streamAssistantId ? { ...m, content: m.content + token } : m
            )
          );
        },
        onDone: (data) => {
          if (data?.message_id) {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === streamAssistantId ? { ...m, id: data.message_id } : m
              )
            );
          }
        },
        onError: async (err) => {
          console.warn("SSE stream failed, falling back to sync POST", err);
          const fallbackRes = await api.post(`/chat/conversations/${currentConvId}/messages`, {
            content: userText,
          });
          if (fallbackRes.success && fallbackRes.data) {
            setMessages((prev) => [
              ...prev.filter((m) => m.id !== streamAssistantId),
              fallbackRes.data,
            ]);
          }
        },
      });

      // Update sidebar title if newly created
      setConversations((prev) =>
        prev.map((c) =>
          c.id === currentConvId && c.title === "New Conversation"
            ? { ...c, title: userText.slice(0, 30) + "..." }
            : c
        )
      );
    } catch (err) {
      console.error("Chat error:", err);
    } finally {
      setIsGenerating(false);
    }
  };

  const handleFeedback = async (messageId: string, rating: number) => {
    if (!activeConvId) return;
    const res = await api.post(`/chat/conversations/${activeConvId}/messages/${messageId}/feedback`, {
      rating,
    });
    if (res.success) {
      setMessages((prev) =>
        prev.map((m) => (m.id === messageId ? { ...m, feedback: rating } : m))
      );
    }
  };

  const handleCopy = (content: string, id: string) => {
    navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="h-[calc(100vh-4rem)] flex overflow-hidden">
      {/* Conversations Sidebar */}
      <div className="w-80 border-r border-[#EEEBDA] dark:border-navy-800 bg-white/80 dark:bg-navy-950/70 flex flex-col shrink-0">
        <div className="p-4 border-b border-[#EEEBDA] dark:border-navy-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <MessageSquare className="w-5 h-5 text-[#014BAA] dark:text-cyan-400" />
            <h2 className="text-sm font-bold text-[#282B4A] dark:text-white tracking-tight">Conversations</h2>
          </div>
          <button
            onClick={handleNewConversation}
            className="p-1.5 rounded-lg bg-[#014BAA]/10 hover:bg-[#014BAA]/20 text-[#014BAA] border border-[#014BAA]/30 dark:bg-cyan-500/10 dark:text-cyan-400 dark:border-cyan-500/30 transition-colors"
            title="New Chat"
          >
            <Plus className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          {isLoadingConvs ? (
            <div className="py-8 flex justify-center text-slate-400">
              <Loader2 className="w-5 h-5 animate-spin text-[#014BAA] dark:text-cyan-400" />
            </div>
          ) : conversations.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-6">No conversations yet.</p>
          ) : (
            conversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => selectConversation(conv.id)}
                className={`p-3 rounded-xl border text-left cursor-pointer transition-all flex items-center justify-between group ${
                  activeConvId === conv.id
                    ? "bg-[#014BAA]/10 border-[#014BAA]/40 text-[#014BAA] dark:bg-navy-900 dark:border-cyan-500/50 dark:text-white font-semibold shadow-xs"
                    : "border-transparent text-slate-600 dark:text-slate-400 hover:text-[#014BAA] dark:hover:text-white hover:bg-slate-100 dark:hover:bg-navy-900/50"
                }`}
              >
                <div className="truncate flex-1 pr-2">
                  <p className="text-xs font-semibold truncate">{conv.title}</p>
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">{formatDate(conv.updated_at)}</p>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(e, conv.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-slate-400 hover:text-red-500 transition-opacity"
                  title="Delete chat"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="flex-1 flex flex-col bg-transparent dark:bg-navy-900/20 overflow-hidden relative">
        {/* Messages List */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-5">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center max-w-md mx-auto space-y-4">
              <div className="w-12 h-12 rounded-2xl bg-[#014BAA]/10 border border-[#014BAA]/30 flex items-center justify-center text-[#014BAA] dark:text-cyan-400">
                <Sparkles className="w-6 h-6" />
              </div>
              <h3 className="text-base font-bold text-[#282B4A] dark:text-white">Ask AI-MemoryVerse</h3>
              <p className="text-xs text-slate-600 dark:text-slate-400 leading-relaxed">
                Ask questions about your projects, personal rules, or uploaded documentation. Answers are source-grounded in your workspace vault.
              </p>
            </div>
          ) : (
            messages.map((msg, idx) => {
              const isAssistant = msg.role === "assistant";
              return (
                <div
                  key={msg.id}
                  className={`flex space-x-3 max-w-4xl ${isAssistant ? "" : "ml-auto justify-end"}`}
                >
                  {isAssistant && (
                    <div className="w-8 h-8 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/30 flex items-center justify-center text-[#014BAA] dark:text-cyan-400 shrink-0 mt-0.5">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}

                  <div
                    className={`rounded-2xl p-4 text-xs sm:text-sm leading-relaxed space-y-3 ${
                      isAssistant
                        ? "bg-white dark:bg-navy-900/80 border border-[#EEEBDA] dark:border-navy-800 text-[#282B4A] dark:text-slate-100 shadow-sm"
                        : "bg-[#014BAA] text-[#F8F3F0] font-medium ml-12 shadow-md shadow-[#014BAA]/20"
                    }`}
                  >
                    <p className="whitespace-pre-wrap">
                      {msg.content}
                      {isAssistant && isGenerating && idx === messages.length - 1 && (
                        <span className="inline-block w-1.5 h-3.5 ml-1 bg-[#014BAA] dark:bg-cyan-400 animate-pulse align-middle" />
                      )}
                    </p>

                    {/* Citations Footer */}
                    {isAssistant && msg.citations && msg.citations.length > 0 && (
                      <div className="pt-2 border-t border-[#EEEBDA] dark:border-navy-800/80 space-y-1.5">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-[#014BAA] dark:text-cyan-400">
                          Grounded Sources:
                        </span>
                        <div className="flex flex-wrap gap-2">
                          {msg.citations.map((c) => (
                            <button
                              key={c.citation_index}
                              onClick={() => setActiveCitation(c)}
                              className="px-2 py-1 rounded-md bg-[#F8F3F0] dark:bg-navy-950 border border-[#EEEBDA] dark:border-navy-700 hover:border-[#014BAA]/40 text-[11px] text-[#282B4A] dark:text-slate-300 flex items-center space-x-1.5 transition-colors"
                            >
                              <span className="font-mono text-[#014BAA] dark:text-cyan-400 font-bold">{c.marker}</span>
                              <span className="truncate max-w-[140px]">{c.title}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Actions on Assistant Response */}
                    {isAssistant && (
                      <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={() => handleFeedback(msg.id, 1)}
                            className={`p-1 rounded hover:text-emerald-400 transition-colors ${
                              msg.feedback === 1 ? "text-emerald-400" : ""
                            }`}
                            title="Helpful"
                          >
                            <ThumbsUp className="w-3.5 h-3.5" />
                          </button>
                          <button
                            onClick={() => handleFeedback(msg.id, -1)}
                            className={`p-1 rounded hover:text-red-400 transition-colors ${
                              msg.feedback === -1 ? "text-red-400" : ""
                            }`}
                            title="Unhelpful"
                          >
                            <ThumbsDown className="w-3.5 h-3.5" />
                          </button>
                        </div>

                        <button
                          onClick={() => handleCopy(msg.content, msg.id)}
                          className="flex items-center space-x-1 hover:text-white transition-colors"
                        >
                          {copiedId === msg.id ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>

                  {!isAssistant && (
                    <div className="w-8 h-8 rounded-xl bg-[#014BAA] text-[#F8F3F0] flex items-center justify-center font-bold text-xs shrink-0 mt-0.5 shadow-md shadow-[#014BAA]/25">
                      <User className="w-4 h-4" />
                    </div>
                  )}
                </div>
              );
            })
          )}

          {isGenerating &&
            (!messages.length ||
              messages[messages.length - 1]?.role !== "assistant" ||
              !messages[messages.length - 1]?.content) && (
              <div className="flex items-center space-x-3 text-slate-500 dark:text-slate-400 text-xs">
                <div className="w-8 h-8 rounded-xl bg-[#014BAA]/10 border border-[#014BAA]/30 flex items-center justify-center text-[#014BAA] dark:text-cyan-400 shrink-0">
                  <Loader2 className="w-4 h-4 animate-spin" />
                </div>
                <span className="animate-pulse">Retrieving vault context & generating response...</span>
              </div>
            )}
          <div ref={messagesEndRef} />
        </div>

        {/* Citation Detail Popover */}
        {activeCitation && (
          <div className="p-4 bg-white dark:bg-navy-900 border-t border-[#EEEBDA] dark:border-navy-800 flex items-start justify-between gap-4 shadow-lg">
            <div className="space-y-1 text-xs">
              <div className="flex items-center space-x-2">
                <span className="font-mono font-bold text-[#014BAA] dark:text-cyan-400">{activeCitation.marker}</span>
                <span className="font-bold text-[#282B4A] dark:text-white">{activeCitation.title}</span>
                <span className="uppercase text-[10px] px-1.5 py-0.5 rounded bg-[#F8F3F0] dark:bg-navy-950 text-slate-600 dark:text-slate-400 border border-[#EEEBDA] dark:border-navy-800">
                  {activeCitation.source_type}
                </span>
              </div>
              <p className="text-slate-600 dark:text-slate-300 leading-relaxed font-mono">{activeCitation.snippet}</p>
            </div>
            <button
              onClick={() => setActiveCitation(null)}
              className="text-slate-400 hover:text-[#282B4A] dark:hover:text-white text-xs font-semibold shrink-0"
            >
              Close
            </button>
          </div>
        )}

        {/* Input Bar */}
        <div className="p-4 border-t border-[#EEEBDA] dark:border-navy-800 bg-white/90 dark:bg-navy-950/80 backdrop-blur">
          <form onSubmit={handleSendMessage} className="max-w-4xl mx-auto flex items-center space-x-2">
            <input
              type="text"
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              placeholder="Ask anything grounded in your memories and documents..."
              disabled={isGenerating}
              className="flex-1 bg-[#F8F3F0] dark:bg-navy-900 border border-[#EEEBDA] dark:border-navy-700 rounded-xl px-4 py-3 text-xs sm:text-sm text-[#282B4A] dark:text-white placeholder-slate-400 focus:outline-none focus:border-[#014BAA] transition-colors"
            />
            <button
              type="submit"
              disabled={isGenerating || !inputMessage.trim()}
              className="p-3 rounded-xl bg-[#014BAA] hover:bg-[#014BAA]/90 text-[#F8F3F0] font-bold transition-all disabled:opacity-50 disabled:pointer-events-none shadow-md shadow-[#014BAA]/25"
            >
              <Send className="w-4 h-4 text-[#F8F3F0]" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
