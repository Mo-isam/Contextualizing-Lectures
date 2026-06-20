import { useEffect, useRef, useState, useCallback } from "react";
import WaveSurfer from "wavesurfer.js";

interface UseWaveSurferProps {
  url: string;
  peaks?: number[];
  onTimeUpdate: (time: number) => void;
}

export function useWaveSurfer({ url, peaks, onTimeUpdate }: UseWaveSurferProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<WaveSurfer | null>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [currentTime, setCurrentTime] = useState<number>(0);
  const [duration, setDuration] = useState<number>(0);

  // Keep callback reference updated without triggering effect restarts
  const onTimeUpdateRef = useRef(onTimeUpdate);
  useEffect(() => {
    onTimeUpdateRef.current = onTimeUpdate;
  }, [onTimeUpdate]);

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
        peaks: peaks ? [peaks] : undefined,
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
        onTimeUpdateRef.current(time);
      });

      ws.on("timeupdate", () => {
        const time = ws.getCurrentTime();
        setCurrentTime(time);
        onTimeUpdateRef.current(time);
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
      setIsPlaying(false);
      setCurrentTime(0);
      setDuration(0);
    };
  }, [url, peaks]);

  const togglePlay = useCallback(() => {
    if (wavesurferRef.current) {
      wavesurferRef.current.playPause();
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (wavesurferRef.current) {
      const nextMute = !isMuted;
      wavesurferRef.current.setMuted(nextMute);
      setIsMuted(nextMute);
    }
  }, [isMuted]);

  const seekToTime = useCallback((time: number) => {
    if (wavesurferRef.current) {
      wavesurferRef.current.setTime(time);
    }
  }, []);

  return {
    containerRef,
    wavesurfer: wavesurferRef.current,
    isPlaying,
    isMuted,
    currentTime,
    duration,
    togglePlay,
    toggleMute,
    seekToTime,
  };
}
