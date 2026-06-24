import React, { useEffect, useRef, useState, useMemo, useCallback } from "react";
import { Play, Pause, Volume2, VolumeX, Link2, Link2Off } from "lucide-react";
import type { AlignedNote } from "../types";
import { useWaveSurfer } from "../hooks/useWaveSurfer";
import { calculateSlideBoundaries, getSlideAtTime, formatTime } from "../utils/boundaries";
import { SlideTimeline } from "./SlideTimeline";
import { SlideJumpPills } from "./SlideJumpPills";

interface AudioPlayerProps {
  url: string;
  notes: AlignedNote[];
  activeSlide: number;
  onSlideChange: (slideNum: number) => void;
  followMode: boolean;
  setFollowMode: (mode: boolean) => void;
  seekTo: { time: number; timestamp: number } | null;
  onTimeUpdate: (time: number) => void;
  peaks?: number[];
}

export const AudioPlayer: React.FC<AudioPlayerProps> = ({
  url,
  notes,
  activeSlide,
  onSlideChange,
  followMode,
  setFollowMode,
  seekTo,
  onTimeUpdate,
  peaks,
}) => {
  const [hoverTime, setHoverTime] = useState<{ x: number; time: string } | null>(null);
  const [resyncSlide, setResyncSlide] = useState<number | null>(null);

  // Compute slide boundaries from notes using memoization
  const slideBoundaries = useMemo(() => calculateSlideBoundaries(notes), [notes]);

  // Hook handles WaveSurfer initialization, element observers, play/pause controls, and volume control
  const {
    containerRef,
    wavesurfer,
    isPlaying,
    isMuted,
    currentTime,
    duration,
    togglePlay,
    toggleMute,
    seekToTime,
  } = useWaveSurfer({ url, peaks, onTimeUpdate });

  // Handle slide boundary checking when playhead updates
  useEffect(() => {
    if (duration <= 0) return;
    
    const newSlide = getSlideAtTime(currentTime, slideBoundaries);
    if (newSlide !== null) {
      if (followMode) {
        if (newSlide !== activeSlide) {
          onSlideChange(newSlide);
        }
        setResyncSlide(null);
      } else {
        if (newSlide !== activeSlide) {
          setResyncSlide(newSlide);
        } else {
          setResyncSlide(null);
        }
      }
    }
  }, [currentTime, duration, followMode, activeSlide, slideBoundaries, onSlideChange]);

  const lastProcessedSeekTo = useRef<{ time: number; timestamp: number } | null>(null);

  // Handle external seek requests (e.g. from AlignedNote play-at buttons)
  useEffect(() => {
    if (seekTo && wavesurfer) {
      if (lastProcessedSeekTo.current === seekTo) return;
      lastProcessedSeekTo.current = seekTo;

      seekToTime(seekTo.time);
      if (!wavesurfer.isPlaying()) {
        wavesurfer.play().catch(console.error);
      }
      setFollowMode(true);
      setResyncSlide(null);
    }
  }, [seekTo, wavesurfer, seekToTime, setFollowMode]);

  // Unified seeking and segment clicking handler
  const handleSegmentClick = useCallback((time: number, slide: number) => {
    seekToTime(time);
    if (wavesurfer && !wavesurfer.isPlaying()) {
      wavesurfer.play().catch(console.error);
    }
    onSlideChange(slide);
    setFollowMode(true);
  }, [wavesurfer, seekToTime, onSlideChange, setFollowMode]);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (duration <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const pct = x / rect.width;
    const time = pct * duration;
    setHoverTime({ x, time: formatTime(time) });
  };

  const handleMouseLeave = () => {
    setHoverTime(null);
  };

  const triggerResync = () => {
    if (resyncSlide !== null) {
      onSlideChange(resyncSlide);
      setFollowMode(true);
      setResyncSlide(null);
    }
  };

  return (
    <div className="space-y-3 w-full bg-[#0d131a] border border-gray-800/80 rounded-xl p-4 shadow-lg shadow-black/40">
      <div className="flex items-center gap-4">
        {/* Play Button */}
        <button
          onClick={togglePlay}
          className="w-10 h-10 rounded-full bg-blue-500 hover:bg-blue-400 text-white flex items-center justify-center transition-all cursor-pointer flex-shrink-0 shadow-md shadow-blue-500/20"
        >
          {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
        </button>

        {/* Time counter */}
        <div className="text-xs text-gray-400 font-mono select-none w-24 flex-shrink-0">
          <span className="text-gray-200 font-semibold">{formatTime(currentTime)}</span>
          <span className="mx-1">/</span>
          <span>{formatTime(duration)}</span>
        </div>

        {/* Timeline Column (Slide Track + Waveform) */}
        <div className="flex-1 flex flex-col gap-2">
          {/* Minimal Colored Timeline Strip */}
          <SlideTimeline
            duration={duration}
            slideBoundaries={slideBoundaries}
            activeSlide={activeSlide}
            currentTime={currentTime}
            onSegmentClick={handleSegmentClick}
            formatTime={formatTime}
          />

          {/* Waveform Wrapper */}
          <div 
            className="relative cursor-pointer group"
            onMouseMove={handleMouseMove}
            onMouseLeave={handleMouseLeave}
          >
            <div ref={containerRef} className="w-full relative z-10" />

            {/* Subtle Slide Boundary Markers */}
            {duration > 0 &&
              slideBoundaries.map((seg) => {
                const leftPct = (seg.start / duration) * 100;
                return (
                  <div
                    key={`${seg.slide}-${seg.start}`}
                    className="absolute top-0 bottom-0 border-l border-dashed border-blue-500/15 pointer-events-none z-20"
                    style={{ left: `${leftPct}%` }}
                  />
                );
              })}

            {/* Time Hover tooltip */}
            {hoverTime && (
              <div
                className="absolute top-[-26px] bg-gray-900 border border-gray-800 text-[10px] text-gray-300 px-2 py-0.5 rounded shadow pointer-events-none z-30 font-mono -translate-x-1/2"
                style={{ left: `${hoverTime.x}px` }}
              >
                {hoverTime.time}
              </div>
            )}
          </div>
        </div>

        {/* Lock Sync Button */}
        <button
          onClick={() => setFollowMode(!followMode)}
          className={`p-2.5 rounded-lg border transition-all cursor-pointer ${
            followMode
              ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
              : "bg-gray-900 border-gray-800 text-gray-400 hover:bg-gray-800"
          }`}
          title={followMode ? "Synced - Slides follow audio" : "Browsing - Click to sync"}
        >
          {followMode ? <Link2 className="w-4 h-4" /> : <Link2Off className="w-4 h-4" />}
        </button>

        {/* Volume Mute Button */}
        <button
          onClick={toggleMute}
          className="p-2.5 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 text-gray-400 transition-all cursor-pointer"
        >
          {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
        </button>
      </div>

      {/* Floating Re-sync Affordance */}
      {resyncSlide !== null && !followMode && (
        <div className="flex justify-center animate-fade-in">
          <button
            onClick={triggerResync}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-500/20 to-purple-500/20 border border-blue-500/40 rounded-full text-[10px] font-bold text-blue-400 cursor-pointer shadow-md shadow-blue-500/10 animate-pulse"
          >
            <Link2 className="w-3.5 h-3.5" />
            Sync Slide View to Slide {resyncSlide} ({formatTime(currentTime)}) ▸
          </button>
        </div>
      )}

      {/* Slide Chapter Pills Row */}
      {duration > 0 && slideBoundaries.length > 0 && (
        <SlideJumpPills
          slideBoundaries={slideBoundaries}
          activeSlide={activeSlide}
          currentTime={currentTime}
          onPillClick={handleSegmentClick}
          formatTime={formatTime}
        />
      )}
    </div>
  );
};
