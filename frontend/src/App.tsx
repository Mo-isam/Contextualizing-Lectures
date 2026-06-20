import React, { useState } from "react";
import { HomeView } from "./views/HomeView";
import { LibraryView } from "./views/LibraryView";
import { UploadView } from "./views/UploadView";
import { ProcessingView } from "./views/ProcessingView";
import { StudioView } from "./views/StudioView";
import type { LectureSession } from "./types";
import { GraduationCap } from "lucide-react";
import { ApiService } from "./services/api";

type AppStep = "home" | "library" | "upload" | "processing" | "studio";

export const App: React.FC = () => {
  const [step, setStep] = useState<AppStep>("home");
  const [pipelineConfig, setPipelineConfig] = useState<any>(null);
  const [activeSession, setActiveSession] = useState<(LectureSession & { slide_images: string[] }) | null>(null);
  const [sessionLoading, setSessionLoading] = useState<boolean>(false);

  // CTA triggers
  const handleNewSession = () => {
    setActiveSession(null);
    setPipelineConfig(null);
    setStep("upload");
  };

  const handleLoadSession = async (filename: string) => {
    setSessionLoading(true);
    try {
      const data = await ApiService.getSession(filename);
      setActiveSession(data);
      setStep("studio");
    } catch (err: any) {
      alert(`Load session error: ${err.message}`);
    } finally {
      setSessionLoading(false);
    }
  };

  const handleStartProcessing = (config: any) => {
    setPipelineConfig(config);
    setStep("processing");
  };

  const handleProcessingComplete = (data: any) => {
    // Scaffold a default lecture name based on file names
    const pdfName = pipelineConfig.pdf_path.split("/").pop() || "Slides";
    const cleanPdfName = pdfName.replace(/\.[^/.]+$/, "");
    
    const sessionData: LectureSession & { slide_images: string[] } = {
      session_name: `Aligned Session - ${cleanPdfName}`,
      session_description: `Processed alignment session using ${pipelineConfig.pipeline_mode} pipeline`,
      pdf_path: pipelineConfig.pdf_path,
      media_path: pipelineConfig.media_path,
      transcript_segments: data.transcript_segments,
      slides: data.slides,
      final_output: data.final_output,
      slide_images: data.slide_images,
      pipeline_type: pipelineConfig.pipeline_mode,
      peaks: data.peaks,
    };
    
    setActiveSession(sessionData);
    setStep("studio");
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#0d1117] via-[#0f1922] to-[#0d1117] text-gray-200">
      {/* SPA Navigation Header bar */}
      <header className="border-b border-gray-800/80 bg-[#0d1117]/80 backdrop-blur-md sticky top-0 z-40 select-none">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div
            onClick={() => setStep("home")}
            className="flex items-center gap-2.5 cursor-pointer group"
          >
            <div className="w-9 h-9 rounded-lg bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 group-hover:bg-blue-500/20 group-hover:border-blue-500/40 transition-all">
              <GraduationCap className="w-5 h-5" />
            </div>
            <span className="font-extrabold text-base tracking-tight bg-gradient-to-r from-gray-100 via-gray-100 to-gray-300 bg-clip-text text-transparent group-hover:text-blue-400 transition-colors">
              Lecture AI Studio
            </span>
          </div>

          <div className="flex items-center gap-4 text-xs font-semibold text-gray-500">
            {step === "home" && <span className="text-blue-400 uppercase tracking-wider bg-blue-500/5 px-3 py-1.5 rounded-lg border border-blue-500/10">Home</span>}
            {step === "library" && <span className="text-purple-400 uppercase tracking-wider bg-purple-500/5 px-3 py-1.5 rounded-lg border border-purple-500/10">Library</span>}
            {step === "upload" && <span className="text-blue-400 uppercase tracking-wider bg-blue-500/5 px-3 py-1.5 rounded-lg border border-blue-500/10">Upload</span>}
            {step === "processing" && <span className="text-purple-400 uppercase tracking-wider bg-purple-500/5 px-3 py-1.5 rounded-lg border border-purple-500/10 animate-pulse">Analyzing</span>}
            {step === "studio" && <span className="text-emerald-400 uppercase tracking-wider bg-emerald-500/5 px-3 py-1.5 rounded-lg border border-emerald-500/10">Studio Workspace</span>}
          </div>
        </div>
      </header>

      {/* Main content body */}
      <main className="min-h-[calc(100vh-4rem)]">
        {sessionLoading && (
          <div className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center">
            <div className="bg-[#121820] border border-gray-800 rounded-xl p-6 flex items-center gap-3 shadow-2xl">
              <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-400"></div>
              <span className="text-sm font-semibold text-gray-300">⏳ Loading session from Library...</span>
            </div>
          </div>
        )}

        {step === "home" && (
          <HomeView
            onNewSession={handleNewSession}
            onOpenLibrary={() => setStep("library")}
          />
        )}

        {step === "library" && (
          <LibraryView
            onBack={() => setStep("home")}
            onLoadSession={handleLoadSession}
          />
        )}

        {step === "upload" && (
          <UploadView
            onBack={() => setStep("home")}
            onStartProcessing={handleStartProcessing}
          />
        )}

        {step === "processing" && (
          <ProcessingView
            config={pipelineConfig}
            onComplete={handleProcessingComplete}
            onCancel={() => setStep("upload")}
          />
        )}

        {step === "studio" && activeSession && (
          <StudioView
            session={activeSession}
            onBack={() => setStep("home")}
            onSaveCompleted={() => {}}
          />
        )}
      </main>
    </div>
  );
};

export default App;
