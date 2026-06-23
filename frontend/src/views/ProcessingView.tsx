import React, { useEffect, useState, useRef } from "react";
import { Loader2, AlertCircle, RefreshCw, Cpu, ChevronUp, ChevronDown } from "lucide-react";
import type { ProgressUpdate } from "../types";
import { ApiService } from "../services/api";

interface ProcessingViewProps {
  config: any;
  onComplete: (data: any) => void;
  onCancel: () => void;
}

interface StageProgress {
  title: string;
  progress: number;
  message: string;
  active: boolean;
  done: boolean;
}

// Module-level connection variables (survive unmount-remount in Strict Mode)
let activeSocket: WebSocket | null = null;
let closeTimeoutId: any = null;

export const ProcessingView: React.FC<ProcessingViewProps> = ({ config, onComplete, onCancel }) => {
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const [stages, setStages] = useState<Record<string, StageProgress>>({
    preflight: { title: "⚙️ System Pre-flight", progress: 0, message: "Waiting to start...", active: false, done: false },
    pdf: { title: "📄 Slide Text Extraction", progress: 0, message: "Waiting...", active: false, done: false },
    video: { title: "🎞️ Video Structural Mapping", progress: 0, message: "Waiting...", active: false, done: false },
    audio: { title: "🎙️ Audio Transcription", progress: 0, message: "Waiting...", active: false, done: false },
    alignment: { title: "🧠 Semantic Temporal Fusion", progress: 0, message: "Waiting...", active: false, done: false },
  });

  // Model Engine States
  const [modelsList, setModelsList] = useState<string[]>([]);
  const [activeModel, setActiveModel] = useState<string | null>(null);
  const [modelStatus, setModelStatus] = useState<"active" | "warning" | "error" | null>(null);
  const [modelMessage, setModelMessage] = useState<string | null>(null);
  const [deadModels, setDeadModels] = useState<string[]>([]);
  const [modelCallStats, setModelCallStats] = useState<Record<string, { success: number; failure: number }>>({});
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [lastNormalMessages, setLastNormalMessages] = useState<Record<string, string>>({});

  const isVisual = config.pipeline_mode === "visual";

  useEffect(() => {
    // Clear any pending socket closure from a recent unmount
    if (closeTimeoutId) {
      clearTimeout(closeTimeoutId);
      closeTimeoutId = null;
    }

    let ws = activeSocket;

    const handleMessage = (event: MessageEvent) => {
      const data: ProgressUpdate = JSON.parse(event.data);

      if (data.status === "processing") {
        if (data.models_list !== undefined) setModelsList(data.models_list);
        if (data.active_model !== undefined) setActiveModel(data.active_model);
        if (data.model_status !== undefined) setModelStatus(data.model_status);
        if (data.model_message !== undefined) setModelMessage(data.model_message);
        if (data.dead_models !== undefined) setDeadModels(data.dead_models);
        if (data.model_call_stats !== undefined && data.model_call_stats !== null) setModelCallStats(data.model_call_stats);

        if (data.stage) {
          const stage = data.stage;
          const progress = data.progress ?? 0;
          const message = data.message ?? "";

          // If the message is a normal status and not a technical retry/warning, store it
          const isWarning = message.startsWith("⏳") || message.startsWith("⚠️") || message.startsWith("❌");
          if (!isWarning && message.trim() !== "") {
            setLastNormalMessages((prev) => ({ ...prev, [stage]: message }));
          }

          setStages((prev) => {
            const next = { ...prev };
            
            // Mark previous stages as done
            const stageKeys = Object.keys(next);
            const currentIdx = stageKeys.indexOf(stage);
            
            stageKeys.forEach((key, idx) => {
              if (idx < currentIdx) {
                next[key] = { ...next[key], progress: 1, active: false, done: true, message: "Complete" };
              } else if (idx === currentIdx) {
                next[key] = { ...next[key], progress, active: true, done: progress >= 1, message };
              } else {
                next[key] = { ...next[key], active: false, done: false };
              }
            });

            return next;
          });
        }
      } else if (data.status === "complete" && data.data) {
        onComplete(data.data);
        if (activeSocket) {
          activeSocket.close();
          activeSocket = null;
        }
      } else if (data.status === "error") {
        setError(data.message || "An unexpected error occurred during execution.");
        if (activeSocket) {
          activeSocket.close();
          activeSocket = null;
        }
      }
    };

    const handleError = () => {
      setError("WebSocket connection error. Could not establish link to alignment server.");
    };

    const handleClose = () => {
      console.log("WebSocket connection closed.");
    };

    if (!ws || ws.readyState === WebSocket.CLOSED || ws.readyState === WebSocket.CLOSING) {
      const wsUrl = ApiService.getWebSocketUrl();
      const newWs = new WebSocket(wsUrl);
      ws = newWs;
      activeSocket = ws;

      newWs.onopen = () => {
        // Send the configuration to the server
        newWs.send(JSON.stringify(config));
      };

      newWs.onmessage = handleMessage;
      newWs.onerror = handleError;
      newWs.onclose = handleClose;
    } else {
      // Re-bind fresh handlers to point to the current closures
      ws.onmessage = handleMessage;
      ws.onerror = handleError;
      ws.onclose = handleClose;
    }

    socketRef.current = ws;

    return () => {
      // Delay closing to see if a remount (Strict Mode) happens immediately
      closeTimeoutId = setTimeout(() => {
        if (activeSocket) {
          activeSocket.close();
          activeSocket = null;
        }
        closeTimeoutId = null;
      }, 100);
    };
  }, [config, onComplete]);

  const handleCancel = () => {
    if (socketRef.current) {
      socketRef.current.close();
    }
    if (activeSocket) {
      activeSocket.close();
      activeSocket = null;
    }
    if (closeTimeoutId) {
      clearTimeout(closeTimeoutId);
      closeTimeoutId = null;
    }
    onCancel();
  };

  const getFlexHeader = (title: string, progress: number) => {
    return (
      <div className="flex justify-between font-semibold text-xs tracking-wider text-gray-300 uppercase mb-2">
        <span>{title}</span>
        <span className="text-blue-400 font-mono">{Math.round(progress * 100)}%</span>
      </div>
    );
  };

  return (
    <>
      <div className="max-w-xl mx-auto py-16 px-6 animate-fade-in">
      <div className="text-center mb-10">
        <Loader2 className="w-12 h-12 text-blue-400 animate-spin mx-auto mb-4" />
        <h1 className="text-3xl font-extrabold text-gray-100">Analyzing Lecture...</h1>
        <p className="text-gray-400 text-sm mt-2">
          Executing pipeline steps to fuse and align slides with transcript timeline.
        </p>
      </div>

      <div className="bg-[#121820]/90 border border-gray-800 rounded-2xl p-6 shadow-xl space-y-6">
        {/* Stages list */}
        {Object.entries(stages).map(([key, stage]) => {
          // If video mode is disabled, skip the video transition stage
          if (key === "video" && !isVisual) return null;

          return (
            <div
              key={key}
              className={`transition-all duration-300 rounded-xl p-4 border ${
                stage.active
                  ? modelStatus === "warning" || modelStatus === "error"
                    ? "bg-amber-500/5 border-amber-500/30 shadow-md shadow-amber-500/5"
                    : "bg-blue-500/5 border-blue-500/30 shadow-md shadow-blue-500/5"
                  : stage.done
                  ? "bg-green-500/5 border-green-500/20 opacity-80"
                  : "bg-gray-900/40 border-gray-800/80 opacity-55"
              }`}
            >
              {getFlexHeader(stage.title, stage.progress)}
              
              {/* Progress bar container */}
              <div className="w-full h-2.5 bg-gray-950 rounded-full overflow-hidden border border-gray-800">
                <div
                  className={`h-full transition-all duration-200 ease-out rounded-full ${
                    stage.done
                      ? "bg-gradient-to-r from-green-500 to-emerald-400"
                      : stage.active && (modelStatus === "warning" || modelStatus === "error")
                      ? "bg-gradient-to-r from-amber-500 to-yellow-400"
                      : "bg-gradient-to-r from-blue-500 to-purple-400"
                  }`}
                  style={{ width: `${stage.progress * 100}%` }}
                ></div>
              </div>
              
              <div className="mt-2 text-[10px] font-mono truncate pl-0.5">
                {stage.done ? (
                  <span className="text-green-400 font-semibold">✓ Completed</span>
                ) : stage.active ? (
                  modelStatus === "warning" || modelStatus === "error" ? (
                    <span className="text-amber-500 animate-pulse font-medium">
                      {lastNormalMessages[key] || "Processing..."} {
                        modelMessage?.toLowerCase().includes("pacing") ? "(⏳ Pacing...)" :
                        modelMessage?.toLowerCase().includes("swap") ? "(⚠️ Swapping...)" :
                        modelMessage?.toLowerCase().includes("safety") || modelMessage?.toLowerCase().includes("block") ? "(⚠️ Blocked...)" :
                        "(⚠️ Retrying...)"
                      }
                    </span>
                  ) : (
                    <span className="text-blue-400 animate-pulse">{stage.message}</span>
                  )
                ) : (
                  <span className="text-gray-600">{stage.message}</span>
                )}
              </div>
            </div>
          );
        })}

        {error && (
          <div className="bg-red-950/20 border border-red-900/30 rounded-xl p-4 flex items-start gap-3 text-red-400">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h5 className="font-bold text-xs">Pipeline Execution Failed</h5>
              <p className="text-[11px] leading-relaxed opacity-90">{error}</p>
            </div>
          </div>
        )}

        <button
          onClick={handleCancel}
          className="w-full py-3 bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-400 hover:text-gray-300 font-bold rounded-xl text-xs transition-all flex items-center justify-center gap-2 cursor-pointer mt-4"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Cancel / Restart
        </button>
      </div>
    </div>

      {/* Floating collapsible AI Engine widget */}
      {modelsList.length > 0 && (
        <div className="fixed bottom-6 left-6 right-6 md:right-auto md:left-8 md:bottom-8 z-50 select-none">
          <div className="relative">
            {/* Expanded panel (opens upwards) */}
            {isExpanded && (
              <div className="absolute bottom-14 left-0 w-full md:w-80 bg-gray-950/95 border border-gray-800/80 rounded-2xl p-4.5 shadow-2xl space-y-3.5 backdrop-blur-md animate-fade-in">
                <div className="flex items-center justify-between border-b border-gray-900 pb-2.5">
                  <h3 className="text-[10px] font-extrabold uppercase tracking-widest text-gray-400 flex items-center gap-2">
                    <Cpu className="w-3.5 h-3.5 text-gray-500" />
                    AI Pipeline Engine
                  </h3>
                  <button 
                    onClick={() => setIsExpanded(false)}
                    className="text-gray-500 hover:text-gray-400 text-[10px] uppercase font-bold tracking-wider cursor-pointer"
                  >
                    Hide
                  </button>
                </div>

                {/* Vertical Diagnostics Dashboard */}
                <div className="space-y-2 max-h-[220px] overflow-y-auto pr-1">
                  {modelsList.map((model) => {
                    const isCurrent = model === activeModel;
                    const isDead = deadModels.includes(model);
                    const stats = modelCallStats[model] || { success: 0, failure: 0 };
                    
                    let stateLabel = "Idle";
                    let badgeClass = "border-gray-800/50 text-gray-500 bg-gray-900/20";
                    let nameClass = "text-gray-400";
                    let cardClass = "bg-gray-900/20 border-gray-800/40";
                    
                    if (isDead) {
                      stateLabel = "Bypassed";
                      badgeClass = "border-gray-800/50 text-gray-500 bg-gray-900/20 line-through decoration-gray-600";
                      nameClass = "text-gray-400 line-through decoration-gray-600";
                      cardClass = "bg-gray-900/20 border-gray-800/40";
                    } else if (isCurrent) {
                      if (modelStatus === "active") {
                        stateLabel = "Active";
                        badgeClass = "border-emerald-500/30 text-emerald-400 bg-emerald-500/10 shadow-[0_0_8px_rgba(16,185,129,0.1)] font-bold";
                        nameClass = "text-emerald-400 font-bold";
                        cardClass = "bg-emerald-950/5 border-emerald-500/20 shadow-[0_0_12px_rgba(16,185,129,0.05)]";
                      } else if (modelStatus === "warning") {
                        stateLabel = "Pacing";
                        badgeClass = "border-amber-500/30 text-amber-400 bg-amber-500/10 animate-pulse font-bold";
                        nameClass = "text-amber-400 font-bold";
                        cardClass = "bg-amber-950/5 border-amber-500/20";
                      } else if (modelStatus === "error") {
                        stateLabel = "Swapping";
                        badgeClass = "border-amber-500/30 text-amber-400 bg-amber-500/10 font-bold";
                        nameClass = "text-amber-400 font-bold";
                        cardClass = "bg-amber-950/5 border-amber-500/20";
                      }
                    }

                    return (
                      <div 
                        key={model} 
                        className={`p-2.5 rounded-xl border transition-all duration-300 ${cardClass}`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className={`text-[10px] font-mono truncate ${nameClass}`}>
                            {model}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-[8px] uppercase tracking-wider border font-semibold ${badgeClass}`}>
                            {stateLabel}
                          </span>
                        </div>
                        
                        {/* Statistics row */}
                        <div className="flex items-center gap-3.5 mt-2 text-[9px] text-gray-400 font-medium font-sans">
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500"></span>
                            <span>{stats.success} successful</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-500"></span>
                            <span>{stats.failure} failed</span>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Pacing/Status details */}
                {modelMessage && (
                  <div className={`text-[10px] font-mono px-3 py-2 rounded-lg border leading-relaxed ${
                    modelStatus === "active" ? "bg-emerald-950/5 border-emerald-950/10 text-emerald-500/90" :
                    modelStatus === "warning" ? "bg-amber-950/10 border-amber-500/15 text-amber-400" :
                    modelStatus === "error" ? "bg-amber-950/10 border-amber-500/15 text-amber-400" : "bg-gray-900/50 border-gray-800/40 text-gray-500"
                  }`}>
                    {modelMessage}
                  </div>
                )}
              </div>
            )}

            {/* Collapsed Pill */}
            <div 
              onClick={() => setIsExpanded(!isExpanded)}
              className="backdrop-blur-md bg-gray-900/80 border border-gray-800 hover:border-gray-700/80 rounded-full py-2.5 px-4.5 flex items-center justify-between gap-3.5 cursor-pointer shadow-2xl hover:bg-gray-900/95 transition-all duration-300 w-full md:w-auto"
            >
              <div className="flex items-center gap-2.5">
                <span className="relative flex h-2.5 w-2.5">
                  {modelStatus === "active" && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  )}
                  {modelStatus === "warning" && (
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75"></span>
                  )}
                  <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                    modelStatus === "active" ? "bg-emerald-500" :
                    modelStatus === "warning" ? "bg-amber-500" :
                    modelStatus === "error" ? "bg-red-500" : "bg-gray-600"
                  }`}></span>
                </span>
                <span className="text-xs font-semibold text-gray-200">
                  {activeModel || "No Active Model"}
                </span>
              </div>
              <div className="flex items-center gap-1.5 border-l border-gray-800 pl-3">
                <span className={`text-[9px] font-extrabold uppercase tracking-widest ${
                  modelStatus === "active" ? "text-emerald-400" :
                  modelStatus === "warning" ? "text-amber-400" :
                  modelStatus === "error" ? "text-red-400" : "text-gray-500"
                }`}>
                  {modelStatus === "active" ? "Active" :
                   modelStatus === "warning" ? "Pacing" :
                   modelStatus === "error" ? "Swapping" : "Idle"}
                </span>
                {isExpanded ? (
                  <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
                ) : (
                  <ChevronUp className="w-3.5 h-3.5 text-gray-500" />
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
