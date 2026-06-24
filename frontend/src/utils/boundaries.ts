import type { AlignedNote } from "../types";

export interface SlideBoundary {
  slide: number;
  start: number;
  end: number;
}

/**
 * Computes non-overlapping slide boundaries from AlignedNotes.
 * Caps the end of each segment at the start of the next segment to avoid overlap.
 */
export function calculateSlideBoundaries(notes: AlignedNote[]): SlideBoundary[] {
  if (!notes || notes.length === 0) return [];
  
  // 1. Sort by timestamp_start
  const sortedNotes = [...notes]
    .sort((a, b) => a.timestamp_start - b.timestamp_start);

  if (sortedNotes.length === 0) return [];

  // 2. Group contiguous notes of the same slide together
  const segments: SlideBoundary[] = [];
  sortedNotes.forEach((n) => {
    const last = segments[segments.length - 1];
    if (!last || last.slide !== n.slide_number) {
      segments.push({
        slide: n.slide_number,
        start: n.timestamp_start,
        end: n.timestamp_end,
      });
    } else {
      last.end = Math.max(last.end, n.timestamp_end);
    }
  });

  // 3. Resolve overlaps by capping the end of each segment at the start of the next
  return segments.map((seg, idx) => {
    const nextSeg = segments[idx + 1];
    const adjustedEnd = nextSeg ? Math.min(seg.end, nextSeg.start) : seg.end;
    return {
      slide: seg.slide,
      start: seg.start,
      end: Math.max(seg.start + 0.1, adjustedEnd),
    };
  });
}

/**
 * Find the slide number active at a given playhead timestamp.
 */
export function getSlideAtTime(time: number, slideBoundaries: SlideBoundary[]): number | null {
  let bestSlide = null;
  for (const seg of slideBoundaries) {
    if (seg.slide !== 0 && time >= seg.start) {
      bestSlide = seg.slide;
    }
  }
  return bestSlide;
}

/**
 * Format a duration in seconds to standard clock format (hh:mm:ss or mm:ss).
 */
export function formatTime(time: number): string {
  const s = Math.max(0, Math.floor(time));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h) {
    return `${h}:${m.toString().padStart(2, "0")}:${sec.toString().padStart(2, "0")}`;
  }
  return `${m}:${sec.toString().padStart(2, "0")}`;
}
