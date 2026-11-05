"use client";

import { useState, useRef, useEffect } from "react";
import {
  Mic,
  MicOff,
  Volume2,
  VolumeX,
  Sparkles,
  Send,
  Loader2,
  MessageSquare,
  RefreshCw,
  Radio,
  FileAudio,
} from "lucide-react";
import { api } from "@/lib/api";

interface VoiceMessage {
  id: string;
  sender: "user" | "assistant";
  text: string;
  audioBase64?: string | null;
  audioMimeType?: string;
  citations?: Array<{ source_id: string; title: string; type: string }>;
  timestamp: string;
}

export default function VoiceAssistantPage() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);
  const [selectedVoice, setSelectedVoice] = useState("alloy");
  const [textInput, setTextInput] = useState("");
  const [messages, setMessages] = useState<VoiceMessage[]>([
    {
      id: "welcome",
      sender: "assistant",
      text: "Hello! I am your AI MemoryVerse voice assistant. Speak or type a question to retrieve and synthesize your knowledge vault.",
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    },
  ]);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const activeAudioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (activeAudioRef.current) activeAudioRef.current.pause();
    };
  }, []);

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
        stream.getTracks().forEach((track) => track.stop());
        await processAudioQuery(audioBlob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setRecordDuration(0);

      timerRef.current = setInterval(() => {
        setRecordDuration((prev) => prev + 1);
      }, 1000);
    } catch (err) {
      console.warn("Microphone access denied or unavailable; fallback to text input.", err);
      alert("Microphone permission was not granted or audio input is unavailable. You can use the text input below to test voice interactions.");
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
      if (timerRef.current) clearInterval(timerRef.current);
    }
  };

  const processAudioQuery = async (audioBlob: Blob) => {
    setIsProcessing(true);
    try {
      // 1. Transcribe audio
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.webm");

      const transRes = await fetch(
        `${process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1"}/voice/transcribe`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${localStorage.getItem("access_token") || ""}`,
            "X-Workspace-ID": localStorage.getItem("active_workspace_id") || "",
          },
          body: formData,
        }
      );
      const transJson = await transRes.json();
      const transcribedText = transJson?.data?.text || "What are my latest memories?";

      await handleVoiceQuery(transcribedText);
    } catch (err) {
      console.error("Audio processing failed", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleVoiceQuery = async (query: string) => {
    if (!query.trim()) return;

    const userMsg: VoiceMessage = {
      id: String(Date.now()),
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };
    setMessages((prev) => [...prev, userMsg]);
    setTextInput("");
    setIsProcessing(true);

    try {
      const res = await api.post("/voice/chat", {
        query: query,
        voice: selectedVoice,
      });

      if (res.success && res.data) {
        const assistantMsg: VoiceMessage = {
          id: String(Date.now() + 1),
          sender: "assistant",
          text: res.data.assistant_response,
          audioBase64: res.data.audio_base64,
          audioMimeType: res.data.audio_mime_type || "audio/wav",
          citations: res.data.citations,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        };
        setMessages((prev) => [...prev, assistantMsg]);

        // Auto play audio response if available
        if (res.data.audio_base64) {
          playAudio(res.data.audio_base64, res.data.audio_mime_type || "audio/wav");
        }
      }
    } finally {
      setIsProcessing(false);
    }
  };

  const playAudio = (b64: string, mime: string) => {
    try {
      if (activeAudioRef.current) {
        activeAudioRef.current.pause();
      }
      const audioUrl = `data:${mime};base64,${b64}`;
      const audio = new Audio(audioUrl);
      activeAudioRef.current = audio;
      setIsPlayingAudio(true);

      audio.onended = () => setIsPlayingAudio(false);
      audio.onerror = () => setIsPlayingAudio(false);
      audio.play().catch((e) => console.log("Audio playback prevented by browser autoplay policy", e));
    } catch (e) {
      console.error("Audio play error", e);
    }
  };

  const stopAudio = () => {
    if (activeAudioRef.current) {
      activeAudioRef.current.pause();
      setIsPlayingAudio(false);
    }
  };

  const formatTimer = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Radio className="h-6 w-6 text-purple-400" />
            Voice Intelligence Assistant
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Hands-free conversational AI grounded in your personal memory vault with ultra-fast speech synthesis.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <label className="text-xs text-slate-400 font-medium">Voice Model:</label>
          <select
            value={selectedVoice}
            onChange={(e) => setSelectedVoice(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-300 focus:outline-none focus:border-purple-500"
          >
            <option value="alloy">Alloy (Balanced)</option>
            <option value="echo">Echo (Authoritative)</option>
            <option value="fable">Fable (Narrative)</option>
            <option value="nova">Nova (Energetic)</option>
            <option value="shimmer">Shimmer (Expressive)</option>
          </select>
        </div>
      </div>

      {/* Main Voice Interactive Sphere */}
      <div className="rounded-2xl border border-slate-800 bg-slate-950/80 p-8 flex flex-col items-center justify-center relative overflow-hidden shadow-2xl">
        {/* Visual Pulse Waves */}
        <div className="relative flex items-center justify-center my-6">
          {isRecording && (
            <>
              <div className="absolute w-48 h-48 rounded-full bg-rose-500/20 animate-ping" />
              <div className="absolute w-36 h-36 rounded-full bg-rose-500/30 animate-pulse" />
            </>
          )}

          {isPlayingAudio && !isRecording && (
            <>
              <div className="absolute w-48 h-48 rounded-full bg-purple-500/20 animate-ping" />
              <div className="absolute w-36 h-36 rounded-full bg-purple-500/30 animate-pulse" />
            </>
          )}

          {isProcessing && (
            <div className="absolute w-44 h-44 rounded-full border border-purple-500/40 border-t-purple-400 animate-spin" />
          )}

          <button
            onClick={isRecording ? stopRecording : startRecording}
            disabled={isProcessing}
            className={`relative z-10 w-24 h-24 rounded-full flex flex-col items-center justify-center shadow-2xl transition-all duration-300 ${
              isRecording
                ? "bg-rose-600 hover:bg-rose-500 text-white scale-110 shadow-rose-900/50"
                : "bg-gradient-to-tr from-purple-700 to-indigo-600 hover:scale-105 text-white shadow-purple-900/50"
            }`}
          >
            {isProcessing ? (
              <Loader2 className="h-8 w-8 animate-spin" />
            ) : isRecording ? (
              <MicOff className="h-8 w-8" />
            ) : (
              <Mic className="h-8 w-8" />
            )}
          </button>
        </div>

        {/* Status text */}
        <div className="text-center">
          {isRecording ? (
            <div className="flex items-center gap-2 text-rose-400 font-semibold text-sm">
              <span className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
              Recording... {formatTimer(recordDuration)} (Click to send)
            </div>
          ) : isProcessing ? (
            <div className="flex items-center gap-2 text-purple-400 font-medium text-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              Searching memories & synthesizing speech...
            </div>
          ) : isPlayingAudio ? (
            <div className="flex items-center gap-3 text-purple-300 font-medium text-sm">
              <Volume2 className="h-4 w-4 animate-bounce" />
              Speaking response...
              <button
                onClick={stopAudio}
                className="text-xs text-slate-400 hover:text-white underline ml-2"
              >
                Mute
              </button>
            </div>
          ) : (
            <p className="text-xs text-slate-400">
              Tap the microphone to speak, or use the quick query bar below.
            </p>
          )}
        </div>
      </div>

      {/* Transcript & Conversation Log */}
      <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
          <MessageSquare className="h-4 w-4 text-purple-400" />
          Transcript & Audio Exchange
        </h3>

        <div className="space-y-4 max-h-[380px] overflow-y-auto pr-2">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === "user" ? "items-end" : "items-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl p-4 text-sm leading-relaxed ${
                  msg.sender === "user"
                    ? "bg-purple-600 text-white rounded-br-none"
                    : "bg-slate-950 border border-slate-800 text-slate-200 rounded-bl-none"
                }`}
              >
                <div className="flex items-center justify-between gap-4 mb-1">
                  <span className="text-[10px] font-semibold tracking-wider uppercase opacity-75">
                    {msg.sender === "user" ? "You (Voice Input)" : "MemoryVerse AI"}
                  </span>
                  <span className="text-[10px] opacity-60">{msg.timestamp}</span>
                </div>

                <p className="whitespace-pre-wrap">{msg.text}</p>

                {msg.citations && msg.citations.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-800/80 flex flex-wrap gap-1.5">
                    <span className="text-[10px] text-slate-400 uppercase font-semibold mr-1">
                      Grounded Sources:
                    </span>
                    {msg.citations.map((c, idx) => (
                      <span
                        key={idx}
                        className="text-[10px] bg-purple-500/10 border border-purple-500/20 text-purple-300 px-2 py-0.5 rounded-full"
                      >
                        [{idx + 1}] {c.title}
                      </span>
                    ))}
                  </div>
                )}

                {msg.audioBase64 && (
                  <div className="mt-3 pt-2 border-t border-slate-800/80 flex items-center gap-2">
                    <button
                      onClick={() =>
                        playAudio(msg.audioBase64!, msg.audioMimeType || "audio/wav")
                      }
                      className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-medium rounded-lg bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 transition-all"
                    >
                      <Volume2 className="h-3.5 w-3.5" />
                      Replay Voice
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleVoiceQuery(textInput);
          }}
          className="pt-2 flex items-center gap-2"
        >
          <input
            type="text"
            placeholder="Or type a question for the voice assistant..."
            value={textInput}
            onChange={(e) => setTextInput(e.target.value)}
            disabled={isProcessing}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
          <button
            type="submit"
            disabled={isProcessing || !textInput.trim()}
            className="px-4 py-2.5 rounded-xl bg-purple-600 text-white font-medium hover:bg-purple-500 transition-all disabled:opacity-50 flex items-center gap-2"
          >
            {isProcessing ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}

