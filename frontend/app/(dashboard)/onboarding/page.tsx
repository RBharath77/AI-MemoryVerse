"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Brain,
  Sparkles,
  ArrowRight,
  CheckCircle2,
  Vault,
  MessageSquare,
  Shield,
  Loader2,
} from "lucide-react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/store/auth-store";

export default function OnboardingPage() {
  const router = useRouter();
  const { user, updateUser } = useAuthStore();

  const [step, setStep] = useState(1);
  const [bio, setBio] = useState("");
  const [aiInstructions, setAiInstructions] = useState(
    "Be concise, source-grounded, and maintain persistent memory context."
  );
  const [firstMemory, setFirstMemory] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleNextStep = async () => {
    if (step === 1) {
      setStep(2);
    } else if (step === 2) {
      setStep(3);
    } else if (step === 3) {
      setIsSubmitting(true);
      // Save profile instructions and first memory
      await api.patch("/users/me", {
        profile: {
          bio,
          ai_custom_instructions: aiInstructions,
        },
      });

      if (firstMemory.trim()) {
        await api.post("/memories", {
          content: firstMemory.trim(),
          category: "preference",
          importance: 8,
          tags: ["onboarding", "preference"],
        });
      }

      updateUser({
        profile: {
          bio,
          avatar_url: "",
          ai_custom_instructions: aiInstructions,
          preferences: {},
        },
      });

      setIsSubmitting(false);
      setStep(4);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-6">
      <div className="max-w-xl w-full bg-navy-900/60 border border-navy-800 rounded-3xl p-8 sm:p-10 shadow-2xl backdrop-blur space-y-6">
        {/* Step indicator */}
        <div className="flex items-center justify-between pb-6 border-b border-navy-800">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain className="w-4 h-4 text-white" />
            </div>
            <span className="font-bold text-sm text-white">AI-MemoryVerse Setup</span>
          </div>
          <span className="text-xs font-mono text-cyan-400">Step {step} of 4</span>
        </div>

        {/* Step 1: Personalization */}
        {step === 1 && (
          <div className="space-y-4">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-cyan-950/60 border border-cyan-500/30 text-cyan-400 text-xs font-semibold">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Personalize Your Experience</span>
            </div>
            <h2 className="text-xl font-bold text-white">
              Welcome, {user?.full_name || "Explorer"}!
            </h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Tell your assistant what you do so it can tailor its reasoning, summaries, and memory extraction to your field.
            </p>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Your Role or Focus Area
              </label>
              <input
                type="text"
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                placeholder="e.g. Software Engineer & AI Researcher"
                className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        )}

        {/* Step 2: AI Personality Instructions */}
        {step === 2 && (
          <div className="space-y-4">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-violet-950/60 border border-violet-500/30 text-violet-400 text-xs font-semibold">
              <Brain className="w-3.5 h-3.5" />
              <span>Define AI Guardrails</span>
            </div>
            <h2 className="text-xl font-bold text-white">Set Persistent Guidelines</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              How would you like your AI assistant to communicate and reason across all conversations?
            </p>
            <div>
              <textarea
                rows={4}
                value={aiInstructions}
                onChange={(e) => setAiInstructions(e.target.value)}
                className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        )}

        {/* Step 3: First Memory */}
        {step === 3 && (
          <div className="space-y-4">
            <div className="inline-flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-emerald-950/60 border border-emerald-500/30 text-emerald-400 text-xs font-semibold">
              <Vault className="w-3.5 h-3.5" />
              <span>Seed Your Memory Vault</span>
            </div>
            <h2 className="text-xl font-bold text-white">Add Your First Memory</h2>
            <p className="text-xs text-slate-400 leading-relaxed">
              Save a fact, preference, or project rule. Unlike ordinary chatbots, AI-MemoryVerse will remember this permanently.
            </p>
            <div>
              <textarea
                rows={3}
                value={firstMemory}
                onChange={(e) => setFirstMemory(e.target.value)}
                placeholder="e.g. My primary architecture stack is FastAPI, Next.js, and PostgreSQL with pgvector."
                className="w-full p-3 bg-navy-950 border border-navy-700 rounded-lg text-xs text-white focus:outline-none focus:border-cyan-500"
              />
            </div>
          </div>
        )}

        {/* Step 4: Completion */}
        {step === 4 && (
          <div className="space-y-4 text-center py-6">
            <div className="w-14 h-14 rounded-2xl bg-emerald-950/80 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-white">External Brain Initialized!</h2>
            <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
              Your memory vault, AI instructions, and workspace multi-tenancy are fully configured and ready for live retrieval.
            </p>
            <button
              onClick={() => router.push("/dashboard")}
              className="mt-4 px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold text-xs shadow-lg shadow-cyan-500/20 transition-all inline-flex items-center space-x-2"
            >
              <span>Go to Overview Dashboard</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        )}

        {step < 4 && (
          <div className="flex items-center justify-end pt-4 border-t border-navy-800">
            <button
              onClick={handleNextStep}
              disabled={isSubmitting}
              className="px-6 py-2.5 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-navy-950 font-bold text-xs flex items-center space-x-2 transition-colors disabled:opacity-50 shadow-md shadow-cyan-500/20"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Configuring...</span>
                </>
              ) : (
                <>
                  <span>Continue</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

