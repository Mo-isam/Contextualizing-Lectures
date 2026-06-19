import React, { useEffect, useState } from "react";
import { FolderOpen, Clock, Play, ArrowLeft } from "lucide-react";
import type { SavedSessionInfo } from "../types";

interface LibraryViewProps {
  onBack: () => void;
  onLoadSession: (filename: string) => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onBack, onLoadSession }) => {
  const [sessions, setSessions] = useState<SavedSessionInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/sessions")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch sessions");
        return res.json();
      })
      .then((data) => {
        setSessions(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const formatDate = (timestamp: number) => {
    if (!timestamp) return "Unknown date";
    return new Date(timestamp * 1000).toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  return (
    <div className="max-w-4xl mx-auto py-10 px-6 animate-fade-in">
      {/* Header Bar */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-gray-800">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 hover:border-gray-700 text-gray-300 font-medium text-sm transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </button>
      </div>

      <div className="flex items-center gap-3 mb-6">
        <div className="w-10 h-10 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400">
          <FolderOpen className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-3xl font-extrabold text-gray-100">Saved Library</h1>
          <p className="text-gray-400 text-xs mt-0.5">
            Select and reopen a previously aligned lecture session from local persistent storage.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
          <span className="ml-3 text-gray-400 text-sm">Loading library...</span>
        </div>
      ) : error ? (
        <div className="text-center py-10 text-red-400 bg-red-950/20 border border-red-900/30 rounded-xl">
          Error loading sessions: {error}
        </div>
      ) : sessions.length === 0 ? (
        <div className="text-center py-20 text-gray-500 border border-dashed border-gray-800 rounded-xl bg-gray-950/10">
          <FolderOpen className="w-16 h-16 mx-auto text-gray-700 mb-4" />
          <p className="font-semibold text-gray-400 mb-1">No sessions found</p>
          <p className="text-xs">Your aligned sessions library is currently empty.</p>
        </div>
      ) : (
        <div className="grid sm:grid-cols-2 gap-6">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="bg-[#121820]/90 border border-gray-800/80 hover:border-blue-500/30 rounded-xl p-5 transition-all hover:bg-[#151c27] flex flex-col justify-between group"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h4 className="font-bold text-gray-200 group-hover:text-blue-400 transition-colors text-base truncate">
                    {session.pipeline_type === "visual" ? "🎞️ " : "🎙️ "}
                    {session.name}
                  </h4>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-800 border border-gray-700 text-gray-400 capitalize">
                    {session.pipeline_type} pipeline
                  </span>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-gray-500 mb-3">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Edited: {formatDate(session.timestamp)}</span>
                </div>
                <p className="text-gray-400 text-xs leading-relaxed line-clamp-2 min-h-[2.5rem] mb-4">
                  {session.description || "No description provided."}
                </p>
              </div>
              <button
                onClick={() => onLoadSession(session.filename)}
                className="w-full py-2.5 bg-gray-800 hover:bg-blue-600 text-gray-200 hover:text-white font-medium rounded-lg text-xs transition-all flex items-center justify-center gap-2 group-hover:bg-blue-600/90 cursor-pointer"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                Open Session
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
