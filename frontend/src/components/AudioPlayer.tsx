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
  const trackRef = useRef<HTMLDivElement>(null);
  const [trackWidthPx, setTrackWidthPx] = useState<number>(0);
  const [hoveredCluster, setHoveredCluster] = useState<Array<{
    slide: number;
    start: number;
    end: number;
    widthPct: number;
    isEven: boolean;
    isActive: boolean;
  }> | null>(null);
  const [clusterAnchorX, setClusterAnchorX] = useState<number>(0);

  // Measure slide duration track width in pixels
  useEffect(() => {
    const el = trackRef.current;
    if (!el) return;

    const updateWidth = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0) {
        setTrackWidthPx(rect.width);
      }
    };

    updateWidth();

    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        if (entry.contentRect && entry.contentRect.width > 0) {
          setTrackWidthPx(entry.contentRect.width);
        }
      }
    });

    observer.observe(el);

    return () => {
      observer.unobserve(el);
      observer.disconnect();
    };
  }, []);

  // Secondary measure check when boundaries update
  useEffect(() => {
    if (trackRef.current) {
      const rect = trackRef.current.getBoundingClientRect();
      if (rect.width > 0) {
        setTrackWidthPx(rect.width);
      }
    }
  }, [slideBoundaries]);

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

    const audio = new Audio();
    audio.src = url;
    audio.crossOrigin = "anonymous";

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

    const handleDurationChange = () => {
      if (audio.duration) {
        setDuration(audio.duration);
      }
    };
    audio.addEventListener("durationchange", handleDurationChange);
    audio.addEventListener("loadedmetadata", handleDurationChange);

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

    return () => {
      audio.pause();
      audio.src = "";
      try {
        audio.load();
      } catch (err) {}
      audio.removeEventListener("durationchange", handleDurationChange);
      audio.removeEventListener("loadedmetadata", handleDurationChange);
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

  const handleTrackMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (duration <= 0 || trackWidthPx <= 0 || slideBoundaries.length === 0) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const clientX = e.clientX - rect.left;
    const pct = clientX / rect.width;
    const time = pct * duration;

    // Find which segment is under the mouse
    const hoveredIdx = slideBoundaries.findIndex(
      (seg) => time >= seg.start && time <= seg.end
    );

    if (hoveredIdx === -1) {
      setHoveredCluster(null);
      return;
    }

    const hoveredSeg = slideBoundaries[hoveredIdx];
    const getSegWidthPx = (seg: typeof slideBoundaries[0]) => {
      const startPct = (seg.start / duration) * 100;
      const durationPct = Math.max(0, Math.min(100 - startPct, ((seg.end - seg.start) / duration) * 100));
      return (durationPct / 100) * trackWidthPx;
    };

    const hoveredWidthPx = getSegWidthPx(hoveredSeg);

    if (hoveredWidthPx < 20) {
      // Find all adjacent narrow segments (width < 20px)
      let startIdx = hoveredIdx;
      while (startIdx > 0 && getSegWidthPx(slideBoundaries[startIdx - 1]) < 20) {
        startIdx--;
      }

      let endIdx = hoveredIdx;
      while (endIdx < slideBoundaries.length - 1 && getSegWidthPx(slideBoundaries[endIdx + 1]) < 20) {
        endIdx++;
      }

      // Limit the cluster to at most 7 segments centered around hoveredIdx
      let clusterStart = startIdx;
      let clusterEnd = endIdx;
      
      const maxSegments = 7;
      if (clusterEnd - clusterStart + 1 > maxSegments) {
        const halfMax = Math.floor(maxSegments / 2);
        let leftBound = hoveredIdx - halfMax;
        let rightBound = hoveredIdx + halfMax;

        if (leftBound < clusterStart) {
          rightBound += (clusterStart - leftBound);
          leftBound = clusterStart;
        }
        if (rightBound > clusterEnd) {
          leftBound -= (rightBound - clusterEnd);
          rightBound = clusterEnd;
        }

        clusterStart = Math.max(clusterStart, leftBound);
        clusterEnd = Math.min(clusterEnd, rightBound);
      }

      const cluster = slideBoundaries.slice(clusterStart, clusterEnd + 1).map((seg) => {
        const segStartPct = (seg.start / duration) * 100;
        const segDurationPct = Math.max(0, Math.min(100 - segStartPct, ((seg.end - seg.start) / duration) * 100));
        return {
          slide: seg.slide,
          start: seg.start,
          end: seg.end,
          widthPct: segDurationPct,
          isEven: seg.slide % 2 === 0,
          isActive: activeSlide === seg.slide,
        };
      });

      // Calculate anchor X
      const hoveredStartPct = (hoveredSeg.start / duration) * 100;
      const hoveredDurationPct = Math.max(0, Math.min(100 - hoveredStartPct, ((hoveredSeg.end - hoveredSeg.start) / duration) * 100));
      const segmentCenterX = ((hoveredStartPct + hoveredDurationPct / 2) / 100) * trackWidthPx;

      setHoveredCluster(cluster);
      setClusterAnchorX(segmentCenterX);
    } else {
      setHoveredCluster(null);
    }
  };

  const handleTrackMouseLeave = () => {
    setHoveredCluster(null);
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
          {/* Slide Track Container Wrapper */}
          <div 
            className="relative"
            onMouseLeave={handleTrackMouseLeave}
          >
            {/* Hover Magnifier Popover */}
            {hoveredCluster && hoveredCluster.length > 0 && (() => {
              const popoverWidth = hoveredCluster.length * 52 + 8;
              const halfWidth = popoverWidth / 2;
              let leftPos = clusterAnchorX - halfWidth;
              leftPos = Math.max(4, Math.min(trackWidthPx - popoverWidth - 4, leftPos));
              const triangleLeft = clusterAnchorX - leftPos;

              return (
                <div 
                  className="absolute z-50 bottom-full mb-2 bg-[#090d14]/95 backdrop-blur-md border border-blue-500/20 rounded-lg shadow-[0_10px_25px_-5px_rgba(0,0,0,0.8),0_8px_10px_-6px_rgba(0,0,0,0.8)] p-1.5 flex items-center gap-1 animate-fade-in"
                  style={{ left: `${leftPos}px` }}
                >
                  {hoveredCluster.map((seg) => (
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
                      className={`h-8 w-12 flex flex-col items-center justify-center rounded text-[10px] font-mono transition-all border cursor-pointer select-none ${
                        seg.isActive
                          ? "bg-gradient-to-b from-blue-500/30 to-indigo-500/20 text-blue-300 border-blue-500/60 shadow-[0_0_8px_rgba(59,130,246,0.3)]"
                          : seg.isEven
                            ? "bg-slate-800/90 text-gray-300 border-gray-700 hover:bg-slate-700 hover:text-white"
                            : "bg-slate-700/80 text-gray-300 border-gray-600/80 hover:bg-slate-600 hover:text-white"
                      }`}
                      title={`Slide ${seg.slide} (${formatTime(seg.start)} - ${formatTime(seg.end)})`}
                    >
                      <span className="text-[7px] text-gray-400 font-sans tracking-wide leading-none">SLIDE</span>
                      <span className="font-bold text-[11px] leading-tight">{seg.slide}</span>
                    </button>
                  ))}
                  {/* Triangle Caret */}
                  <div 
                    className="absolute top-full border-x-[6px] border-x-transparent border-t-[6px] border-t-[#090d14]/95 -translate-x-1/2 pointer-events-none"
                    style={{ left: `${triangleLeft}px` }}
                  />
                </div>
              );
            })()}

            {/* Slide Duration Track */}
            <div 
              ref={trackRef}
              onMouseMove={handleTrackMouseMove}
              className={`h-6 w-full bg-[#070b0f] rounded-lg relative overflow-hidden border border-gray-800/60 flex select-none ${
                duration > 0 && slideBoundaries.length > 0 ? "" : "hidden"
              }`}
            >
              {duration > 0 && slideBoundaries.length > 0 && slideBoundaries.map((seg) => {
                const startPct = (seg.start / duration) * 100;
                const durationPct = Math.max(0, Math.min(100 - startPct, ((seg.end - seg.start) / duration) * 100));
                const isActive = activeSlide === seg.slide;
                const isEven = seg.slide % 2 === 0;

                const pixelWidth = trackWidthPx > 0 ? (durationPct / 100) * trackWidthPx : 0;
                const showBorderRight = trackWidthPx > 0 ? pixelWidth >= 10 : durationPct >= 1.0;

                let labelContent = null;
                if (trackWidthPx > 0) {
                  if (pixelWidth >= 40) {
                    labelContent = <span className="px-1 text-[9px] truncate font-mono">Slide {seg.slide}</span>;
                  } else if (pixelWidth >= 20) {
                    labelContent = <span className="px-1 text-[9px] truncate font-mono">{seg.slide}</span>;
                  }
                } else {
                  if (durationPct >= 3.5) {
                    labelContent = <span className="px-1 text-[9px] truncate font-mono">Slide {seg.slide}</span>;
                  } else if (durationPct >= 1.5) {
                    labelContent = <span className="px-1 text-[9px] truncate font-mono">{seg.slide}</span>;
                  }
                }

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
                    className={`absolute top-0 bottom-0 text-[10px] font-bold transition-all duration-300 flex items-center justify-center hover:bg-blue-500/10 cursor-pointer overflow-hidden truncate ${
                      isActive
                        ? "bg-gradient-to-r from-blue-500/20 to-indigo-500/20 text-blue-400 border-b-2 border-blue-500 shadow-[inset_0_0_10px_rgba(59,130,246,0.15)]"
                        : isEven
                          ? "text-gray-400 bg-slate-800/30"
                          : "text-gray-400 bg-slate-700/20"
                    } ${showBorderRight ? "border-r border-gray-800/40" : ""}`}
                    style={{
                      left: `${startPct}%`,
                      width: `${durationPct}%`,
                      minWidth: "4px",
                    }}
                    title={`Slide ${seg.slide} (${formatTime(seg.start)} - ${formatTime(seg.end)})`}
                  >
                    {labelContent}
                  </button>
                );
              })}
            </div>
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
    </div>
  );
};
