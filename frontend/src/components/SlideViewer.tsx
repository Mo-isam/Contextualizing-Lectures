import React from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface SlideViewerProps {
  slideImages: string[];
  activeSlide: number;
  onSlideChange: (slideNum: number) => void;
}

export const SlideViewer: React.FC<SlideViewerProps> = ({
  slideImages,
  activeSlide,
  onSlideChange,
}) => {
  if (!slideImages || slideImages.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center bg-gray-900 border border-gray-800 rounded-xl p-12 text-center h-[350px]">
        <span className="text-3xl mb-3">📄</span>
        <h4 className="font-bold text-gray-300">No slides loaded</h4>
        <p className="text-xs text-gray-500 mt-1">Upload a PDF to render slides in the studio.</p>
      </div>
    );
  }

  const totalSlides = slideImages.length;
  // Ensure activeSlide stays in bounds
  const currentIndex = Math.max(0, Math.min(activeSlide - 1, totalSlides - 1));
  const activeImage = `/tmp/${slideImages[currentIndex]}`;

  const handlePrev = () => {
    if (activeSlide > 1) {
      onSlideChange(activeSlide - 1);
    }
  };

  const handleNext = () => {
    if (activeSlide < totalSlides) {
      onSlideChange(activeSlide + 1);
    }
  };

  const handleSelectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    onSlideChange(parseInt(e.target.value));
  };

  return (
    <div className="bg-[#121820]/80 border border-gray-800 rounded-xl p-4 space-y-4 shadow-lg">
      <div className="text-xs font-semibold uppercase tracking-wider text-gray-400 select-none">
        📄 Lecture Slides
      </div>

      {/* Slide Image Panel */}
      <div className="relative overflow-hidden rounded-lg border border-gray-800/80 bg-black flex items-center justify-center group aspect-[16/9]">
        <img
          src={activeImage}
          alt={`Slide ${activeSlide}`}
          className="max-h-full max-w-full object-contain select-none transition-all duration-300"
          loading="lazy"
        />
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 bg-black/60 backdrop-blur-sm border border-gray-800 px-3 py-1 rounded-full text-[10px] text-gray-300 select-none">
          Slide {activeSlide} of {totalSlides}
        </div>
      </div>

      {/* Slide Navigation Controls */}
      <div className="flex gap-2">
        <button
          onClick={handlePrev}
          disabled={activeSlide <= 1}
          className="flex-1 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 disabled:opacity-30 text-gray-300 disabled:hover:bg-gray-900 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1 cursor-pointer disabled:cursor-not-allowed"
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </button>

        <select
          value={activeSlide}
          onChange={handleSelectChange}
          className="flex-[2] bg-gray-900 border border-gray-800 text-gray-300 rounded-lg py-2 px-3 text-xs font-medium text-center outline-none cursor-pointer hover:border-gray-700 transition-all appearance-none"
          style={{ textIndent: "25%" }}
        >
          {slideImages.map((_, i) => (
            <option key={i + 1} value={i + 1}>
              Slide {i + 1} / {totalSlides}
            </option>
          ))}
        </select>

        <button
          onClick={handleNext}
          disabled={activeSlide >= totalSlides}
          className="flex-1 py-2 bg-gray-900 border border-gray-800 hover:bg-gray-800 disabled:opacity-30 text-gray-300 disabled:hover:bg-gray-900 rounded-lg text-xs font-semibold transition-all flex items-center justify-center gap-1 cursor-pointer disabled:cursor-not-allowed"
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
};
