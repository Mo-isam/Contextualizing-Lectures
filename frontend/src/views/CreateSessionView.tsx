import React, { useState, useRef, useEffect } from "react";
import { ArrowLeft, Key, FileText, Video, HelpCircle, Settings, Play, AlertCircle, Database, UploadCloud } from "lucide-react";
import { SettingsModal } from "../components/SettingsModal";
import { ApiService } from "../services/api";

interface CreateSessionViewProps {
  onBack: () => void;
  onStartProcessing: (config: any) => void;
}

interface StoredFile {
  name: string;
  relative_path: string;
  size_bytes: number;
  modified_time: number;
}

export const CreateSessionView: React.FC<CreateSessionViewProps> = ({ onBack, onStartProcessing }) => {
  const [apiKey, setApiKey] = useState<string>(() => sessionStorage.getItem("api_key") || "");
  
  // File sources: "upload" vs "existing"
  const [pdfSource, setPdfSource] = useState<"upload" | "existing">("upload");
  const [mediaSource, setMediaSource] = useState<"upload" | "existing">("upload");

  // Upload source files
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [mediaFile, setMediaFile] = useState<File | null>(null);

  // Existing source files selection
  const [selectedPdfPath, setSelectedPdfPath] = useState<string | null>(null);
  const [selectedMediaPath, setSelectedMediaPath] = useState<string | null>(null);

  // Stored library files
  const [storedDocs, setStoredDocs] = useState<StoredFile[]>([]);
  const [storedMedia, setStoredMedia] = useState<StoredFile[]>([]);
  const [loadingFiles, setLoadingFiles] = useState<boolean>(false);

  const [pipelineMode, setPipelineMode] = useState<"audio" | "visual">("audio");
  const [showSettingsModal, setShowSettingsModal] = useState<boolean>(false);
  const [processing, setProcessing] = useState<boolean>(false);
  const [processingStatus, setProcessingStatus] = useState<string>("");

  // Validation and Error states
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [apiKeyError, setApiKeyError] = useState<boolean>(false);
  const [filesError, setFilesError] = useState<boolean>(false);

  // Advanced settings defaults synced with config.yaml
  const [pdfEngine, setPdfEngine] = useState<string>("Native (PyMuPDF) - Fast");
  const [txEngine, setTxEngine] = useState<string>("Local Whisper (CPU) - Private");
  const [selectedModel, setSelectedModel] = useState<string>("gemini-3.5-flash");
  const [isPaidApi, setIsPaidApi] = useState<boolean>(false);

  const fetchConfig = () => {
    ApiService.getConfig()
      .then((data) => {
        setIsPaidApi(data.ui_defaults.is_paid_api);
        setSelectedModel(data.ui_defaults.default_model);
        setPdfEngine(data.ui_defaults.pdf_engine);
        setTxEngine(data.ui_defaults.tx_engine);
      })
      .catch((err) => console.error("Error loading config:", err));
  };

  const fetchStoredFiles = async () => {
    setLoadingFiles(true);
    try {
      const data = await ApiService.getStoredFiles();
      setStoredDocs(data.documents);
      setStoredMedia(data.media);
    } catch (err) {
      console.error("Error loading stored files:", err);
    } finally {
      setLoadingFiles(false);
    }
  };

  useEffect(() => {
    fetchConfig();
    fetchStoredFiles();
  }, []);

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);

  const handleMediaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setMediaFile(file);
      setFilesError(false);
      if (errorMessage?.includes("select") || errorMessage?.includes("upload")) setErrorMessage(null);
      if (file.name.toLowerCase().endsWith(".mp4")) {
        setPipelineMode("visual");
      } else {
        setPipelineMode("audio");
      }
    }
  };

  const handlePdfChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setPdfFile(e.target.files[0]);
      setFilesError(false);
      if (errorMessage?.includes("select") || errorMessage?.includes("upload")) setErrorMessage(null);
    }
  };

  const handleSelectPdf = (path: string) => {
    setSelectedPdfPath(path);
    setFilesError(false);
    if (errorMessage?.includes("select") || errorMessage?.includes("upload")) setErrorMessage(null);
  };

  const handleSelectMedia = (path: string) => {
    setSelectedMediaPath(path);
    setFilesError(false);
    if (errorMessage?.includes("select") || errorMessage?.includes("upload")) setErrorMessage(null);
    if (path.toLowerCase().endsWith(".mp4")) {
      setPipelineMode("visual");
    } else {
      setPipelineMode("audio");
    }
  };

  const executeCreateSession = async () => {
    setErrorMessage(null);
    setApiKeyError(false);
    setFilesError(false);

    if (!apiKey.trim()) {
      setApiKeyError(true);
      setErrorMessage("Gemini API Key is required to run the alignment pipeline.");
      return;
    }

    // Verify slide selection
    if (pdfSource === "upload" && !pdfFile) {
      setFilesError(true);
      setErrorMessage("Please select or upload a Lecture Slide deck.");
      return;
    }
    if (pdfSource === "existing" && !selectedPdfPath) {
      setFilesError(true);
      setErrorMessage("Please select an existing Lecture Slide deck from storage.");
      return;
    }

    // Verify recording selection
    if (mediaSource === "upload" && !mediaFile) {
      setFilesError(true);
      setErrorMessage("Please select or upload an Audio/Video recording.");
      return;
    }
    if (mediaSource === "existing" && !selectedMediaPath) {
      setFilesError(true);
      setErrorMessage("Please select an existing Audio/Video recording from storage.");
      return;
    }

    setProcessing(true);
    sessionStorage.setItem("api_key", apiKey);

    try {
      let resolvedPdfPath = "";
      let resolvedMediaPath = "";

      // 1. Resolve PDF Path
      if (pdfSource === "upload" && pdfFile) {
        setProcessingStatus("Uploading slide materials...");
        const pdfData = await ApiService.uploadFile(pdfFile, "pdf");
        resolvedPdfPath = pdfData.relative_path;
      } else if (selectedPdfPath) {
        resolvedPdfPath = selectedPdfPath;
      }

      // 2. Resolve Media Path
      if (mediaSource === "upload" && mediaFile) {
        setProcessingStatus("Uploading lecture recording...");
        const mediaData = await ApiService.uploadFile(mediaFile, "media");
        resolvedMediaPath = mediaData.relative_path;
      } else if (selectedMediaPath) {
        resolvedMediaPath = selectedMediaPath;
      }

      // Pass relative paths and configurations forward
      onStartProcessing({
        pdf_path: resolvedPdfPath,
        media_path: resolvedMediaPath,
        pipeline_mode: pipelineMode,
        pdf_engine: pdfEngine,
        tx_engine: txEngine,
        selected_model: selectedModel,
        api_key: apiKey,
        is_paid_api: isPaidApi,
      });
    } catch (err: any) {
      setErrorMessage(`Failed to initialize session: ${err.message}`);
    } finally {
      setProcessing(false);
      setProcessingStatus("");
    }
  };

  // Helper formatting functions
  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + " " + sizes[i];
  };

  const formatFriendlyDate = (timestamp: number): string => {
    const date = new Date(timestamp * 1000);
    return date.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  };

  // Check if active media file/path is a video (.mp4)
  const isVideoSelected =
    (mediaSource === "upload" && mediaFile && mediaFile.name.toLowerCase().endsWith(".mp4")) ||
    (mediaSource === "existing" && selectedMediaPath && selectedMediaPath.toLowerCase().endsWith(".mp4"));

  return (
    <div className="max-w-3xl mx-auto py-10 px-6 animate-fade-in">
      {/* Header Bar */}
      <div className="flex items-center justify-between mb-8 pb-4 border-b border-gray-800">
        <button
          onClick={onBack}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 border border-gray-800 hover:bg-gray-800 hover:border-gray-700 text-gray-300 font-medium text-sm transition-all cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Home
        </button>

        <button
          onClick={() => setShowSettingsModal(true)}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-gray-900 border border-gray-800 text-gray-300 hover:bg-gray-800 hover:border-gray-700 transition-all cursor-pointer text-sm font-medium"
        >
          <Settings className="w-4 h-4" />
          Settings
        </button>
      </div>

      <h1 className="text-3xl font-extrabold text-gray-100 mb-2">Create Lecture Session</h1>
      <p className="text-gray-400 text-sm mb-8">
        Configure credentials, load your lecture slide deck and recording, and launch the concept alignment pipeline.
      </p>

      {/* Main Form Box */}
      <div className="bg-[#121820]/90 border border-gray-800/80 rounded-2xl p-6 shadow-xl space-y-6">
        {/* API Key */}
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm font-bold text-gray-300">
            <Key className="w-4 h-4 text-blue-400" />
            1. Enter Gemini API Key
          </label>
          <input
            type="password"
            placeholder="AIzaSy... (Saved locally in session memory)"
            value={apiKey}
            onChange={(e) => {
              setApiKey(e.target.value);
              if (e.target.value.trim()) {
                setApiKeyError(false);
                if (errorMessage?.includes("API Key")) setErrorMessage(null);
              }
            }}
            className={`w-full bg-[#0d1117] border focus:ring-1 focus:ring-blue-500/20 text-gray-200 placeholder-gray-600 rounded-xl px-4 py-3 text-sm outline-none transition-all ${
              apiKeyError 
                ? "border-red-500/80 focus:border-red-500 focus:ring-red-500/10" 
                : "border-gray-800 focus:border-blue-500 focus:ring-blue-500/10"
            }`}
          />
          <div className="text-[10px] text-gray-500 flex items-center gap-1.5 leading-relaxed pl-1">
            <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Used strictly for Slide OCR and semantic temporal alignment directly via Google AI Studio.</span>
          </div>
        </div>

        {/* Input Source Grid */}
        <div className="grid md:grid-cols-2 gap-6">
          
          {/* Slide Deck Container */}
          <div className="space-y-2 flex flex-col">
            <div className="flex items-center justify-between">
              <label className="text-sm font-bold text-gray-300 flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                2. Lecture Slides
              </label>
              
              {/* Toggle Switch */}
              <label className="relative inline-flex items-center cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={pdfSource === "existing"}
                  onChange={(e) => setPdfSource(e.target.checked ? "existing" : "upload")}
                  className="sr-only peer"
                />
                <div className="w-8 h-4.5 bg-gray-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[3px] after:start-[3px] after:bg-gray-500 peer-checked:after:bg-blue-400 after:border-transparent after:border after:rounded-full after:h-3 w-7.5 after:w-3 after:transition-all peer-checked:bg-blue-900/40 border border-gray-700/50"></div>
                <span className="ms-1.5 text-[10px] font-semibold text-gray-400 peer-checked:text-blue-400">
                  Use Library
                </span>
              </label>
            </div>

            {pdfSource === "upload" ? (
              <div
                onClick={() => pdfInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer flex-grow flex flex-col justify-center transition-all hover:bg-blue-500/5 min-h-[148px] ${
                  pdfFile 
                    ? "border-green-500/40 bg-green-500/5" 
                    : filesError 
                    ? "border-red-500/45 bg-red-500/5 animate-pulse" 
                    : "border-gray-800 hover:border-blue-500/30"
                }`}
              >
                <input
                  ref={pdfInputRef}
                  type="file"
                  accept=".pdf,.pptx,.ppt"
                  onChange={handlePdfChange}
                  className="hidden"
                />
                <UploadCloud className={`w-7 h-7 mx-auto mb-1.5 ${pdfFile ? "text-green-400" : "text-gray-500"}`} />
                <p className="text-xs font-semibold text-gray-300 truncate">
                  {pdfFile ? pdfFile.name : "Select PDF or PPTX Slides"}
                </p>
                <p className="text-[9px] text-gray-500 mt-0.5">PDF, PPT, or PPTX up to 100MB</p>
              </div>
            ) : (
              <div className="border border-gray-800 rounded-xl bg-[#0d1117] min-h-[148px] max-h-[148px] overflow-y-auto p-1.5 space-y-1 scrollbar-thin select-none">
                {loadingFiles ? (
                  <div className="text-[10px] text-gray-500 text-center py-10">Loading stored documents...</div>
                ) : storedDocs.length === 0 ? (
                  <div className="text-[10px] text-gray-500 text-center py-10 flex flex-col items-center justify-center gap-1">
                    <Database className="w-5 h-5 text-gray-600" />
                    <span>No documents in data_storage/</span>
                  </div>
                ) : (
                  storedDocs.map((doc) => (
                    <div
                      key={doc.relative_path}
                      onClick={() => handleSelectPdf(doc.relative_path)}
                      className={`flex items-start gap-2.5 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedPdfPath === doc.relative_path
                          ? "bg-blue-600/10 border-blue-500/40 text-gray-200"
                          : "bg-transparent border-transparent hover:bg-gray-800/40 text-gray-400 hover:text-gray-200"
                      }`}
                    >
                      <FileText className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${selectedPdfPath === doc.relative_path ? "text-blue-400" : "text-gray-500"}`} />
                      <div className="min-w-0 flex-grow">
                        <div className="text-[11px] font-semibold leading-normal truncate">{doc.name}</div>
                        <div className="text-[9px] opacity-75 mt-0.5 flex gap-2">
                          <span>{formatFileSize(doc.size_bytes)}</span>
                          <span>•</span>
                          <span>{formatFriendlyDate(doc.modified_time)}</span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>

          {/* Lecture Recording Container */}
          <div className="space-y-2 flex flex-col">
            <div className="flex items-center justify-between">
              <label className="text-sm font-bold text-gray-300 flex items-center gap-2">
                <Video className="w-4 h-4 text-blue-400" />
                3. Lecture Recording
              </label>

              {/* Toggle Switch */}
              <label className="relative inline-flex items-center cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={mediaSource === "existing"}
                  onChange={(e) => setMediaSource(e.target.checked ? "existing" : "upload")}
                  className="sr-only peer"
                />
                <div className="w-8 h-4.5 bg-gray-800 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[3px] after:start-[3px] after:bg-gray-500 peer-checked:after:bg-blue-400 after:border-transparent after:border after:rounded-full after:h-3 w-7.5 after:w-3 after:transition-all peer-checked:bg-blue-900/40 border border-gray-700/50"></div>
                <span className="ms-1.5 text-[10px] font-semibold text-gray-400 peer-checked:text-blue-400">
                  Use Library
                </span>
              </label>
            </div>

            {mediaSource === "upload" ? (
              <div
                onClick={() => mediaInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-5 text-center cursor-pointer flex-grow flex flex-col justify-center transition-all hover:bg-blue-500/5 min-h-[148px] ${
                  mediaFile 
                    ? "border-green-500/40 bg-green-500/5" 
                    : filesError 
                    ? "border-red-500/45 bg-red-500/5 animate-pulse" 
                    : "border-gray-800 hover:border-blue-500/30"
                }`}
              >
                <input
                  ref={mediaInputRef}
                  type="file"
                  accept=".mp3,.wav,.mp4"
                  onChange={handleMediaChange}
                  className="hidden"
                />
                <UploadCloud className={`w-7 h-7 mx-auto mb-1.5 ${mediaFile ? "text-green-400" : "text-gray-500"}`} />
                <p className="text-xs font-semibold text-gray-300 truncate">
                  {mediaFile ? mediaFile.name : "Select Audio or Video File"}
                </p>
                <p className="text-[9px] text-gray-500 mt-0.5">MP4, MP3, or WAV up to 500MB</p>
              </div>
            ) : (
              <div className="border border-gray-800 rounded-xl bg-[#0d1117] min-h-[148px] max-h-[148px] overflow-y-auto p-1.5 space-y-1 scrollbar-thin select-none">
                {loadingFiles ? (
                  <div className="text-[10px] text-gray-500 text-center py-10">Loading stored media...</div>
                ) : storedMedia.length === 0 ? (
                  <div className="text-[10px] text-gray-500 text-center py-10 flex flex-col items-center justify-center gap-1">
                    <Database className="w-5 h-5 text-gray-600" />
                    <span>No media in data_storage/</span>
                  </div>
                ) : (
                  storedMedia.map((media) => (
                    <div
                      key={media.relative_path}
                      onClick={() => handleSelectMedia(media.relative_path)}
                      className={`flex items-start gap-2.5 p-2 rounded-lg cursor-pointer transition-all border ${
                        selectedMediaPath === media.relative_path
                          ? "bg-blue-600/10 border-blue-500/40 text-gray-200"
                          : "bg-transparent border-transparent hover:bg-gray-800/40 text-gray-400 hover:text-gray-200"
                      }`}
                    >
                      <Video className={`w-3.5 h-3.5 flex-shrink-0 mt-0.5 ${selectedMediaPath === media.relative_path ? "text-blue-400" : "text-gray-500"}`} />
                      <div className="min-w-0 flex-grow">
                        <div className="text-[11px] font-semibold leading-normal truncate">{media.name}</div>
                        <div className="text-[9px] opacity-75 mt-0.5 flex gap-2">
                          <span>{formatFileSize(media.size_bytes)}</span>
                          <span>•</span>
                          <span>{formatFriendlyDate(media.modified_time)}</span>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            )}
          </div>
        </div>

        {/* Pipeline Selection (shows if video is selected) */}
        {isVideoSelected && (
          <div className="bg-[#1c2330]/50 border border-blue-500/10 rounded-xl p-4 animate-fade-in space-y-3">
            <div className="text-xs text-blue-400 font-bold">🎬 Video File Detected!</div>
            <p className="text-[11px] text-gray-400 leading-normal">
              You can run the Visual Pipeline to deterministically extract slide changes directly from the screen, or use the semantic Audio-Only model.
            </p>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 bg-gray-900 border border-gray-800 px-4 py-2.5 rounded-lg cursor-pointer text-xs select-none">
                <input
                  type="radio"
                  checked={pipelineMode === "visual"}
                  onChange={() => setPipelineMode("visual")}
                  className="accent-blue-500"
                />
                <span className="font-semibold text-gray-200">🎞️ Visual Pipeline (Deterministic & Fast)</span>
              </label>
              <label className="flex items-center gap-2 bg-gray-900 border border-gray-800 px-4 py-2.5 rounded-lg cursor-pointer text-xs select-none">
                <input
                  type="radio"
                  checked={pipelineMode === "audio"}
                  onChange={() => setPipelineMode("audio")}
                  className="accent-blue-500"
                />
                <span className="font-semibold text-gray-200">🎙️ Audio-Only Pipeline (Semantic AI)</span>
              </label>
            </div>
          </div>
        )}

        {/* Validation Error Banner */}
        {errorMessage && (
          <div className="bg-red-500/10 border border-red-500/25 rounded-xl p-4 flex items-start gap-3 text-red-400 animate-fade-in">
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <h5 className="font-bold text-xs">Validation Failed</h5>
              <p className="text-[11px] leading-relaxed opacity-95">{errorMessage}</p>
            </div>
          </div>
        )}

        {/* Submit */}
        {processing ? (
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-center justify-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-400"></div>
            <span className="text-xs text-gray-300 font-medium">{processingStatus}</span>
          </div>
        ) : (
          <button
            onClick={executeCreateSession}
            className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-bold rounded-xl shadow-lg hover:shadow-blue-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm"
          >
            <Play className="w-4 h-4 fill-current" />
            Run Alignment Pipeline
          </button>
        )}
      </div>

      {showSettingsModal && (
        <SettingsModal
          onClose={() => setShowSettingsModal(false)}
          onSave={fetchConfig}
        />
      )}
    </div>
  );
};
