import React, { useEffect, useState } from "react";
import { FolderOpen, Sparkles, BookOpen, Clock, Play } from "lucide-react";
import type { SavedSessionInfo } from "../types";

interface HomeViewProps {
  onNewSession: () => void;
  onLoadSession: (filename: string) => void;
}

export const HomeView: React.FC<HomeViewProps> = ({ onNewSession, onLoadSession }) => {
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
    <div className="max-w-6xl mx-auto py-12 px-6 animate-fade-in">
      <div className="text-center mb-16">
        <h1 className="text-5xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-purple-400 to-blue-500 bg-clip-text text-transparent leading-normal">
          Contextualizing Lectures
        </h1>
        <p className="text-gray-400 mt-4 text-lg max-w-xl mx-auto opacity-85">
          Bridge static slide PDFs with dynamic spoken insights using multimodal AI alignment.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto mb-16">
        {/* New Session CTA Card */}
        <div className="bg-gradient-to-br from-[#161b22] to-[#0d1117] border border-blue-500/20 hover:border-blue-500/40 rounded-2xl p-8 transition-all hover:-translate-y-1 shadow-lg hover:shadow-blue-500/10 flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center text-blue-400 mb-6">
              <Sparkles className="w-6 h-6" />
            </div>
            <h3 className="text-2xl font-bold text-gray-100 mb-2">New Lecture</h3>
            <p className="text-gray-400 text-sm leading-relaxed mb-8">
              Upload a slide PDF (or PPTX) and an audio/video recording to align, annotate, and analyze slide-by-slide concepts.
            </p>
          </div>
          <button
            onClick={onNewSession}
            className="w-full py-3 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-semibold rounded-xl shadow-lg hover:shadow-blue-500/20 transition-all cursor-pointer"
          >
            Create New Session
          </button>
        </div>

        {/* Load Session CTA Card */}
        <div className="bg-gradient-to-br from-[#161b22] to-[#0d1117] border border-purple-500/20 rounded-2xl p-8 flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400 mb-6">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="text-2xl font-bold text-gray-100 mb-2">Saved Library</h3>
            <p className="text-gray-400 text-sm leading-relaxed mb-8">
              Select and reopen a previously aligned lecture session from your local persistent database cache.
            </p>
          </div>
          <div className="text-xs text-gray-500 text-center italic py-3 bg-gray-900/40 rounded-xl border border-gray-800">
            Select a session from the list below to load
          </div>
        </div>
      </div>

      {/* Library Sections */}
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-2 border-b border-gray-800 pb-4 mb-6">
          <FolderOpen className="w-5 h-5 text-blue-400" />
          <h2 className="text-xl font-bold text-gray-200">Session Library</h2>
        </div>

        {loading ? (
          <div className="flex justify-center items-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
            <span className="ml-3 text-gray-400 text-sm">Loading library...</span>
          </div>
        ) : error ? (
          <div className="text-center py-8 text-red-400 bg-red-950/20 border border-red-900/30 rounded-xl">
            Error loading sessions: {error}
          </div>
        ) : sessions.length === 0 ? (
          <div className="text-center py-12 text-gray-500 border border-dashed border-gray-800 rounded-xl bg-gray-950/10">
            <FolderOpen className="w-12 h-12 mx-auto text-gray-700 mb-3" />
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
    </div>
  );
};
