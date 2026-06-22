import React, { useEffect, useRef } from "react";
import type { SlideBoundary } from "../utils/boundaries";
import { getSlideAtTime } from "../utils/boundaries";

interface SlideJumpPillsProps {
  slideBoundaries: SlideBoundary[];
  activeSlide: number;
  currentTime: number;
  onPillClick: (time: number, slide: number) => void;
  formatTime: (time: number) => string;
}

export const SlideJumpPills: React.FC<SlideJumpPillsProps> = ({
  slideBoundaries,
  activeSlide,
  currentTime,
  onPillClick,
  formatTime,
}) => {
  const pillsContainerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll active pill into view
  useEffect(() => {
    if (!pillsContainerRef.current) return;
    const activePill = pillsContainerRef.current.querySelector('[data-active="true"]');
    if (activePill) {
      activePill.scrollIntoView({
        behavior: "smooth",
        block: "nearest",
        inline: "center",
      });
    }
  }, [activeSlide]);

  return (
    <div className="pt-3 border-t border-gray-800/40 flex flex-col gap-2">
      <div className="text-[10px] uppercase font-bold tracking-wider text-gray-500 select-none pl-1">
        Jump to Slide Segment
      </div>
      <div
        ref={pillsContainerRef}
        className="flex items-center gap-2 overflow-x-auto py-1 px-1 scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent"
      >
        {slideBoundaries.map((seg) => {
          const isActive = activeSlide === seg.slide;
          const isCurrentPlayheadSlide = getSlideAtTime(currentTime, slideBoundaries) === seg.slide;

          return (
            <button
              key={seg.slide}
              data-active={isActive ? "true" : "false"}
              onClick={() => onPillClick(seg.start, seg.slide)}
              className={`h-7 px-3 flex-shrink-0 flex items-center justify-center rounded-full text-[11px] font-mono font-bold border transition-all cursor-pointer select-none ${
                isActive
                  ? "bg-blue-600/90 text-white border-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.3)] hover:bg-blue-500"
                  : isCurrentPlayheadSlide
                    ? "bg-purple-600/10 text-purple-300 border-purple-500/50 hover:bg-purple-600/20"
                    : "bg-slate-900/80 text-gray-400 border-gray-800/85 hover:bg-slate-800 hover:text-gray-200"
              }`}
              title={`Slide ${seg.slide} (${formatTime(seg.start)} - ${formatTime(seg.end)})`}
            >
              <span
                className={`text-[9px] font-sans tracking-wide leading-none mr-1 ${
                  isActive
                    ? "text-blue-200"
                    : isCurrentPlayheadSlide
                      ? "text-purple-400"
                      : "text-gray-500"
                }`}
              >
                SLIDE
              </span>
              {seg.slide}
            </button>
          );
        })}
      </div>
    </div>
  );
};
