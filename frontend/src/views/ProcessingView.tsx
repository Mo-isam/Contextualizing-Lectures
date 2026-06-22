import React, { useEffect, useState, useRef } from "react";
import { Loader2, AlertCircle, RefreshCw } from "lucide-react";
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

      if (data.status === "processing" && data.stage) {
        const stage = data.stage;
        const progress = data.progress ?? 0;
        const message = data.message ?? "";

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
      ws = new WebSocket(wsUrl);
      activeSocket = ws;

      ws.onopen = () => {
        // Send the configuration to the server
        ws.send(JSON.stringify(config));
      };

      ws.onmessage = handleMessage;
      ws.onerror = handleError;
      ws.onclose = handleClose;
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
                  ? "bg-blue-500/5 border-blue-500/30 shadow-md shadow-blue-500/5"
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
                      : "bg-gradient-to-r from-blue-500 to-purple-400"
                  }`}
                  style={{ width: `${stage.progress * 100}%` }}
                ></div>
              </div>
              
              <div className="mt-2 text-[10px] text-gray-400 font-mono truncate pl-0.5">
                {stage.done ? (
                  <span className="text-green-400 font-semibold">✓ Completed</span>
                ) : stage.active ? (
                  <span className="text-blue-400 animate-pulse">{stage.message}</span>
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
  );
};
