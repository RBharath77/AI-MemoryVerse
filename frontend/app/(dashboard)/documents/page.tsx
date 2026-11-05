"use client";

import { useEffect, useState } from "react";
import {
  FileText,
  Upload,
  Search,
  FileSpreadsheet,
  FileCode,
  FileCheck,
  Clock,
  Trash2,
  RefreshCw,
  Loader2,
  CheckCircle2,
  AlertCircle,
  Plus,
} from "lucide-react";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { useAuthStore } from "@/store/auth-store";

interface DocumentItem {
  id: string;
  name: string;
  mime_type: string;
  size_bytes: number;
  status: "QUEUED" | "PROCESSING" | "READY" | "FAILED";
  chunk_count: number;
  created_at: string;
}

export default function DocumentLibraryPage() {
  const { activeWorkspaceId } = useAuthStore();
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadSuccessMessage, setUploadSuccessMessage] = useState<string | null>(null);

  useEffect(() => {
    setIsLoading(false);
  }, [activeWorkspaceId]);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "READY":
        return "bg-emerald-950/80 border-emerald-500/30 text-emerald-400";
      case "PROCESSING":
        return "bg-cyan-950/80 border-cyan-500/30 text-cyan-400 animate-pulse";
      case "QUEUED":
        return "bg-amber-950/80 border-amber-500/30 text-amber-400";
      case "FAILED":
        return "bg-red-950/80 border-red-500/30 text-red-400";
      default:
        return "bg-navy-950 border-navy-700 text-slate-400";
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
            Securely upload and parse heterogeneous documents into vectorized chunks for RAG.
          </p>
        </div>

        <label className="px-4 py-2 rounded-lg bg-blue-500 hover:bg-blue-400 text-white font-semibold text-xs flex items-center justify-center space-x-2 shadow-lg shadow-blue-500/20 transition-colors cursor-pointer">
          <Upload className="w-4 h-4" />
          <span>Upload Document</span>
          <input
            type="file"
            className="hidden"
            accept=".pdf,.docx,.xlsx,.pptx,.txt,.md,.csv"
            onChange={(e) => {
              if (e.target.files && e.target.files[0]) {
                const file = e.target.files[0];
                setIsUploading(true);
                setTimeout(() => {
                  const newDoc: DocumentItem = {
                    id: Math.random().toString(),
                    name: file.name,
                    mime_type: file.type || "application/octet-stream",
                    size_bytes: file.size,
                    status: "READY",
                    chunk_count: Math.max(1, Math.floor(file.size / 1500)),
                    created_at: new Date().toISOString(),
                  };
                  setDocuments([newDoc, ...documents]);
                  setIsUploading(false);
                  setUploadSuccessMessage(`Successfully ingested "${file.name}"!`);
                  setTimeout(() => setUploadSuccessMessage(null), 4000);
                }, 800);
              }
            }}
          />
        </label>
      </div>

      {uploadSuccessMessage && (
        <div className="p-4 rounded-xl border border-emerald-500/30 bg-emerald-950/40 text-emerald-300 text-xs flex items-center space-x-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{uploadSuccessMessage}</span>
        </div>
      )}

      {/* Upload Drag & Drop Area */}
      <div className="border-2 border-dashed border-navy-800 hover:border-blue-500/40 rounded-2xl p-8 bg-navy-900/30 text-center transition-colors">
        <div className="w-12 h-12 rounded-xl bg-blue-950/80 border border-blue-500/30 flex items-center justify-center mx-auto mb-3 text-blue-400">
          <Upload className="w-6 h-6" />
        </div>
        <h3 className="text-sm font-bold text-white mb-1">
          Drag and drop documents here
        </h3>
        <p className="text-xs text-slate-400 max-w-sm mx-auto mb-4">
          Supported formats: PDF, DOCX, XLSX, PPTX, Markdown, TXT, and CSV (Up to 25MB).
        </p>
      </div>

      {/* Document List */}
      <div className="bg-navy-900/40 border border-navy-800 rounded-2xl overflow-hidden">
        <div className="p-4 border-b border-navy-800 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">
            Ingested Documents ({documents.length})
          </h3>
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search documents..."
              className="w-full pl-8 pr-3 py-1.5 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white placeholder-slate-500 focus:outline-none"
            />
          </div>
        </div>

        {documents.length === 0 ? (
          <div className="py-16 text-center text-slate-400">
            <FileText className="w-8 h-8 mx-auto mb-3 opacity-40" />
            <p className="text-xs">No documents uploaded yet in this workspace.</p>
          </div>
        ) : (
          <div className="divide-y divide-navy-800">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="p-4 flex items-center justify-between hover:bg-navy-800/40 transition-colors"
              >
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-lg bg-navy-950 border border-navy-700 flex items-center justify-center text-blue-400">
                    <FileText className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-xs font-semibold text-white">{doc.name}</h4>
                    <p className="text-[10px] text-slate-500">
                      {formatFileSize(doc.size_bytes)} &bull; {doc.chunk_count} chunks &bull;{" "}
                      {formatDate(doc.created_at)}
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-3">
                  <span
                    className={`text-[10px] font-bold uppercase px-2.5 py-0.5 rounded border ${getStatusBadge(
                      doc.status
                    )}`}
                  >
                    {doc.status}
                  </span>
                  <button
                    onClick={() => setDocuments(documents.filter((d) => d.id !== doc.id))}
                    className="p-1 rounded text-slate-500 hover:text-red-400"
                    title="Delete document"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

