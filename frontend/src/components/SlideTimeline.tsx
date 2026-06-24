import React, { useState } from "react";
import type { SlideBoundary } from "../utils/boundaries";

interface SlideTimelineProps {
  duration: number;
  slideBoundaries: SlideBoundary[];
  activeSlide: number;
  currentTime: number;
  onSegmentClick: (time: number, slide: number) => void;
  formatTime: (time: number) => string;
}

interface TimelineHoverState {
  x: number;
  slide: number;
  start: number;
  end: number;
}

export const SlideTimeline: React.FC<SlideTimelineProps> = ({
  duration,
  slideBoundaries,
  activeSlide,
  currentTime,
  onSegmentClick,
  formatTime,
}) => {
  const [timelineHover, setTimelineHover] = useState<TimelineHoverState | null>(null);

  const handleTimelineMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (duration <= 0 || slideBoundaries.length === 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    const time = pct * duration;

    const seg = slideBoundaries.find((s) => time >= s.start && time <= s.end);
    if (seg) {
      setTimelineHover({
        x,
        slide: seg.slide,
        start: seg.start,
        end: seg.end,
      });
    } else {
      setTimelineHover(null);
    }
  };

  const handleTimelineMouseLeave = () => {
    setTimelineHover(null);
  };

  return (
    <div
      className="relative h-1.5 w-full bg-[#070b0f] rounded-full overflow-hidden border border-gray-800/60 cursor-pointer flex select-none"
      onMouseMove={handleTimelineMouseMove}
      onMouseLeave={handleTimelineMouseLeave}
    >
      {duration > 0 &&
        slideBoundaries.map((seg) => {
          const startPct = (seg.start / duration) * 100;
          const durationPct = Math.max(
            0,
            Math.min(100 - startPct, ((seg.end - seg.start) / duration) * 100)
          );
          const isPlayingSeg = currentTime >= seg.start && currentTime <= seg.end;
          const isRelatedSeg = seg.slide === activeSlide;
          const isEven = seg.slide % 2 === 0;

          return (
            <div
              key={`${seg.slide}-${seg.start}`}
              onClick={() => onSegmentClick(seg.start, seg.slide)}
              className={`absolute top-0 bottom-0 transition-all duration-200 hover:brightness-125 cursor-pointer ${
                isPlayingSeg
                  ? "bg-gradient-to-r from-blue-500 to-indigo-500 shadow-[0_0_8px_rgba(59,130,246,0.5)] z-10"
                  : isRelatedSeg
                    ? "bg-gradient-to-r from-purple-500 to-fuchsia-500 shadow-[0_0_8px_rgba(168,85,247,0.4)] z-10"
                    : isEven
                      ? "bg-slate-800/80"
                      : "bg-slate-600/50"
              }`}
              style={{
                left: `${startPct}%`,
                width: `${durationPct}%`,
              }}
            />
          );
        })}

      {/* Hover Tooltip for Slide timeline */}
      {timelineHover && (
        <div
          className="absolute bottom-full mb-2 bg-[#090d14]/95 border border-blue-500/30 text-[10px] text-gray-200 px-2.5 py-1 rounded-lg shadow-xl pointer-events-none z-30 font-mono -translate-x-1/2 whitespace-nowrap"
          style={{ left: `${timelineHover.x}px` }}
        >
          Slide {timelineHover.slide}{" "}
          <span className="text-gray-400 font-sans font-normal">
            ({formatTime(timelineHover.start)} - {formatTime(timelineHover.end)})
          </span>
        </div>
      )}
    </div>
  );
};
