import React, { useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import { Play, Pause, Volume2, VolumeX, Link2, Link2Off } from "lucide-react";
import type { AlignedNote } from "../types";

interface AudioPlayerProps {
  url: string;
  notes: AlignedNote[];
  activeSlide: number;
  onSlideChange: (slideNum: number) => void;
  followMode: boolean;
  setFollowMode: (mode: boolean) => void;
  seekTo: { time: number; timestamp: number } | null;
  onTimeUpdate: (time: number) => void;
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
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);
  const [slideBoundaries, setSlideBoundaries] = useState<Array<{ slide: number; start: number; end: number }>>([]);
  const [hoverTime, setHoverTime] = useState<{ x: number; time: string } | null>(null);
  const [resyncSlide, setResyncSlide] = useState<number | null>(null);

  // Compute slide boundaries from notes
  useEffect(() => {
    if (!notes || notes.length === 0) return;
    
    const boundaries: Record<number, { start: number; end: number }> = {};
    notes.forEach((n) => {
      if (n.slide_number === 0) return; // Skip general notes
      if (!boundaries[n.slide_number]) {
        boundaries[n.slide_number] = { start: n.timestamp_start, end: n.timestamp_end };
      } else {
        boundaries[n.slide_number].start = Math.min(boundaries[n.slide_number].start, n.timestamp_start);
        boundaries[n.slide_number].end = Math.max(boundaries[n.slide_number].end, n.timestamp_end);
      }
    });

    const segments = Object.entries(boundaries).map(([slide, r]) => ({
      slide: parseInt(slide),
      start: r.start,
      end: r.end,
    })).sort((a, b) => a.start - b.start);

    setSlideBoundaries(segments);
  }, [notes]);

  // Find slide active at a given timestamp
  const getSlideAtTime = (time: number) => {
    let bestSlide = null;
    for (const seg of slideBoundaries) {
      if (time >= seg.start) {
        bestSlide = seg.slide;
      }
    }
    return bestSlide;
  };

  // Initialize WaveSurfer
  useEffect(() => {
    if (!containerRef.current || !url) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "rgba(148, 163, 184, 0.15)",
      progressColor: "rgba(59, 130, 246, 0.75)",
      cursorColor: "#3b82f6",
      cursorWidth: 2,
      height: 38,
      normalize: true,
      barWidth: 2,
      barGap: 2.5,
      barRadius: 2,
    });

    wavesurferRef.current = ws;

    ws.on("ready", () => {
      setDuration(ws.getDuration());
    });

    ws.on("audioprocess", () => {
      const time = ws.getCurrentTime();
      setCurrentTime(time);
      onTimeUpdate(time);
    });

    ws.on("timeupdate", () => {
      const time = ws.getCurrentTime();
      setCurrentTime(time);
      onTimeUpdate(time);
    });

    ws.on("play", () => setIsPlaying(true));
    ws.on("pause", () => setIsPlaying(false));

    // Load the audio source
    ws.load(url);

    return () => {
      ws.destroy();
    };
  }, [url]);

  // Handle slide boundary checking when playhead updates
  useEffect(() => {
    if (duration <= 0) return;
    
    const newSlide = getSlideAtTime(currentTime);
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
  }, [currentTime, duration, followMode, activeSlide, slideBoundaries]);

  // Handle external seek requests (e.g. from AlignedNote play-at buttons)
  useEffect(() => {
    if (seekTo && wavesurferRef.current) {
      wavesurferRef.current.setTime(seekTo.time);
      if (!wavesurferRef.current.isPlaying()) {
        wavesurferRef.current.play().catch(console.error);
      }
      setFollowMode(true);
      setResyncSlide(null);
    }
  }, [seekTo]);

  const togglePlay = () => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  };

  const toggleMute = () => {
    if (wavesurferRef.current) {
      const nextMute = !isMuted;
      wavesurferRef.current.setMuted(nextMute);
      setIsMuted(nextMute);
    }
  };

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

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!wavesurferRef.current || duration <= 0) return;
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
    <div className="space-y-3 w-full bg-[#121820]/90 border border-gray-800 rounded-xl p-4 shadow-md">
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
          {/* Slide Duration Track */}
          {duration > 0 && slideBoundaries.length > 0 && (
            <div className="h-6 w-full bg-gray-900/60 rounded-lg relative overflow-hidden border border-gray-800/80 flex select-none">
              {slideBoundaries.map((seg) => {
                const startPct = (seg.start / duration) * 100;
                const durationPct = Math.max(0, Math.min(100 - startPct, ((seg.end - seg.start) / duration) * 100));
                const isActive = activeSlide === seg.slide;
                
                return (
                  <button
                    key={seg.slide}
                    onClick={() => {
                      if (wavesurferRef.current) {
                        wavesurferRef.current.setTime(seg.start);
                        if (!wavesurferRef.current.isPlaying()) {
                          wavesurferRef.current.play().catch(console.error);
                        }
                        onSlideChange(seg.slide);
                        setFollowMode(true);
                      }
                    }}
                    className={`absolute top-0 bottom-0 text-[10px] font-bold transition-all duration-300 flex items-center justify-center border-r border-gray-800/60 hover:bg-blue-500/10 cursor-pointer overflow-hidden truncate ${
                      isActive
                        ? "bg-blue-500/20 text-blue-400 border-b-2 border-b-blue-500 shadow-inner"
                        : "text-gray-400 bg-gray-950/20"
                    }`}
                    style={{
                      left: `${startPct}%`,
                      width: `${durationPct}%`,
                    }}
                    title={`Slide ${seg.slide} (${formatTime(seg.start)} - ${formatTime(seg.end)})`}
                  >
                    <span className="px-1 text-[9px] truncate font-mono">S{seg.slide}</span>
                  </button>
                );
              })}
            </div>
          )}

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
                    key={seg.slide}
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
    </div>
  );
};
