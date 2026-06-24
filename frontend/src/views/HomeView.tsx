import React from "react";
import { Sparkles, BookOpen } from "lucide-react";

interface HomeViewProps {
  onNewSession: () => void;
  onOpenLibrary: () => void;
}

export const HomeView: React.FC<HomeViewProps> = ({ onNewSession, onOpenLibrary }) => {
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
              Upload or select a slide PDF (or PPTX) and an audio/video recording to align, annotate, and analyze slide-by-slide concepts.
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
        <div className="bg-gradient-to-br from-[#161b22] to-[#0d1117] border border-purple-500/20 hover:border-purple-500/40 rounded-2xl p-8 transition-all hover:-translate-y-1 shadow-lg hover:shadow-purple-500/10 flex flex-col justify-between">
          <div>
            <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center text-purple-400 mb-6">
              <BookOpen className="w-6 h-6" />
            </div>
            <h3 className="text-2xl font-bold text-gray-100 mb-2">Saved Library</h3>
            <p className="text-gray-400 text-sm leading-relaxed mb-8">
              Select and reopen a previously aligned lecture session from your local persistent database cache.
            </p>
          </div>
          <button
            onClick={onOpenLibrary}
            className="w-full py-3 bg-gradient-to-r from-purple-600 to-purple-500 hover:from-purple-500 hover:to-purple-400 text-white font-semibold rounded-xl shadow-lg hover:shadow-purple-500/20 transition-all cursor-pointer"
          >
            Open Saved Library
          </button>
        </div>
      </div>
    </div>
  );
};
