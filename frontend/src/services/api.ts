import type { LectureSession, SavedSessionInfo } from "../types";

export interface ApiConfig {
  ui_defaults: {
    is_paid_api: boolean;
    default_model: string;
    selected_model_label: string;
    pdf_engine: string;
    tx_engine: string;
  };
  audio: {
    whisper_model_size: string;
    sample_rate: number;
  };
  alignment: {
    min_chunk_duration_sec: number;
    max_chunk_duration_sec: number;
  };
  pdf: {
    render_zoom: number;
  };
  video: {
    matching_strategy: string;
    frame_sample_rate: number;
    ssim_threshold: number;
  };
  model_options: Record<string, string>;
}

export const ApiService = {
  /**
   * Get dynamic WebSocket URL that works with Vite proxies and production servers.
   */
  getWebSocketUrl(): string {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    // By using window.location.host, we leverage the Vite proxy (localhost:5173 -> localhost:8000)
    // or standard production domain mappings without hardcoding port 8000.
    return `${protocol}//${window.location.host}/api/process/stream`;
  },

  /**
   * Get relative data paths for slide images, transcripts, etc.
   */
  getDataUrl(path: string): string {
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https:") || path.startsWith("/")) {
      return path;
    }
    return `/data/${path}`;
  },

  /**
   * Get relative tmp paths.
   */
  getTmpUrl(path: string): string {
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https:") || path.startsWith("/")) {
      return path;
    }
    return `/tmp/${path}`;
  },

  /**
   * Get list of all saved sessions in the local library.
   */
  async getSessions(): Promise<SavedSessionInfo[]> {
    const res = await fetch("/api/sessions");
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to list sessions");
    }
    return res.json();
  },

  /**
   * Retrieve and deserialize a specific session.
   */
  async getSession(filename: string): Promise<LectureSession & { slide_images: string[] }> {
    const res = await fetch(`/api/session/${filename}`);
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `Failed to load session: ${filename}`);
    }
    return res.json();
  },

  /**
   * Save session details to persistent storage.
   */
  async saveSession(payload: LectureSession): Promise<{ status: string; filename: string }> {
    const res = await fetch("/api/session/save", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to save session");
    }
    return res.json();
  },

  /**
   * Update name and description of a session.
   */
  async updateSessionMetadata(filename: string, name: string, description: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`/api/session/${filename}/metadata`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_name: name, session_description: description }),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to update session metadata");
    }
    return res.json();
  },

  /**
   * Delete a session.
   */
  async deleteSession(filename: string): Promise<{ status: string; message: string }> {
    const res = await fetch(`/api/session/${filename}`, {
      method: "DELETE",
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to delete session");
    }
    return res.json();
  },

  /**
   * Retrieve configuration settings.
   */
  async getConfig(): Promise<ApiConfig> {
    const res = await fetch("/api/config");
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to fetch configuration");
    }
    return res.json();
  },

  /**
   * Save configuration updates persistently.
   */
  async saveConfig(payload: Partial<ApiConfig["ui_defaults"] & ApiConfig["audio"] & ApiConfig["alignment"] & ApiConfig["pdf"] & ApiConfig["video"]>): Promise<{ status: string; message: string }> {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to save configuration");
    }
    return res.json();
  },

  /**
   * Retrieve list of files stored in data_storage files directories.
   */
  async getStoredFiles(): Promise<{
    documents: Array<{ name: string; relative_path: string; size_bytes: number; modified_time: number }>;
    media: Array<{ name: string; relative_path: string; size_bytes: number; modified_time: number }>;
  }> {
    const res = await fetch("/api/files");
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || "Failed to list stored files");
    }
    return res.json();
  },

  /**
   * Upload PDF or media file, including auto-converting PPTX to PDF.
   */
  async uploadFile(
    file: File,
    fileType: "pdf" | "media"
  ): Promise<{ filename: string; absolute_path: string; relative_path: string }> {
    const formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);

    const res = await fetch("/api/upload", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(err || `Failed to upload ${fileType} file`);
    }
    return res.json();
  },
};
