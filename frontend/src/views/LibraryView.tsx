import React, { useEffect, useState } from "react";
import { FolderOpen, Clock, Play, ArrowLeft, MoreVertical, Edit, Trash2 } from "lucide-react";
import type { SavedSessionInfo } from "../types";
import { ApiService } from "../services/api";

interface LibraryViewProps {
  onBack: () => void;
  onLoadSession: (filename: string) => void;
}

export const LibraryView: React.FC<LibraryViewProps> = ({ onBack, onLoadSession }) => {
  const [sessions, setSessions] = useState<SavedSessionInfo[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Card action states
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  
  // Edit dialog state
  const [editSession, setEditSession] = useState<SavedSessionInfo | null>(null);
  const [editName, setEditName] = useState<string>("");
  const [editDesc, setEditDesc] = useState<string>("");
  const [saving, setSaving] = useState<boolean>(false);

  useEffect(() => {
    ApiService.getSessions()
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

  const handleEditClick = (session: SavedSessionInfo) => {
    setActiveDropdown(null);
    setEditSession(session);
    setEditName(session.name);
    setEditDesc(session.description);
  };

  const handleUpdateMetadata = async () => {
    if (!editSession || !editName.trim()) return;
    setSaving(true);
    try {
      await ApiService.updateSessionMetadata(editSession.filename, editName, editDesc);
      
      // Update local state list instantly
      setSessions((prev) =>
        prev.map((s) =>
          s.filename === editSession.filename
            ? { ...s, name: editName, description: editDesc, timestamp: Date.now() / 1000 }
            : s
        )
      );
      setEditSession(null);
    } catch (err: any) {
      alert(`Update error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClick = async (session: SavedSessionInfo) => {
    setActiveDropdown(null);
    if (!confirm(`Are you sure you want to permanently delete "${session.name}"?`)) {
      return;
    }
    
    try {
      await ApiService.deleteSession(session.filename);
      // Remove from local list instantly
      setSessions((prev) => prev.filter((s) => s.filename !== session.filename));
    } catch (err: any) {
      alert(`Delete error: ${err.message}`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-10 px-6 animate-fade-in relative">
      {/* Invisible backdrop to dismiss active dropdowns */}
      {activeDropdown && (
        <div 
          className="fixed inset-0 z-10" 
          onClick={() => setActiveDropdown(null)}
        />
      )}

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
              className="bg-[#121820]/90 border border-gray-800/80 hover:border-blue-500/30 rounded-xl p-5 transition-all hover:bg-[#151c27] flex flex-col justify-between group relative"
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-2">
                  <h4 className="font-bold text-gray-200 group-hover:text-blue-400 transition-colors text-base truncate flex-1">
                    {session.pipeline_type === "visual" ? "🎞️ " : "🎙️ "}
                    {session.name}
                  </h4>
                  
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-gray-800 border border-gray-700 text-gray-400 capitalize">
                      {session.pipeline_type}
                    </span>
                    
                    {/* Action Dropdown Menu */}
                    <div className="relative">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveDropdown(activeDropdown === session.filename ? null : session.filename);
                        }}
                        className="p-1 rounded-lg text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors cursor-pointer relative z-20"
                      >
                        <MoreVertical className="w-4 h-4" />
                      </button>
                      {activeDropdown === session.filename && (
                        <div className="absolute right-0 mt-1 w-36 bg-gray-900 border border-gray-800 rounded-lg shadow-xl py-1 z-30 animate-fade-in">
                          <button
                            onClick={() => handleEditClick(session)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-gray-300 hover:bg-gray-800 hover:text-white transition-colors text-left"
                          >
                            <Edit className="w-3.5 h-3.5 text-blue-400" />
                            Edit Details
                          </button>
                          <button
                            onClick={() => handleDeleteClick(session)}
                            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-400 hover:bg-red-500/10 transition-colors text-left"
                          >
                            <Trash2 className="w-3.5 h-3.5 text-red-500" />
                            Delete Session
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
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

      {/* Edit Session Modal */}
      {editSession && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#121820] border border-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-4">
            <h3 className="text-xl font-bold text-gray-100 flex items-center gap-2">
              <Edit className="w-5 h-5 text-blue-400" />
              Edit Session Details
            </h3>
            <p className="text-xs text-gray-400">
              Update the name and description for this lecture session.
            </p>

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-gray-400 pl-1">Session Name</label>
                <input
                  type="text"
                  value={editName}
                  onChange={(e) => setEditName(e.target.value)}
                  className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs text-gray-200 rounded-xl px-4 py-3 outline-none transition-all font-medium"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-gray-400 pl-1">Description</label>
                <textarea
                  value={editDesc}
                  onChange={(e) => setEditDesc(e.target.value)}
                  rows={3}
                  className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs text-gray-200 rounded-xl px-4 py-3 outline-none transition-all leading-normal"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setEditSession(null)}
                disabled={saving}
                className="px-4 py-2 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-lg text-xs font-semibold cursor-pointer transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                onClick={handleUpdateMetadata}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold cursor-pointer transition-all flex items-center gap-1.5 shadow-lg shadow-blue-600/10 disabled:opacity-40"
              >
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
