import React, { useEffect, useState } from "react";
import {
  Settings,
  Save,
  X,
  Info,
  GripVertical,
  ArrowUp,
  ArrowDown,
  RotateCcw,
  Sparkles,
  AudioLines,
  Sliders,
  AlertTriangle,
  CheckCircle
} from "lucide-react";
import { ApiService } from "../services/api";

interface SettingsModalProps {
  onClose: () => void;
  onSave: () => void;
}

type SettingsTab = "general" | "priority" | "audio" | "video";

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onSave }) => {
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);
  const [resetting, setResetting] = useState<boolean>(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [showResetSuccess, setShowResetSuccess] = useState<boolean>(false);

  // General settings state
  const [isPaidApi, setIsPaidApi] = useState<boolean>(false);
  const [defaultModel, setDefaultModel] = useState<string>("gemini-3.5-flash");
  const [pdfEngine, setPdfEngine] = useState<string>("Native (PyMuPDF) - Fast");
  const [txEngine, setTxEngine] = useState<string>("Local Whisper (CPU) - Private");
  const [modelOptions, setModelOptions] = useState<Record<string, string>>({});

  // Model fallback priority state
  const [modelPriority, setModelPriority] = useState<string[]>([]);
  const [rpmLimits, setRpmLimits] = useState<Record<string, number>>({});
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);

  // Audio/Transcription settings state
  const [whisperModelSize, setWhisperModelSize] = useState<string>("base");
  const [sampleRate, setSampleRate] = useState<number>(16000);
  const [minChunkDuration, setMinChunkDuration] = useState<number>(180);
  const [maxChunkDuration, setMaxChunkDuration] = useState<number>(300);

  // Video/PDF matching settings state
  const [renderZoom, setRenderZoom] = useState<number>(2.0);
  const [matchingStrategy, setMatchingStrategy] = useState<string>("hybrid");
  const [frameSampleRate, setFrameSampleRate] = useState<number>(1);
  const [ssimThreshold, setSsimThreshold] = useState<number>(0.85);

  const loadConfig = () => {
    setLoading(true);
    ApiService.getConfig()
      .then((data) => {
        setIsPaidApi(data.ui_defaults.is_paid_api);
        setDefaultModel(data.ui_defaults.default_model);
        setPdfEngine(data.ui_defaults.pdf_engine);
        setTxEngine(data.ui_defaults.tx_engine);
        setModelOptions(data.model_options || {});
        setModelPriority(data.model_priority || []);
        setRpmLimits(data.rpm_limits || {});

        setWhisperModelSize(data.audio.whisper_model_size);
        setSampleRate(data.audio.sample_rate);
        setMinChunkDuration(data.alignment.min_chunk_duration_sec);
        setMaxChunkDuration(data.alignment.max_chunk_duration_sec);
        setRenderZoom(data.pdf.render_zoom);
        setMatchingStrategy(data.video.matching_strategy);
        setFrameSampleRate(data.video.frame_sample_rate);
        setSsimThreshold(data.video.ssim_threshold);
        setLoading(false);
      })
      .catch((err) => {
        alert(err.message);
        setLoading(false);
      });
  };

  useEffect(() => {
    loadConfig();
  }, []);

  // Validate settings inputs
  const validateForm = (): boolean => {
    if (minChunkDuration <= 0) {
      setValidationError("Minimum chunk duration must be a positive number.");
      setActiveTab("audio");
      return false;
    }
    if (maxChunkDuration <= 0) {
      setValidationError("Maximum chunk duration must be a positive number.");
      setActiveTab("audio");
      return false;
    }
    if (minChunkDuration >= maxChunkDuration) {
      setValidationError("Minimum chunk duration must be strictly less than maximum chunk duration.");
      setActiveTab("audio");
      return false;
    }
    if (sampleRate < 8000 || sampleRate > 48000) {
      setValidationError("Audio sample rate should be between 8,000 Hz and 48,000 Hz.");
      setActiveTab("audio");
      return false;
    }
    if (renderZoom < 1.0 || renderZoom > 4.0) {
      setValidationError("Render zoom should be between 1.0 (standard) and 4.0 (ultra crisp).");
      setActiveTab("video");
      return false;
    }
    if (frameSampleRate <= 0) {
      setValidationError("Frame sample rate must be at least 1 frame per second.");
      setActiveTab("video");
      return false;
    }
    setValidationError(null);
    return true;
  };

  const handleSave = async () => {
    if (!validateForm()) return;
    setSaving(true);
    try {
      await ApiService.saveConfig({
        is_paid_api: isPaidApi,
        default_model: defaultModel,
        pdf_engine: pdfEngine,
        tx_engine: txEngine,
        whisper_model_size: whisperModelSize,
        sample_rate: sampleRate,
        min_chunk_duration_sec: minChunkDuration,
        max_chunk_duration_sec: maxChunkDuration,
        render_zoom: renderZoom,
        matching_strategy: matchingStrategy,
        frame_sample_rate: frameSampleRate,
        ssim_threshold: ssimThreshold,
        model_priority: modelPriority,
      });
      onSave();
      onClose();
    } catch (err: any) {
      alert(`Save settings error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleFactoryReset = async () => {
    const confirmReset = window.confirm(
      "Are you sure you want to reset all pipeline settings and model fallback priority to factory defaults?"
    );
    if (!confirmReset) return;

    setResetting(true);
    try {
      await ApiService.resetConfig();
      setShowResetSuccess(true);
      setTimeout(() => setShowResetSuccess(false), 3000);
      loadConfig();
    } catch (err: any) {
      alert(`Failed to reset configurations: ${err.message}`);
    } finally {
      setResetting(false);
    }
  };

  // Drag and Drop reordering logic
  const handleDragStart = (e: React.DragEvent, index: number) => {
    setDraggedIndex(index);
    e.dataTransfer.effectAllowed = "move";
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
  };

  const handleDragEnter = (e: React.DragEvent, targetIndex: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === targetIndex) return;

    const list = [...modelPriority];
    const draggedItem = list[draggedIndex];
    list.splice(draggedIndex, 1);
    list.splice(targetIndex, 0, draggedItem);

    setDraggedIndex(targetIndex);
    setModelPriority(list);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const moveItem = (index: number, direction: "up" | "down") => {
    if (direction === "up" && index === 0) return;
    if (direction === "down" && index === modelPriority.length - 1) return;

    const list = [...modelPriority];
    const targetIndex = direction === "up" ? index - 1 : index + 1;
    const temp = list[index];
    list[index] = list[targetIndex];
    list[targetIndex] = temp;
    setModelPriority(list);
  };

  // Look up display name for target model ID
  const getModelLabel = (modelId: string): string => {
    const entry = Object.entries(modelOptions).find(([_, id]) => id === modelId);
    return entry ? entry[0] : modelId;
  };

  // Human-readable SSIM descriptors
  const getSsimDescription = (val: number): string => {
    if (val < 0.70) return "Very Low (Triggers slide cuts only on extreme layout transitions)";
    if (val < 0.80) return "Low (Ignores minor layout shifts, captures distinct slide changes)";
    if (val < 0.88) return "Balanced (Recommended: ideal for standard text/slide lectures)";
    if (val < 0.95) return "Strict (Captures tiny slide updates or line-by-line list bullet builds)";
    return "Ultra (Triggers on micro-motions, cursor pointer changes, or video noise)";
  };

  const tabs = [
    { id: "general" as SettingsTab, label: "General Settings", icon: Settings, desc: "Global model and engine defaults" },
    { id: "priority" as SettingsTab, label: "Fallback Priority", icon: Sparkles, desc: "Drag & rank fallback sequence" },
    { id: "audio" as SettingsTab, label: "Audio & Transcription", icon: AudioLines, desc: "Whisper sizes and chunk intervals" },
    { id: "video" as SettingsTab, label: "Video & Slide Matching", icon: Sliders, desc: "SSIM rates and vision precision" },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-[#121820] border border-gray-800 rounded-2xl w-full max-w-4xl h-[80vh] min-h-[550px] shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2 text-gray-100 font-bold text-lg">
            <Settings className="w-5 h-5 text-blue-400" />
            <span>Application Settings</span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors p-1 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex flex-col justify-center items-center">
            <div className="animate-spin rounded-full h-10 w-10 border-t-2 border-b-2 border-blue-400"></div>
            <span className="ml-3 mt-3 text-gray-400 text-sm">Retrieving config...</span>
          </div>
        ) : (
          <div className="flex-1 flex overflow-hidden">
            {/* Sidebar Navigation */}
            <div className="w-64 bg-gray-900/30 border-r border-gray-800 p-4 flex flex-col justify-between select-none">
              <nav className="space-y-1">
                {tabs.map((tab) => {
                  const Icon = tab.icon;
                  const isActive = activeTab === tab.id;
                  return (
                    <button
                      key={tab.id}
                      onClick={() => {
                        setActiveTab(tab.id);
                        setValidationError(null);
                      }}
                      className={`w-full flex items-start gap-3 p-3 rounded-xl transition-all text-left cursor-pointer border ${
                        isActive
                          ? "bg-blue-600/10 border-blue-500/30 text-blue-400"
                          : "border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-800/40"
                      }`}
                    >
                      <Icon className={`w-5 h-5 mt-0.5 flex-shrink-0 ${isActive ? "text-blue-400" : "text-gray-500"}`} />
                      <div>
                        <p className="text-xs font-bold leading-none">{tab.label}</p>
                        <p className={`text-[10px] mt-1 leading-tight ${isActive ? "text-blue-400/70" : "text-gray-500"}`}>
                          {tab.desc}
                        </p>
                      </div>
                    </button>
                  );
                })}
              </nav>

              {/* Reset Defaults button */}
              <div className="pt-4 border-t border-gray-800/80">
                <button
                  onClick={handleFactoryReset}
                  disabled={resetting || saving}
                  className="w-full flex items-center justify-center gap-2 p-2.5 rounded-xl border border-red-900/30 text-red-400 hover:bg-red-950/20 hover:border-red-800/50 transition-all text-xs font-bold cursor-pointer disabled:opacity-40"
                >
                  <RotateCcw className="w-4 h-4" />
                  {resetting ? "Resetting..." : "Reset defaults"}
                </button>
                {showResetSuccess && (
                  <div className="mt-2 text-[10px] text-green-400 flex items-center justify-center gap-1.5 animate-pulse">
                    <CheckCircle className="w-3.5 h-3.5" />
                    Reset successful!
                  </div>
                )}
              </div>
            </div>

            {/* Content Pane */}
            <div className="flex-1 overflow-y-auto p-6 scrollbar-thin">
              {activeTab === "general" && (
                <div className="space-y-5">
                  <h3 className="text-sm font-bold text-gray-200 mb-2 pb-2 border-b border-gray-800">General Defaults</h3>
                  
                  {/* Default Model */}
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <label className="text-xs font-semibold text-gray-300">Target model</label>
                      <span className="text-[10px] text-gray-500">(default fallback seed)</span>
                    </div>
                    <select
                      value={defaultModel}
                      onChange={(e) => setDefaultModel(e.target.value)}
                      className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-3 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                    >
                      {Object.entries(modelOptions).map(([label, modelId]) => (
                        <option key={modelId || "auto"} value={modelId}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Slide Extraction Engine */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-300">Slide Extraction Engine</label>
                    <select
                      value={pdfEngine}
                      onChange={(e) => setPdfEngine(e.target.value)}
                      className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-3 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                    >
                      <option>Native (PyMuPDF) - Fast</option>
                      <option>AI Vision (Gemini) - High Accuracy</option>
                    </select>
                  </div>

                  {/* Transcription Engine */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-300">Transcription Engine</label>
                    <select
                      value={txEngine}
                      onChange={(e) => setTxEngine(e.target.value)}
                      className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-3 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                    >
                      <option>Local Whisper (CPU) - Private</option>
                      <option>AI Audio (Gemini) - Fast/Cloud</option>
                    </select>
                  </div>

                  {/* Paid tier check */}
                  <div className="pt-2">
                    <label className="flex items-start gap-3 select-none cursor-pointer text-xs text-gray-300 bg-gray-900/40 border border-gray-800/70 p-4 rounded-xl hover:border-gray-700 transition-all">
                      <input
                        type="checkbox"
                        checked={isPaidApi}
                        onChange={(e) => setIsPaidApi(e.target.checked)}
                        className="rounded accent-blue-500 w-4 h-4 mt-0.5 cursor-pointer"
                      />
                      <div>
                        <p className="font-semibold text-gray-200">Paid API Tier Quota Mode</p>
                        <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
                          Disables client-side request pacing (useful if you have billing enabled on Google AI Studio to bypass free tier RPM limits).
                        </p>
                      </div>
                    </label>
                  </div>
                </div>
              )}

              {activeTab === "priority" && (
                <div className="space-y-4">
                  <div className="pb-2 border-b border-gray-800">
                    <h3 className="text-sm font-bold text-gray-200">Fallback Priority Model List</h3>
                    <p className="text-[10px] text-gray-500 mt-1 leading-relaxed">
                      If rate limits (429) or transient server errors (503) occur, the system will fall back to models in the order defined below. Drag and drop items to adjust ranking.
                    </p>
                  </div>

                  {/* Fallback priority drag and drop list */}
                  <div className="space-y-2 mt-3 select-none">
                    {modelPriority.map((modelId, index) => {
                      const label = getModelLabel(modelId);
                      const isDragged = draggedIndex === index;
                      const rpm = rpmLimits[modelId] || 5;
                      
                      // Format model display label clean
                      const cleanLabel = label.split("✦")[0].trim();
                      const suffix = label.includes("✦") ? label.split("✦")[1].trim() : "";

                      return (
                        <div
                          key={modelId}
                          draggable
                          onDragStart={(e) => handleDragStart(e, index)}
                          onDragOver={handleDragOver}
                          onDragEnter={(e) => handleDragEnter(e, index)}
                          onDragEnd={handleDragEnd}
                          className={`flex items-center justify-between p-3 border rounded-xl transition-all duration-150 ${
                            isDragged
                              ? "bg-blue-500/5 border-dashed border-blue-500/40 opacity-55 shadow-[0_0_15px_rgba(59,130,246,0.05)]"
                              : "bg-[#0d1117] border-gray-800/90 hover:border-gray-700"
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            {/* Drag handle */}
                            <div className="cursor-grab active:cursor-grabbing text-gray-600 hover:text-gray-400 p-1 rounded transition-colors">
                              <GripVertical className="w-4 h-4" />
                            </div>
                            
                            {/* Rank badge */}
                            <span className="w-5 h-5 rounded-full bg-gray-900 border border-gray-800 flex items-center justify-center text-[10px] font-bold text-gray-400">
                              {index + 1}
                            </span>

                            {/* Name & tags */}
                            <div>
                              <div className="flex items-center gap-2 flex-wrap">
                                <span className="text-xs font-semibold text-gray-200">{cleanLabel}</span>
                                {suffix && (
                                  <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-blue-500/10 border border-blue-500/20 text-blue-400 scale-95">
                                    {suffix}
                                  </span>
                                )}
                              </div>
                              <span className="text-[9.5px] text-gray-500 font-mono">{modelId}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            {/* Quota indicator */}
                            <span className="text-[10px] font-medium text-gray-400 bg-gray-900/60 border border-gray-800/80 px-2 py-1 rounded-md">
                              {rpm} RPM
                            </span>

                            {/* Control button chevrons */}
                            <div className="flex gap-1">
                              <button
                                onClick={() => moveItem(index, "up")}
                                disabled={index === 0}
                                className="p-1.5 rounded-lg border border-gray-800 bg-[#0d1117] text-gray-400 hover:text-gray-200 hover:border-gray-700 disabled:opacity-30 disabled:hover:border-gray-800 cursor-pointer transition-colors"
                                title="Move Up"
                              >
                                <ArrowUp className="w-3.5 h-3.5" />
                              </button>
                              <button
                                onClick={() => moveItem(index, "down")}
                                disabled={index === modelPriority.length - 1}
                                className="p-1.5 rounded-lg border border-gray-800 bg-[#0d1117] text-gray-400 hover:text-gray-200 hover:border-gray-700 disabled:opacity-30 disabled:hover:border-gray-800 cursor-pointer transition-colors"
                                title="Move Down"
                              >
                                <ArrowDown className="w-3.5 h-3.5" />
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {activeTab === "audio" && (
                <div className="space-y-5">
                  <h3 className="text-sm font-bold text-gray-200 mb-2 pb-2 border-b border-gray-800">Audio Processing & Chunking</h3>

                  <div className="grid grid-cols-2 gap-4">
                    {/* Whisper Size */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Whisper model size</label>
                      <select
                        value={whisperModelSize}
                        onChange={(e) => setWhisperModelSize(e.target.value)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                      >
                        <option value="tiny">Tiny (39M params - Fast)</option>
                        <option value="base">Base (74M params - Balanced)</option>
                        <option value="small">Small (244M params - Accurate)</option>
                        <option value="medium">Medium (769M params - Precise)</option>
                        <option value="large">Large (1550M params - Maximum accuracy)</option>
                      </select>
                    </div>

                    {/* Sample Rate */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Audio sample rate (Hz)</label>
                      <input
                        type="number"
                        value={sampleRate}
                        onChange={(e) => setSampleRate(parseInt(e.target.value) || 0)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* Min Chunk Duration */}
                    <div className="space-y-1.5 col-span-1">
                      <label className="text-xs font-semibold text-gray-300">Min chunk duration (sec)</label>
                      <input
                        type="number"
                        value={minChunkDuration}
                        onChange={(e) => setMinChunkDuration(parseInt(e.target.value) || 0)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* Max Chunk Duration */}
                    <div className="space-y-1.5 col-span-1">
                      <label className="text-xs font-semibold text-gray-300">Max chunk duration (sec)</label>
                      <input
                        type="number"
                        value={maxChunkDuration}
                        onChange={(e) => setMaxChunkDuration(parseInt(e.target.value) || 0)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>
                  </div>

                  {/* Trade-off guide box */}
                  <div className="bg-blue-500/5 border border-blue-500/10 rounded-xl p-4 flex gap-2 text-[10.5px] leading-relaxed text-blue-400/90">
                    <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold">Chunk intervals trade-off:</p>
                      <p className="mt-1">
                        Smaller intervals (e.g. 120s) produce faster alignment processing but may split conceptual topics across slide boundaries. Larger values (e.g. 300s) maintain strong conceptual coherence but require larger LLM context windows.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "video" && (
                <div className="space-y-5">
                  <h3 className="text-sm font-bold text-gray-200 mb-2 pb-2 border-b border-gray-800">Video & Slide Matching</h3>

                  <div className="grid grid-cols-2 gap-4">
                    {/* PDF render zoom */}
                    <div className="space-y-1.5">
                      <div className="flex justify-between items-center">
                        <label className="text-xs font-semibold text-gray-300">PDF slide render zoom</label>
                        <span className="text-[9px] text-gray-500 font-mono">{renderZoom.toFixed(1)}x</span>
                      </div>
                      <input
                        type="number"
                        step="0.1"
                        min="1.0"
                        max="4.0"
                        value={renderZoom}
                        onChange={(e) => setRenderZoom(parseFloat(e.target.value) || 1.0)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* Video Strategy */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Video Matching Strategy</label>
                      <select
                        value={matchingStrategy}
                        onChange={(e) => setMatchingStrategy(e.target.value)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                      >
                        <option value="cv">CV Hash (Fast local check)</option>
                        <option value="ai">AI Vision (Gemini high accuracy)</option>
                        <option value="hybrid">Hybrid (Local CV + AI Verification)</option>
                      </select>
                    </div>

                    {/* Video sample rate */}
                    <div className="space-y-1.5 col-span-2">
                      <label className="text-xs font-semibold text-gray-300">Frame Sample Rate (Frames per Second)</label>
                      <input
                        type="number"
                        value={frameSampleRate}
                        onChange={(e) => setFrameSampleRate(parseInt(e.target.value) || 1)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* SSIM Threshold */}
                    <div className="space-y-1.5 col-span-2 pt-2">
                      <div className="flex justify-between items-center">
                        <label className="text-xs font-semibold text-gray-300">SSIM Slide Cut Threshold</label>
                        <span className="text-xs font-bold text-blue-400 font-mono">{ssimThreshold.toFixed(2)}</span>
                      </div>
                      <input
                        type="range"
                        min="0.50"
                        max="0.99"
                        step="0.01"
                        value={ssimThreshold}
                        onChange={(e) => setSsimThreshold(parseFloat(e.target.value))}
                        className="w-full accent-blue-500 py-1.5 cursor-pointer"
                      />
                      <p className="text-[10px] text-gray-400 italic">
                        Sensitivity: {getSsimDescription(ssimThreshold)}
                      </p>
                    </div>
                  </div>

                  {/* Render zoom warning tooltip */}
                  <div className="bg-yellow-500/5 border border-yellow-500/10 rounded-xl p-4 flex gap-2 text-[10.5px] leading-relaxed text-yellow-500/90">
                    <AlertTriangle className="w-4 h-4 flex-shrink-0 mt-0.5 text-yellow-500" />
                    <div>
                      <p className="font-bold">Render zoom advice:</p>
                      <p className="mt-1">
                        Higher zoom settings (e.g. 2.0 or 3.0) produce high-resolution crisp images which improve AI optical character recognition (OCR) on slides, but will require significantly more storage space and slide generation time.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Footer Actions */}
        <div className="p-4 border-t border-gray-800 bg-gray-900/20 flex flex-row items-center justify-between select-none">
          {/* Validation warning */}
          <div className="flex-1 max-w-[50%]">
            {validationError && (
              <div className="text-red-400 text-xs font-bold flex items-center gap-1.5 animate-pulse">
                <AlertTriangle className="w-4 h-4 flex-shrink-0 text-red-400" />
                <span>{validationError}</span>
              </div>
            )}
          </div>

          <div className="flex gap-3">
            <button
              onClick={onClose}
              disabled={saving || resetting}
              className="px-4 py-2.5 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-xl text-xs font-bold cursor-pointer transition-all disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving || resetting}
              className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold cursor-pointer transition-all flex items-center gap-1.5 shadow-lg shadow-blue-600/10 disabled:opacity-40"
            >
              <Save className="w-4 h-4" />
              {saving ? "Saving..." : "Save & Close"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
