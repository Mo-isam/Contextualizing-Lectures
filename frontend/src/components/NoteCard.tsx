import React from "react";
import { Clock, Play, Sparkles, MessageSquare } from "lucide-react";
import type { AlignedNote } from "../types";

interface NoteCardProps {
  note: AlignedNote;
  onPlayAt: (time: number) => void;
}

export const NoteCard: React.FC<NoteCardProps> = ({ note, onPlayAt }) => {
  const formatTime = (time: number) => {
    const s = Math.max(0, Math.floor(time));
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    if (h) {
      return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
    }
    return `${m}:${sec.toString().padStart(2, "0")}`;
  };

  const tsLabel = `⏱ ${formatTime(note.timestamp_start)} → ${formatTime(note.timestamp_end)}`;

  return (
    <div
      className={`relative rounded-xl p-5 border shadow-sm transition-all duration-300 hover:-translate-y-0.5 hover:shadow-md ${
        note.is_off_topic
          ? "bg-[#1c212a]/95 border-gray-800 hover:border-gray-700"
          : "bg-gradient-to-br from-[#121c2c]/90 to-[#0e1624]/90 border-[#1f3f6e]/30 hover:border-[#1f3f6e]/60"
      }`}
    >
      {/* Indicator border stripe */}
      <div
        className={`absolute left-0 top-0 bottom-0 w-1 rounded-l-xl ${
          note.is_off_topic ? "bg-gray-500" : "bg-gradient-to-b from-blue-500 to-purple-500"
        }`}
      />

      <div className="flex items-start justify-between gap-3 mb-2.5">
        {/* Badges */}
        {note.is_off_topic ? (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded-full bg-gray-800 border border-gray-700 text-gray-400">
            <MessageSquare className="w-3 h-3" />
            Tangent
          </span>
        ) : (
          <span className="inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-bold rounded-full bg-blue-500/10 border border-blue-500/30 text-blue-400">
            Slide {note.slide_number}
          </span>
        )}
      </div>

      {/* Note Title */}
      <h5 className="font-semibold text-sm text-gray-200 mb-2 leading-snug">
        {note.slide_title}
      </h5>

      {/* Exact Transcript Quote */}
      <blockquote
        className={`text-xs italic pl-3 border-l-2 mb-3 leading-relaxed ${
          note.is_off_topic
            ? "border-gray-600 text-gray-400"
            : "border-blue-500/50 text-gray-300"
        }`}
      >
        "{note.exact_transcript}"
      </blockquote>

      {/* AI Insight (if present and not off-topic) */}
      {!note.is_off_topic && note.ai_insight && (
        <div className="bg-blue-500/5 border border-blue-500/10 rounded-lg p-3 text-[11px] leading-relaxed text-[#c4d6f0] mb-4 flex gap-2">
          <Sparkles className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
          <div>
            <strong className="text-blue-400 font-semibold">AI Insight: </strong>
            {note.ai_insight}
          </div>
        </div>
      )}

      {/* Bottom actions row */}
      <div className="flex items-center justify-between mt-2 pt-2 border-t border-gray-800/40">
        <span className="text-[10px] text-gray-500 font-medium font-mono flex items-center gap-1">
          <Clock className="w-3.5 h-3.5 text-gray-600" />
          {tsLabel}
        </span>

        <button
          onClick={() => onPlayAt(note.timestamp_start)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500/10 to-purple-500/10 hover:from-blue-500/25 hover:to-purple-500/25 border border-blue-500/20 hover:border-blue-500/40 rounded-full text-[10px] font-bold text-blue-400 transition-all cursor-pointer"
        >
          <Play className="w-3 h-3 fill-current" />
          Play at {formatTime(note.timestamp_start)}
        </button>
      </div>
    </div>
  );
};
