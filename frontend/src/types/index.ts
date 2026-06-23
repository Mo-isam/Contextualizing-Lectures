export interface TranscriptSegment {
  id: number;
  start: number;
  end: number;
  text: string;
}

export interface Slide {
  page_number: number;
  title: string;
  text: string;
}

export interface AlignedNote {
  slide_number: number;
  slide_title: string;
  exact_transcript: string;
  ai_insight: string;
  timestamp_start: number;
  timestamp_end: number;
  is_off_topic: boolean;
}

export interface LectureSession {
  session_name: string;
  session_description?: string;
  session_id?: string;
  pdf_path?: string;
  media_path?: string;
  transcript_segments?: TranscriptSegment[];
  slides?: Slide[];
  final_output?: AlignedNote[];
  timestamp?: number;
  pipeline_type?: "audio" | "visual";
  peaks?: number[];
}

export interface SavedSessionInfo {
  name: string;
  description: string;
  id: string;
  filename: string;
  timestamp: number;
  pipeline_type: "audio" | "visual";
}

export interface ProgressUpdate {
  status: "processing" | "complete" | "error";
  stage?: "preflight" | "pdf" | "video" | "audio" | "alignment";
  progress?: number;
  message?: string;
  models_list?: string[];
  active_model?: string | null;
  model_status?: "active" | "warning" | "error" | null;
  model_message?: string | null;
  dead_models?: string[];
  model_call_stats?: Record<string, { success: number; failure: number }> | null;
  data?: {
    transcript_segments: TranscriptSegment[];
    slides: Slide[];
    final_output: AlignedNote[];
    slide_images: string[];
    peaks?: number[];
  };
}
