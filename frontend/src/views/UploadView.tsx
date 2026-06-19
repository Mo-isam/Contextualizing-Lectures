import React, { useState, useRef } from "react";
import { ArrowLeft, Key, FileText, Video, HelpCircle, Settings, Play } from "lucide-react";

interface UploadViewProps {
  onBack: () => void;
  onStartProcessing: (config: any) => void;
}

export const UploadView: React.FC<UploadViewProps> = ({ onBack, onStartProcessing }) => {
  const [apiKey, setApiKey] = useState<string>(() => sessionStorage.getItem("api_key") || "");
  const [pdfFile, setPdfFile] = useState<File | null>(null);
  const [mediaFile, setMediaFile] = useState<File | null>(null);
  const [pipelineMode, setPipelineMode] = useState<"audio" | "visual">("audio");
  const [showAdvanced, setShowAdvanced] = useState<boolean>(false);
  const [uploading, setUploading] = useState<boolean>(false);
  const [uploadStatus, setUploadStatus] = useState<string>("");

  // Advanced settings defaults
  const [pdfEngine, setPdfEngine] = useState<string>("Native (PyMuPDF) - Fast");
  const [txEngine, setTxEngine] = useState<string>("Local Whisper (CPU) - Private");
  const [selectedModel, setSelectedModel] = useState<string>("gemini-3.5-flash");
  const [isPaidApi, setIsPaidApi] = useState<boolean>(false);

  const pdfInputRef = useRef<HTMLInputElement>(null);
  const mediaInputRef = useRef<HTMLInputElement>(null);

  const handleMediaChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setMediaFile(file);
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
    }
  };

  const executeUpload = async () => {
    if (!apiKey.trim()) {
      alert("Please enter a Gemini API Key.");
      return;
    }
    if (!pdfFile || !mediaFile) {
      alert("Please upload both slides and media files.");
      return;
    }

    setUploading(true);
    sessionStorage.setItem("api_key", apiKey);

    try {
      // 1. Upload PDF
      setUploadStatus("Uploading slide materials...");
      const pdfFormData = new FormData();
      pdfFormData.append("file", pdfFile);
      pdfFormData.append("file_type", "pdf");

      const pdfRes = await fetch("/api/upload", {
        method: "POST",
        body: pdfFormData,
      });
      if (!pdfRes.ok) throw new Error("Failed to upload presentation file.");
      const pdfData = await pdfRes.json();

      // 2. Upload Media
      setUploadStatus("Uploading lecture recording...");
      const mediaFormData = new FormData();
      mediaFormData.append("file", mediaFile);
      mediaFormData.append("file_type", "media");

      const mediaRes = await fetch("/api/upload", {
        method: "POST",
        body: mediaFormData,
      });
      if (!mediaRes.ok) throw new Error("Failed to upload recording file.");
      const mediaData = await mediaRes.json();

      // Pass relative paths and configurations forward
      onStartProcessing({
        pdf_path: pdfData.relative_path,
        media_path: mediaData.relative_path,
        pipeline_mode: pipelineMode,
        pdf_engine: pdfEngine,
        tx_engine: txEngine,
        selected_model: selectedModel,
        api_key: apiKey,
        is_paid_api: isPaidApi,
      });
    } catch (err: any) {
      alert(`Upload error: ${err.message}`);
    } finally {
      setUploading(false);
      setUploadStatus("");
    }
  };

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
          onClick={() => setShowAdvanced(!showAdvanced)}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg border text-sm font-medium transition-all cursor-pointer ${
            showAdvanced
              ? "bg-blue-500/10 border-blue-500/30 text-blue-400"
              : "bg-gray-900 border-gray-800 text-gray-300 hover:bg-gray-800"
          }`}
        >
          <Settings className="w-4 h-4" />
          Settings
        </button>
      </div>

      <h1 className="text-3xl font-extrabold text-gray-100 mb-2">Upload Lecture Materials</h1>
      <p className="text-gray-400 text-sm mb-8">
        Enter your credentials and upload your lecture slide deck and recording to execute alignment.
      </p>

      {/* Main Upload Box */}
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
            onChange={(e) => setApiKey(e.target.value)}
            className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/20 text-gray-200 placeholder-gray-600 rounded-xl px-4 py-3 text-sm outline-none transition-all"
          />
          <div className="text-[10px] text-gray-500 flex items-center gap-1.5 leading-relaxed pl-1">
            <HelpCircle className="w-3.5 h-3.5 flex-shrink-0" />
            <span>Used strictly for Slide OCR and semantic temporal alignment directly via Google AI Studio.</span>
          </div>
        </div>

        {/* Drag and Drop Grid */}
        <div className="grid md:grid-cols-2 gap-6">
          {/* PDF Box */}
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-300 flex items-center gap-2">
              <FileText className="w-4 h-4 text-blue-400" />
              2. Upload Lecture Slides
            </label>
            <div
              onClick={() => pdfInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all hover:bg-blue-500/5 ${
                pdfFile ? "border-green-500/40 bg-green-500/5" : "border-gray-800 hover:border-blue-500/30"
              }`}
            >
              <input
                ref={pdfInputRef}
                type="file"
                accept=".pdf,.pptx,.ppt"
                onChange={handlePdfChange}
                className="hidden"
              />
              <FileText className={`w-8 h-8 mx-auto mb-2 ${pdfFile ? "text-green-400" : "text-gray-500"}`} />
              <p className="text-xs font-semibold text-gray-300 truncate">
                {pdfFile ? pdfFile.name : "Select PDF or PPTX Slides"}
              </p>
              <p className="text-[10px] text-gray-500 mt-1">PDF, PPT, or PPTX up to 100MB</p>
            </div>
          </div>

          {/* Media Box */}
          <div className="space-y-2">
            <label className="text-sm font-bold text-gray-300 flex items-center gap-2">
              <Video className="w-4 h-4 text-blue-400" />
              3. Upload Lecture Recording
            </label>
            <div
              onClick={() => mediaInputRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-all hover:bg-blue-500/5 ${
                mediaFile ? "border-green-500/40 bg-green-500/5" : "border-gray-800 hover:border-blue-500/30"
              }`}
            >
              <input
                ref={mediaInputRef}
                type="file"
                accept=".mp3,.wav,.mp4"
                onChange={handleMediaChange}
                className="hidden"
              />
              <Video className={`w-8 h-8 mx-auto mb-2 ${mediaFile ? "text-green-400" : "text-gray-500"}`} />
              <p className="text-xs font-semibold text-gray-300 truncate">
                {mediaFile ? mediaFile.name : "Select Audio or Video File"}
              </p>
              <p className="text-[10px] text-gray-500 mt-1">MP4, MP3, or WAV up to 500MB</p>
            </div>
          </div>
        </div>

        {/* Pipeline Selection (shows if video is uploaded) */}
        {mediaFile && mediaFile.name.toLowerCase().endsWith(".mp4") && (
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

        {/* Advanced Settings Drawer */}
        {showAdvanced && (
          <div className="bg-[#0d1117] border border-gray-800 rounded-xl p-5 space-y-4 animate-fade-in">
            <h4 className="text-xs font-bold uppercase tracking-wider text-blue-400">⚙️ Pipeline Settings</h4>
            
            <div className="grid md:grid-cols-2 gap-4">
              <div className="space-y-1">
                <label className="text-[11px] text-gray-400 font-bold">Slide Text Extraction</label>
                <select
                  value={pdfEngine}
                  onChange={(e) => setPdfEngine(e.target.value)}
                  className="w-full bg-[#121820] border border-gray-800 rounded-lg p-2 text-xs text-gray-200 outline-none"
                >
                  <option>Native (PyMuPDF) - Fast</option>
                  <option>AI Vision (Gemini) - High Accuracy</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-gray-400 font-bold">Transcription Engine</label>
                <select
                  value={txEngine}
                  onChange={(e) => setTxEngine(e.target.value)}
                  className="w-full bg-[#121820] border border-gray-800 rounded-lg p-2 text-xs text-gray-200 outline-none"
                >
                  <option>Local Whisper (CPU) - Private</option>
                  <option>AI Audio (Gemini) - Fast/Cloud</option>
                </select>
              </div>

              <div className="space-y-1">
                <label className="text-[11px] text-gray-400 font-bold">Default Model ID</label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="w-full bg-[#121820] border border-gray-800 rounded-lg p-2 text-xs text-gray-200 outline-none"
                >
                  <option value="gemini-3.5-flash">Gemini 3.5 Flash (Auto/Priority)</option>
                  <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                </select>
              </div>

              <div className="space-y-2 flex flex-col justify-end">
                <label className="flex items-center gap-2 select-none cursor-pointer text-xs text-gray-300 pl-1 pb-1">
                  <input
                    type="checkbox"
                    checked={isPaidApi}
                    onChange={(e) => setIsPaidApi(e.target.checked)}
                    className="rounded accent-blue-500"
                  />
                  <span>Paid API Tier Quota (Disable rate pacing)</span>
                </label>
              </div>
            </div>
          </div>
        )}

        {/* Submit */}
        {uploading ? (
          <div className="bg-blue-500/10 border border-blue-500/20 rounded-xl p-4 flex items-center justify-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-400"></div>
            <span className="text-xs text-gray-300 font-medium">{uploadStatus}</span>
          </div>
        ) : (
          <button
            onClick={executeUpload}
            className="w-full py-3.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white font-bold rounded-xl shadow-lg hover:shadow-blue-500/20 transition-all flex items-center justify-center gap-2 cursor-pointer text-sm"
          >
            <Play className="w-4 h-4 fill-current" />
            Run Alignment Pipeline
          </button>
        )}
      </div>
    </div>
  );
};
