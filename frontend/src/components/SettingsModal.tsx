import React, { useEffect, useState } from "react";
import { Settings, Save, X, Info } from "lucide-react";

interface SettingsModalProps {
  onClose: () => void;
  onSave: () => void;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ onClose, onSave }) => {
  const [activeTab, setActiveTab] = useState<"general" | "advanced">("general");
  const [loading, setLoading] = useState<boolean>(true);
  const [saving, setSaving] = useState<boolean>(false);

  // General settings state
  const [isPaidApi, setIsPaidApi] = useState<boolean>(false);
  const [defaultModel, setDefaultModel] = useState<string>("gemini-3.5-flash");
  const [pdfEngine, setPdfEngine] = useState<string>("Native (PyMuPDF) - Fast");
  const [txEngine, setTxEngine] = useState<string>("Local Whisper (CPU) - Private");
  const [modelOptions, setModelOptions] = useState<Record<string, string>>({});

  // Advanced settings state
  const [whisperModelSize, setWhisperModelSize] = useState<string>("base");
  const [sampleRate, setSampleRate] = useState<number>(16000);
  const [minChunkDuration, setMinChunkDuration] = useState<number>(180);
  const [maxChunkDuration, setMaxChunkDuration] = useState<number>(300);
  const [renderZoom, setRenderZoom] = useState<number>(2.0);
  const [matchingStrategy, setMatchingStrategy] = useState<string>("hybrid");
  const [frameSampleRate, setFrameSampleRate] = useState<number>(1);
  const [ssimThreshold, setSsimThreshold] = useState<number>(0.85);

  useEffect(() => {
    fetch("/api/config")
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch settings.");
        return res.json();
      })
      .then((data) => {
        setIsPaidApi(data.ui_defaults.is_paid_api);
        setDefaultModel(data.ui_defaults.default_model);
        setPdfEngine(data.ui_defaults.pdf_engine);
        setTxEngine(data.ui_defaults.tx_engine);
        setModelOptions(data.model_options || {});

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
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
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
        }),
      });

      if (!res.ok) throw new Error("Failed to save settings.");
      onSave();
      onClose();
    } catch (err: any) {
      alert(`Save settings error: ${err.message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4 animate-fade-in">
      <div className="bg-[#121820] border border-gray-800 rounded-2xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-gray-800">
          <div className="flex items-center gap-2 text-gray-100 font-bold text-lg">
            <Settings className="w-5 h-5 text-blue-400" />
            <span>Pipeline Settings</span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300 transition-colors p-1 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {loading ? (
          <div className="flex-1 flex justify-center items-center py-24">
            <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-400"></div>
            <span className="ml-3 text-gray-400 text-sm">Loading config...</span>
          </div>
        ) : (
          <>
            {/* Tabs */}
            <div className="flex border-b border-gray-800 bg-gray-900/30">
              <button
                onClick={() => setActiveTab("general")}
                className={`flex-1 py-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 cursor-pointer ${
                  activeTab === "general"
                    ? "border-blue-500 text-blue-400 bg-blue-500/5"
                    : "border-transparent text-gray-400 hover:text-gray-300 hover:bg-gray-800/20"
                }`}
              >
                General Settings
              </button>
              <button
                onClick={() => setActiveTab("advanced")}
                className={`flex-1 py-3 text-xs font-bold uppercase tracking-wider transition-all border-b-2 cursor-pointer ${
                  activeTab === "advanced"
                    ? "border-blue-500 text-blue-400 bg-blue-500/5"
                    : "border-transparent text-gray-400 hover:text-gray-300 hover:bg-gray-800/20"
                }`}
              >
                Advanced Settings
              </button>
            </div>

            {/* Scrollable Form Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {activeTab === "general" ? (
                <div className="space-y-4">
                  {/* Model */}
                  <div className="space-y-1.5">
                    <label className="text-xs font-semibold text-gray-300">Target Model ID</label>
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
                    <label className="flex items-center gap-3 select-none cursor-pointer text-xs text-gray-300 bg-gray-900/40 border border-gray-800 p-4 rounded-xl hover:border-gray-700 transition-all">
                      <input
                        type="checkbox"
                        checked={isPaidApi}
                        onChange={(e) => setIsPaidApi(e.target.checked)}
                        className="rounded accent-blue-500 w-4 h-4"
                      />
                      <div>
                        <p className="font-semibold text-gray-200">Paid API Tier Quota</p>
                        <p className="text-[10px] text-gray-500 mt-0.5">Disable rate pacing (useful if you have billing enabled on Google AI Studio).</p>
                      </div>
                    </label>
                  </div>
                </div>
              ) : (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    {/* Whisper Size */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Whisper Model Size</label>
                      <select
                        value={whisperModelSize}
                        onChange={(e) => setWhisperModelSize(e.target.value)}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all cursor-pointer"
                      >
                        <option value="tiny">Tiny</option>
                        <option value="base">Base</option>
                        <option value="small">Small</option>
                        <option value="medium">Medium</option>
                        <option value="large">Large</option>
                      </select>
                    </div>

                    {/* Sample Rate */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Audio Sample Rate (Hz)</label>
                      <input
                        type="number"
                        value={sampleRate}
                        onChange={(e) => setSampleRate(parseInt(e.target.value))}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* Min Chunk Duration */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Min Chunk (sec)</label>
                      <input
                        type="number"
                        value={minChunkDuration}
                        onChange={(e) => setMinChunkDuration(parseInt(e.target.value))}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* Max Chunk Duration */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Max Chunk (sec)</label>
                      <input
                        type="number"
                        value={maxChunkDuration}
                        onChange={(e) => setMaxChunkDuration(parseInt(e.target.value))}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* PDF render zoom */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Render Zoom</label>
                      <input
                        type="number"
                        step="0.1"
                        value={renderZoom}
                        onChange={(e) => setRenderZoom(parseFloat(e.target.value))}
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
                        <option value="cv">CV Hash</option>
                        <option value="ai">AI Vision</option>
                        <option value="hybrid">Hybrid</option>
                      </select>
                    </div>

                    {/* Video sample rate */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">Frame Sample Rate</label>
                      <input
                        type="number"
                        value={frameSampleRate}
                        onChange={(e) => setFrameSampleRate(parseInt(e.target.value))}
                        className="w-full bg-[#0d1117] border border-gray-800 focus:border-blue-500 rounded-xl p-2.5 text-xs text-gray-200 outline-none transition-all"
                      />
                    </div>

                    {/* SSIM Threshold */}
                    <div className="space-y-1.5">
                      <label className="text-xs font-semibold text-gray-300">SSIM Threshold ({ssimThreshold})</label>
                      <input
                        type="range"
                        min="0.0"
                        max="1.0"
                        step="0.01"
                        value={ssimThreshold}
                        onChange={(e) => setSsimThreshold(parseFloat(e.target.value))}
                        className="w-full accent-blue-500 py-1"
                      />
                    </div>
                  </div>

                  <div className="bg-blue-500/5 border border-blue-500/10 rounded-xl p-4 flex gap-2 text-[10px] leading-relaxed text-blue-400">
                    <Info className="w-4 h-4 flex-shrink-0 mt-0.5" />
                    <span>Advanced adjustments affect compute processing loads and alignment precision. Leave as default unless required.</span>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="p-5 border-t border-gray-800 bg-gray-900/20 flex gap-3 justify-end">
              <button
                onClick={onClose}
                disabled={saving}
                className="px-4 py-2.5 border border-gray-800 hover:bg-gray-800 text-gray-300 rounded-xl text-xs font-bold cursor-pointer transition-all disabled:opacity-40"
              >
                Cancel
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="px-4 py-2.5 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold cursor-pointer transition-all flex items-center gap-1.5 shadow-lg shadow-blue-600/10 disabled:opacity-40"
              >
                <Save className="w-4 h-4" />
                {saving ? "Saving..." : "Save & Close"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
