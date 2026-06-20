import React, { useEffect, useRef, useState, useCallback } from "react";
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
  const [timelineHover, setTimelineHover] = useState<{
    x: number;
    slide: number;
    start: number;
    end: number;
  } | null>(null);

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

    // Resolve overlaps by capping the end of each segment at the start of the next
    const cleanSegments = segments.map((seg, idx) => {
      const nextSeg = segments[idx + 1];
      const adjustedEnd = nextSeg ? Math.min(seg.end, nextSeg.start) : seg.end;
      return {
        slide: seg.slide,
        start: seg.start,
        end: Math.max(seg.start + 0.1, adjustedEnd),
      };
    });

    setSlideBoundaries(cleanSegments);
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

    let observer: ResizeObserver | null = null;
    let isCleanedUp = false;

    const initWaveSurfer = () => {
      if (isCleanedUp || !containerRef.current) return;

      const audio = new Audio();
      audio.crossOrigin = "anonymous";

      const handleDurationChange = () => {
        if (audio.duration) {
          setDuration(audio.duration);
        }
      };

      audio.addEventListener("durationchange", handleDurationChange);
      audio.addEventListener("loadedmetadata", handleDurationChange);

      // Set src after adding listeners to ensure we don't miss early cached events
      audio.src = url;

      const ws = WaveSurfer.create({
        container: containerRef.current,
        media: audio,
        waveColor: "rgba(148, 163, 184, 0.25)",
        progressColor: "#3b82f6",
        cursorColor: "#60a5fa",
        cursorWidth: 2,
        height: 48,
        normalize: true,
        barWidth: 2,
        barGap: 3,
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
      ws.on("error", (e) => console.warn("WaveSurfer visual error (falling back to audio element):", e));

      // Trigger duration update if audio element loaded metadata before WaveSurfer was ready
      if (audio.duration) {
        setDuration(audio.duration);
      }
    };

    const container = containerRef.current;
    if (container.clientWidth > 0) {
      initWaveSurfer();
    } else {
      // Wait for layout/animation to paint the container before initializing WaveSurfer
      observer = new ResizeObserver((entries) => {
        for (const entry of entries) {
          if (entry.contentRect.width > 0) {
            initWaveSurfer();
            observer?.disconnect();
            observer = null;
            break;
          }
        }
      });
      observer.observe(container);
    }

    return () => {
      isCleanedUp = true;
      if (observer) {
        observer.disconnect();
      }
      if (wavesurferRef.current) {
        const ws = wavesurferRef.current;
        const media = ws.getMediaElement();
        if (media) {
          media.pause();
          media.src = "";
          try {
            (media as HTMLAudioElement).load();
          } catch (e) {}
        }
        ws.destroy();
        wavesurferRef.current = null;
      }
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
          <div 
            className="relative h-1.5 w-full bg-[#070b0f] rounded-full overflow-hidden border border-gray-800/60 cursor-pointer flex select-none"
            onMouseMove={handleTimelineMouseMove}
            onMouseLeave={handleTimelineMouseLeave}
          >
            {duration > 0 && slideBoundaries.map((seg) => {
              const startPct = (seg.start / duration) * 100;
              const durationPct = Math.max(0, Math.min(100 - startPct, ((seg.end - seg.start) / duration) * 100));
              const isActive = activeSlide === seg.slide;
              const isEven = seg.slide % 2 === 0;

              return (
                <div
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
                  className={`absolute top-0 bottom-0 transition-all duration-200 hover:brightness-125 cursor-pointer ${
                    isActive
                      ? "bg-gradient-to-r from-blue-500 to-indigo-500 shadow-[0_0_8px_rgba(59,130,246,0.5)] z-10"
                      : isEven
                        ? "bg-slate-600/55"
                        : "bg-slate-800/55"
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
                Slide {timelineHover.slide} <span className="text-gray-400 font-sans font-normal">({formatTime(timelineHover.start)} - {formatTime(timelineHover.end)})</span>
              </div>
            )}
          </div>

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

      {/* Slide Chapter Pills Row */}
      {duration > 0 && slideBoundaries.length > 0 && (
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
              const isCurrentPlayheadSlide = getSlideAtTime(currentTime) === seg.slide;
              
              return (
                <button
                  key={seg.slide}
                  data-active={isActive ? "true" : "false"}
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
                  className={`h-7 px-3 flex-shrink-0 flex items-center justify-center rounded-full text-[11px] font-mono font-bold border transition-all cursor-pointer select-none ${
                    isActive
                      ? "bg-blue-600/90 text-white border-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.3)] hover:bg-blue-500"
                      : isCurrentPlayheadSlide
                        ? "bg-purple-600/10 text-purple-300 border-purple-500/50 hover:bg-purple-600/20"
                        : "bg-slate-900/80 text-gray-400 border-gray-800/85 hover:bg-slate-800 hover:text-gray-200"
                  }`}
                  title={`Slide ${seg.slide} (${formatTime(seg.start)} - ${formatTime(seg.end)})`}
                >
                  <span className="text-[9px] text-gray-500 font-sans tracking-wide leading-none mr-1">SLIDE</span>
                  {seg.slide}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};
