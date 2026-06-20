import React, { useState } from "react";
import { ArrowLeft, Save, Download, Search, MessageSquare } from "lucide-react";
import { AudioPlayer } from "../components/AudioPlayer";
import { SlideViewer } from "../components/SlideViewer";
import { NoteCard } from "../components/NoteCard";
import type { AlignedNote, LectureSession } from "../types";
import { ApiService } from "../services/api";

interface StudioViewProps {
  session: LectureSession & { slide_images: string[] };
  onBack: () => void;
  onSaveCompleted: () => void;
}

export const StudioView: React.FC<StudioViewProps> = ({ session, onBack, onSaveCompleted }) => {
  const [activeSlide, setActiveSlide] = useState<number>(1);
  const [followMode, setFollowMode] = useState<boolean>(true);
  const [seekTo, setSeekTo] = useState<{ time: number; timestamp: number } | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>(``);
  const [, setCurrentTime] = useState<number>(0);

  // Dialog states
  const [showSaveDialog, setShowSaveDialog] = useState<boolean>(false);
  const [saveName, setSaveName] = useState<string>(session.session_name || "");
  const [saveDesc, setSaveDesc] = useState<string>(session.session_description || "");
  const [saving, setSaving] = useState<boolean>(false);

  const notes: AlignedNote[] = session.final_output || [];
  const slideImages = session.slide_images || [];

  // Filter notes by active slide
  const slideNotes = notes.filter((n) => n.slide_number === activeSlide);
  
  // Filter by search query
  const filteredNotes = slideNotes.filter((n) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase();
    return (
      n.slide_title.toLowerCase().includes(q) ||
      n.exact_transcript.toLowerCase().includes(q) ||
      n.ai_insight.toLowerCase().includes(q)
    );
  });

  // General off-slide / tangent notes
  const generalNotes = notes.filter((n) => n.slide_number === 0);
  const [showGeneralNotes, setShowGeneralNotes] = useState<boolean>(false);

  // Handle play at seek requests
  const handlePlayAt = (time: number) => {
    setSeekTo({ time, timestamp: Date.now() });
  };

  const handleManualSlideChange = (slideNum: number) => {
    setActiveSlide(slideNum);
    setFollowMode(false);
  };

  // Execute save session POST
  const handleSaveSession = async () => {
    if (!saveName.trim()) {
      alert("Please enter a session name.");
      return;
    }
    setSaving(true);
    try {
      await ApiService.saveSession({
        session_name: saveName,
        session_description: saveDesc,
        pdf_path: session.pdf_path,
        media_path: session.media_path,
        transcript_segments: session.transcript_segments,
        slides: session.slides,
        final_output: session.final_output,
        pipeline_type: session.pipeline_type || "audio",
        peaks: session.peaks,
        session_id: session.session_id,
      });
      alert("Session saved successfully to your Library!");
      setShowSaveDialog(false);
      onSaveCompleted();
    } catch (err: any) {
      alert(`Save error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  // Export JSON file
  const handleExportJSON = () => {
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(notes, null, 2));
    const downloadAnchor = document.createElement("a");
    downloadAnchor.setAttribute("href", dataStr);
    downloadAnchor.setAttribute("download", `${saveName.replace(/\s+/g, "_")}_notes.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="max-w-7xl mx-auto py-6 px-6 space-y-6 animate-fade-in">
      {/* Top Header Controls */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-4 border-b border-gray-800">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-lg text-xs font-semibold transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </button>

        <div className="flex gap-2">
          <button
            onClick={() => setShowSaveDialog(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-lg shadow-blue-600/10"
          >
            <Save className="w-4 h-4" />
            Save Session
          </button>
          
          <button
            onClick={handleExportJSON}
            className="flex items-center gap-1.5 px-4 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-lg text-xs font-semibold transition-all cursor-pointer"
          >
            <Download className="w-4 h-4" />
            Export JSON
          </button>
        </div>
      </div>

      {/* custom Title & Metadata */}
      <div>
        <h2 className="text-2xl font-extrabold text-gray-100">{saveName}</h2>
        {saveDesc && <p className="text-gray-400 text-xs mt-1">{saveDesc}</p>}
      </div>

      {/* Audio Timeline Player Component */}
      <div className="space-y-1">
        <div className="text-[10px] uppercase font-bold tracking-wider text-blue-400 select-none pl-1">
          🎵 Lecture Media Timeline
        </div>
        <AudioPlayer
          url={ApiService.getDataUrl(session.media_path || "")}
          notes={notes}
          activeSlide={activeSlide}
          onSlideChange={setActiveSlide}
          followMode={followMode}
          setFollowMode={setFollowMode}
          seekTo={seekTo}
          onTimeUpdate={setCurrentTime}
          peaks={session.peaks}
        />
      </div>

      {/* main Grid Split: 60/40 */}
      <div className="grid md:grid-cols-5 gap-6 items-start">
        {/* Sticky Slide Viewer Column (60% / 3 cols) */}
        <div className="md:col-span-3 md:sticky md:top-6 space-y-4">
          <SlideViewer
            slideImages={slideImages}
            activeSlide={activeSlide}
            onSlideChange={handleManualSlideChange}
          />
        </div>

        {/* Scrollable Notes Column (40% / 2 cols) */}
        <div className="md:col-span-2 space-y-4">
          {/* General Notes Expander */}
          {generalNotes.length > 0 && (
            <div className="border border-gray-800 rounded-xl overflow-hidden bg-[#121820]/40">
              <button
                onClick={() => setShowGeneralNotes(!showGeneralNotes)}
                className="w-full flex items-center justify-between p-4 text-xs font-bold text-gray-300 hover:bg-[#151c27] transition-all cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-4 h-4 text-purple-400" />
                  <span>General / Off-Slide Tangents ({generalNotes.length})</span>
                </div>
                <span className="text-[10px] text-gray-500 uppercase">{showGeneralNotes ? "Collapse ▲" : "Expand ▼"}</span>
              </button>

              {showGeneralNotes && (
                <div className="p-4 border-t border-gray-800 space-y-4 bg-gray-950/20 max-h-[300px] overflow-y-auto">
                  {generalNotes.map((note, i) => (
                    <NoteCard key={i} note={note} onPlayAt={handlePlayAt} />
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Search bar inside the slide notes list */}
          <div className="relative w-full">
            <Search className="w-4 h-4 text-gray-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder={`Search within Slide ${activeSlide} notes...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-[#121820]/90 border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs text-gray-200 placeholder-gray-500 rounded-xl pl-10 pr-4 py-3 outline-none transition-all"
            />
          </div>

          {/* Slide Notes Container */}
          <div className="space-y-4 max-h-[580px] overflow-y-auto pr-1">
            <div className="flex justify-between items-center text-xs font-semibold text-gray-400 px-1 select-none">
              <span>🧠 Slide {activeSlide} Insights</span>
              <span className="text-[10px] text-gray-500 font-normal">
                {filteredNotes.length} item(s) found
              </span>
            </div>

            {filteredNotes.length > 0 ? (
              filteredNotes.map((note, i) => (
                <NoteCard key={i} note={note} onPlayAt={handlePlayAt} />
              ))
            ) : (
              <div className="border border-dashed border-blue-500/15 rounded-2xl p-10 text-center bg-gray-950/5">
                <div className="text-3xl mb-3 text-blue-500/20">🧠</div>
                <h5 className="font-bold text-xs text-blue-400 mb-1">No Specific Insights</h5>
                <p className="text-[10px] text-gray-500 leading-relaxed max-w-[250px] mx-auto">
                  No verbal alignment notes were found matching Slide {activeSlide} in this section.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Save Session Dialog Modal overlay */}
      {showSaveDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
          <div className="bg-[#121820] border border-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl space-y-4">
            <h3 className="text-xl font-bold text-gray-100 flex items-center gap-2">
              <Save className="w-5 h-5 text-blue-400" />
              Save Lecture Session
            </h3>
            <p className="text-xs text-gray-400">
              Save this aligned session to your Library database cache to reload it dynamically at any time.
            </p>

            <div className="space-y-3">
              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-gray-400 pl-1">Session Name</label>
                <input
                  type="text"
                  value={saveName}
                  onChange={(e) => setSaveName(e.target.value)}
                  placeholder="e.g. Physics Lecture 3"
                  className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs text-gray-200 rounded-xl px-4 py-3 outline-none transition-all font-medium"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[10px] uppercase font-bold text-gray-400 pl-1">Description</label>
                <textarea
                  value={saveDesc}
                  onChange={(e) => setSaveDesc(e.target.value)}
                  placeholder="e.g. Topics covered: electromagnetism, Lorentz force..."
                  rows={3}
                  className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-xs text-gray-200 rounded-xl px-4 py-3 outline-none transition-all leading-normal"
                />
              </div>
            </div>

            <div className="flex gap-3 justify-end pt-2">
              <button
                onClick={() => setShowSaveDialog(false)}
                disabled={saving}
                className="px-4 py-2 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-lg text-xs font-semibold cursor-pointer transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveSession}
                disabled={saving}
                className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold cursor-pointer transition-all flex items-center gap-1.5 shadow-lg shadow-blue-600/10 disabled:opacity-40"
              >
                {saving ? "Saving..." : "Confirm & Save"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
