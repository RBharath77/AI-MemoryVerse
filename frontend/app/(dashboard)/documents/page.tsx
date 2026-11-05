"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Upload,
  Search,
  Trash2,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Eye,
  Download,
  X,
  FileCode,
  FileSpreadsheet,
  FileCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface DocumentItem {
  id: string;
  title: string;
  filename: string;
  mime_type: string;
  file_size: number;
  status: "pending" | "processing" | "extracting_text" | "chunking" | "completed" | "failed";
  error_message?: string | null;
  page_count?: number | null;
  word_count?: number | null;
  token_count?: number | null;
  summary?: string | null;
  chunk_count: number;
  created_at: string;
}

interface DocumentChunk {
  id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  start_char?: number | null;
  end_char?: number | null;
  section_title?: string | null;
}

export default function DocumentLibraryPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Chunks Inspector Modal
  const [selectedDoc, setSelectedDoc] = useState<DocumentItem | null>(null);
  const [chunks, setChunks] = useState<DocumentChunk[]>([]);
  const [isLoadingChunks, setIsLoadingChunks] = useState(false);

  const fetchDocuments = async () => {
    setIsLoading(true);
    let url = "/documents?";
    if (searchQuery.trim()) {
      url += `search=${encodeURIComponent(searchQuery.trim())}&`;
    }
    const res = await api.get(url);
    if (res.success && res.data) {
      setDocuments(res.data.items || []);
    }
    setIsLoading(false);
  };

  useEffect(() => {
    if (activeWorkspaceId) {
      fetchDocuments();
    }
  }, [activeWorkspaceId, searchQuery]);

  const formatFileSize = (bytes: number): string => {
    if (!bytes) return "0 B";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getFileIcon = (filename: string) => {
    const ext = filename.split(".").pop()?.toLowerCase();
    if (ext === "pdf") return FileText;
    if (ext === "csv" || ext === "xlsx") return FileSpreadsheet;
    if (ext === "json" || ext === "html") return FileCode;
    return FileCheck;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-emerald-950/80 border-emerald-500/30 text-emerald-400";
      case "processing":
      case "extracting_text":
      case "chunking":
        return "bg-cyan-950/80 border-cyan-500/30 text-cyan-400 animate-pulse";
      case "pending":
        return "bg-amber-950/80 border-amber-500/30 text-amber-400";
      case "failed":
        return "bg-red-950/80 border-red-500/30 text-red-400";
      default:
        return "bg-navy-950 border-navy-700 text-slate-400";
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || !e.target.files[0]) return;
    const file = e.target.files[0];

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("title", file.name);

    const res = await api.uploadFormData("/documents/upload", formData);

    if (res.success && res.data) {
      await fetchDocuments();
    } else {
      setUploadError(res.error?.message || "Failed to upload document.");
    }
    setIsUploading(false);
    e.target.value = "";
  };

  const handleDelete = async (id: string) => {
    const res = await api.delete(`/documents/${id}`);
    if (res.success) {
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      if (selectedDoc?.id === id) {
        setSelectedDoc(null);
      }
    }
  };

  const handleRetry = async (id: string) => {
    const res = await api.post(`/documents/${id}/retry`);
    if (res.success) {
      await fetchDocuments();
    }
  };

  const handleInspectChunks = async (doc: DocumentItem) => {
    setSelectedDoc(doc);
    setIsLoadingChunks(true);
    const res = await api.get(`/documents/${doc.id}/chunks`);
    if (res.success && res.data) {
      setChunks(res.data.items || []);
    }
    setIsLoadingChunks(false);
  };

  const handleDownload = async (id: string) => {
    const res = await api.get(`/documents/${id}/download`);
    if (res.success && res.data?.download_url) {
      window.open(res.data.download_url, "_blank");
    }
  };

  return (
    <div className="p-6 sm:p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-navy-800">
        <div>
          <div className="flex items-center space-x-2">
            <FileText className="w-6 h-6 text-blue-400" />
            <h1 className="text-2xl font-extrabold text-white tracking-tight">
              Document Intelligence
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-400 mt-1">
            Upload, parse, and chunk PDF, DOCX, TXT, Markdown, CSV, and HTML documents for RAG.
          </p>
        </div>

        <label
          className={`px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-400 text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-lg shadow-blue-500/20 transition-colors cursor-pointer ${
            isUploading ? "opacity-50 pointer-events-none" : ""
          }`}
        >
          {isUploading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Uploading & Parsing...</span>
            </>
          ) : (
            <>
              <Upload className="w-4 h-4" />
              <span>Upload Document</span>
            </>
          )}
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.doc,.txt,.md,.markdown,.csv,.json,.html"
            onChange={handleFileUpload}
            disabled={isUploading}
          />
        </label>
      </div>

      {uploadError && (
        <div className="p-3 rounded-lg border border-red-500/30 bg-red-950/30 text-red-400 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{uploadError}</span>
        </div>
      )}

      {/* Search and Filters */}
      <div className="flex items-center justify-between gap-4">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by name or title..."
            className="w-full pl-9 pr-4 py-2 bg-navy-900/80 border border-navy-800 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
          />
        </div>

        <span className="text-xs font-semibold px-3 py-1.5 rounded-full bg-navy-900 border border-navy-700 text-slate-300">
          {documents.length} documents
        </span>
      </div>

      {/* Documents List */}
      {isLoading ? (
        <div className="py-20 flex flex-col items-center justify-center text-slate-400 space-y-3">
          <Loader2 className="w-8 h-8 animate-spin text-blue-400" />
          <p className="text-xs">Loading document library...</p>
        </div>
      ) : documents.length === 0 ? (
        <div className="py-16 px-4 rounded-2xl border border-navy-800 bg-navy-900/20 text-center">
          <div className="w-12 h-12 rounded-xl bg-navy-900 border border-navy-700 flex items-center justify-center mx-auto mb-4 text-blue-400">
            <FileText className="w-6 h-6" />
          </div>
          <h3 className="text-base font-bold text-white mb-1">No documents found</h3>
          <p className="text-xs text-slate-400 max-w-sm mx-auto mb-6">
            Upload your technical documentation, research papers, design specs, or notes to ground AI answers with verifiable sources.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {documents.map((doc) => {
            const Icon = getFileIcon(doc.filename);
            return (
              <div
                key={doc.id}
                className="p-4 rounded-xl border border-navy-800 bg-navy-900/40 hover:border-navy-700 transition-all flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div className="flex items-start space-x-3 flex-1 min-w-0">
                  <div className="p-2.5 rounded-lg bg-navy-950 border border-navy-800 text-blue-400 shrink-0 mt-0.5">
                    <Icon className="w-5 h-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center space-x-2">
                      <h4 className="text-sm font-bold text-white truncate">{doc.title}</h4>
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${getStatusBadge(
                          doc.status
                        )}`}
                      >
                        {doc.status}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400 truncate mt-0.5">{doc.filename}</p>
                    <div className="text-[11px] text-slate-500 flex flex-wrap items-center gap-3 mt-1.5">
                      <span>Size: {formatFileSize(doc.file_size)}</span>
                      <span>Chunks: {doc.chunk_count}</span>
                      {doc.word_count ? <span>Words: {doc.word_count.toLocaleString()}</span> : null}
                      <span>Uploaded: {formatDate(doc.created_at)}</span>
                    </div>
                    {doc.error_message && (
                      <p className="text-[11px] text-red-400 mt-1">Error: {doc.error_message}</p>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2 shrink-0">
                  {doc.chunk_count > 0 && (
                    <button
                      onClick={() => handleInspectChunks(doc)}
                      className="px-3 py-1.5 rounded-lg border border-navy-700 hover:border-cyan-500/40 hover:bg-cyan-950/20 text-slate-300 hover:text-cyan-400 text-xs font-semibold flex items-center space-x-1.5 transition-colors"
                      title="Inspect chunks"
                    >
                      <Eye className="w-3.5 h-3.5" />
                      <span>Chunks</span>
                    </button>
                  )}
                  {doc.status === "failed" && (
                    <button
                      onClick={() => handleRetry(doc.id)}
                      className="p-1.5 rounded-lg border border-navy-700 hover:border-amber-500/40 hover:bg-amber-950/20 text-slate-400 hover:text-amber-400 transition-colors"
                      title="Retry processing"
                    >
                      <RefreshCw className="w-4 h-4" />
                    </button>
                  )}
                  <button
                    onClick={() => handleDownload(doc.id)}
                    className="p-1.5 rounded-lg border border-navy-700 hover:border-blue-500/40 hover:bg-blue-950/20 text-slate-400 hover:text-blue-400 transition-colors"
                    title="Download file"
                  >
                    <Download className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(doc.id)}
                    className="p-1.5 rounded-lg border border-navy-700 hover:border-red-500/40 hover:bg-red-950/20 text-slate-400 hover:text-red-400 transition-colors"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Inspect Chunks Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-navy-950/80 backdrop-blur-sm">
          <div className="bg-navy-900 border border-navy-700 rounded-2xl w-full max-w-3xl max-h-[85vh] flex flex-col shadow-2xl">
            <div className="p-5 border-b border-navy-800 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-white flex items-center space-x-2">
                  <FileText className="w-4 h-4 text-cyan-400" />
                  <span>Document Chunks: {selectedDoc.title}</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Showing {chunks.length} vectorized semantic chunks used for context injection.
                </p>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="text-slate-400 hover:text-white"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-5 overflow-y-auto space-y-4 flex-1">
              {isLoadingChunks ? (
                <div className="py-12 flex flex-col items-center justify-center text-slate-400 space-y-2">
                  <Loader2 className="w-6 h-6 animate-spin text-cyan-400" />
                  <p className="text-xs">Loading chunks...</p>
                </div>
              ) : chunks.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-8">No chunks found.</p>
              ) : (
                chunks.map((chunk) => (
                  <div
                    key={chunk.id}
                    className="p-4 rounded-xl border border-navy-800 bg-navy-950/60 space-y-2"
                  >
                    <div className="flex items-center justify-between text-[11px] text-slate-400 pb-2 border-b border-navy-800/60">
                      <span className="font-mono text-cyan-400">Chunk #{chunk.chunk_index + 1}</span>
                      <div className="flex items-center space-x-3">
                        {chunk.section_title && (
                          <span className="text-slate-300 font-semibold truncate max-w-xs">
                            Section: {chunk.section_title}
                          </span>
                        )}
                        <span className="font-mono text-slate-500">~{chunk.token_count} tokens</span>
                      </div>
                    </div>
                    <p className="text-xs text-slate-200 whitespace-pre-wrap leading-relaxed font-mono">
                      {chunk.content}
                    </p>
                  </div>
                ))
              )}
            </div>

            <div className="p-4 border-t border-navy-800 flex justify-end">
              <button
                onClick={() => setSelectedDoc(null)}
                className="px-4 py-2 rounded-lg bg-navy-800 hover:bg-navy-700 text-xs font-semibold text-white transition-colors"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
