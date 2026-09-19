import React, { useState } from 'react';
import {
  UploadCloud,
  FileAudio,
  Play,
  Pause,
  AlertTriangle,
  ShieldCheck,
  ShieldAlert,
  Loader2,
  Sparkles,
  RefreshCw,
} from 'lucide-react';
import { RiskGauge } from './RiskGauge';

interface AnalyzeResponse {
  status: string;
  risk_score: number;
  classification: string;
  telemetry: {
    spoof_probability: number;
    speaker_similarity: number;
  };
  message: string;
}

export const FileUploadAnalyzer: React.FC = () => {
  const [refFile, setRefFile] = useState<File | null>(null);
  const [testFile, setTestFile] = useState<File | null>(null);
  const [refPreviewUrl, setRefPreviewUrl] = useState<string | null>(null);
  const [testPreviewUrl, setTestPreviewUrl] = useState<string | null>(null);
  const [isPlayingRef, setIsPlayingRef] = useState(false);
  const [isPlayingTest, setIsPlayingTest] = useState(false);
  const [audioElemRef, setAudioElemRef] = useState<HTMLAudioElement | null>(null);
  const [audioElemTest, setAudioElemTest] = useState<HTMLAudioElement | null>(null);

  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleRefUpload = (file: File) => {
    setRefFile(file);
    const url = URL.createObjectURL(file);
    setRefPreviewUrl(url);
  };

  const handleTestUpload = (file: File) => {
    setTestFile(file);
    const url = URL.createObjectURL(file);
    setTestPreviewUrl(url);
  };

  // Helper to load sample files bundled in /samples/
  const loadPresetSample = async (sampleType: 'genuine' | 'clone' | 'wrong') => {
    setError(null);
    try {
      // 1. Always load genuine reference
      const refRes = await fetch('/samples/genuine_reference.wav');
      const refBlob = await refRes.blob();
      const refSampleFile = new File([refBlob], 'genuine_reference.wav', { type: 'audio/wav' });
      handleRefUpload(refSampleFile);

      // 2. Load chosen test file
      let testFileName = 'genuine_test.wav';
      if (sampleType === 'clone') testFileName = 'voice_clone_test.wav';
      if (sampleType === 'wrong') testFileName = 'wrong_speaker_test.wav';

      const testRes = await fetch(`/samples/${testFileName}`);
      const testBlob = await testRes.blob();
      const testSampleFile = new File([testBlob], testFileName, { type: 'audio/wav' });
      handleTestUpload(testSampleFile);
    } catch (err) {
      setError(`Failed to load preset sample files: ${err}`);
    }
  };

  const handleSubmitAnalysis = async () => {
    if (!refFile || !testFile) {
      setError('Please provide both Reference Audio and Test Audio files.');
      return;
    }

    setError(null);
    setIsLoading(true);

    const formData = new FormData();
    formData.append('reference_audio', refFile);
    formData.append('test_audio', testFile);

    try {
      const response = await fetch('http://localhost:8000/api/v1/analyze-file', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({ detail: 'Analysis failed' }));
        throw new Error(errData.detail || `Server error: ${response.status}`);
      }

      const data: AnalyzeResponse = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis request failed.');
    } finally {
      setIsLoading(false);
    }
  };

  const togglePlay = (type: 'ref' | 'test') => {
    if (type === 'ref') {
      if (!audioElemRef && refPreviewUrl) {
        const a = new Audio(refPreviewUrl);
        a.onended = () => setIsPlayingRef(false);
        a.play();
        setAudioElemRef(a);
        setIsPlayingRef(true);
      } else if (audioElemRef) {
        if (isPlayingRef) {
          audioElemRef.pause();
          setIsPlayingRef(false);
        } else {
          audioElemRef.play();
          setIsPlayingRef(true);
        }
      }
    } else {
      if (!audioElemTest && testPreviewUrl) {
        const a = new Audio(testPreviewUrl);
        a.onended = () => setIsPlayingTest(false);
        a.play();
        setAudioElemTest(a);
        setIsPlayingTest(true);
      } else if (audioElemTest) {
        if (isPlayingTest) {
          audioElemTest.pause();
          setIsPlayingTest(false);
        } else {
          audioElemTest.play();
          setIsPlayingTest(true);
        }
      }
    }
  };

  return (
    <div className="glass-panel p-5 rounded-2xl border-slate-800/80 space-y-5">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between border-b border-slate-800 pb-3 gap-3">
        <div>
          <div className="flex items-center space-x-2">
            <UploadCloud className="w-5 h-5 text-cyan-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              Static Audio Risk Analysis (REST API)
            </h3>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Upload genuine reference & suspect call audio to generate AASIST + ECAPA 0–100 risk scores.
          </p>
        </div>

        {/* Preset Sample Quick-Loaders */}
        <div className="flex items-center space-x-1.5 bg-slate-900/90 border border-slate-800 p-1 rounded-xl">
          <span className="text-[11px] font-semibold text-slate-400 px-2 flex items-center space-x-1">
            <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
            <span>Load Samples:</span>
          </span>
          <button
            onClick={() => loadPresetSample('genuine')}
            className="px-2 py-1 text-[11px] font-medium bg-emerald-950/60 hover:bg-emerald-900 text-emerald-300 border border-emerald-500/30 rounded-lg transition"
          >
            Genuine Pair
          </button>
          <button
            onClick={() => loadPresetSample('clone')}
            className="px-2 py-1 text-[11px] font-medium bg-red-950/60 hover:bg-red-900 text-red-300 border border-red-500/30 rounded-lg transition"
          >
            Voice Clone
          </button>
          <button
            onClick={() => loadPresetSample('wrong')}
            className="px-2 py-1 text-[11px] font-medium bg-amber-950/60 hover:bg-amber-900 text-amber-300 border border-amber-500/30 rounded-lg transition"
          >
            Wrong Speaker
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-red-950/60 border border-red-500/40 rounded-xl text-xs text-red-300 flex items-center space-x-2">
          <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Upload Dropzones */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Reference Audio Box */}
        <div className="bg-[#070b14]/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-purple-500/40 transition">
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-bold text-purple-400 flex items-center space-x-1.5">
                <FileAudio className="w-4 h-4" />
                <span>1. Reference Audio (Genuine Voiceprint)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-500">ECAPA-TDNN</span>
            </div>
            <p className="text-[11px] text-slate-400 mb-3">
              Trusted audio file used to extract the 192-dimensional baseline speaker embedding.
            </p>

            <label className="border-2 border-dashed border-slate-800 hover:border-purple-500/60 rounded-xl p-4 flex flex-col items-center justify-center cursor-pointer transition bg-slate-900/30">
              <UploadCloud className="w-6 h-6 text-purple-400 mb-1" />
              <span className="text-xs font-semibold text-slate-300 truncate max-w-[200px]">
                {refFile ? refFile.name : 'Choose or drop WAV / FLAC'}
              </span>
              <span className="text-[10px] text-slate-500 mt-0.5">Auto-resampled to 16 kHz</span>
              <input
                type="file"
                accept="audio/*,.wav,.flac,.ogg,.mp3"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleRefUpload(e.target.files[0])}
              />
            </label>
          </div>

          {refPreviewUrl && (
            <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <button
                onClick={() => togglePlay('ref')}
                className="flex items-center space-x-1.5 text-xs font-semibold text-purple-300 hover:text-purple-200"
              >
                {isPlayingRef ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{isPlayingRef ? 'Pause' : 'Play Reference'}</span>
              </button>
              <span className="text-[10px] font-mono text-slate-500">Ready</span>
            </div>
          )}
        </div>

        {/* 2. Test Audio Box */}
        <div className="bg-[#070b14]/90 border border-slate-800 rounded-xl p-4 flex flex-col justify-between hover:border-cyan-500/40 transition">
          <div>
            <div className="flex items-center justify-between text-xs mb-2">
              <span className="font-bold text-cyan-400 flex items-center space-x-1.5">
                <FileAudio className="w-4 h-4" />
                <span>2. Test Audio (Suspect Audio Clip)</span>
              </span>
              <span className="text-[10px] font-mono text-slate-500">AASIST 64.6k</span>
            </div>
            <p className="text-[11px] text-slate-400 mb-3">
              Suspicious incoming audio to be tested for AI generation and identity impersonation.
            </p>

            <label className="border-2 border-dashed border-slate-800 hover:border-cyan-500/60 rounded-xl p-4 flex flex-col items-center justify-center cursor-pointer transition bg-slate-900/30">
              <UploadCloud className="w-6 h-6 text-cyan-400 mb-1" />
              <span className="text-xs font-semibold text-slate-300 truncate max-w-[200px]">
                {testFile ? testFile.name : 'Choose or drop suspect audio'}
              </span>
              <span className="text-[10px] text-slate-500 mt-0.5">300ms VAD & 64.6k ASVspoof Pad</span>
              <input
                type="file"
                accept="audio/*,.wav,.flac,.ogg,.mp3"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && handleTestUpload(e.target.files[0])}
              />
            </label>
          </div>

          {testPreviewUrl && (
            <div className="mt-3 pt-3 border-t border-slate-800/80 flex items-center justify-between">
              <button
                onClick={() => togglePlay('test')}
                className="flex items-center space-x-1.5 text-xs font-semibold text-cyan-300 hover:text-cyan-200"
              >
                {isPlayingTest ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
                <span>{isPlayingTest ? 'Pause' : 'Play Test Clip'}</span>
              </button>
              <span className="text-[10px] font-mono text-slate-500">Ready</span>
            </div>
          )}
        </div>
      </div>

      {/* Action Button */}
      <div className="flex justify-end">
        <button
          onClick={handleSubmitAnalysis}
          disabled={isLoading || !refFile || !testFile}
          className="px-6 py-2.5 bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-bold text-xs rounded-xl flex items-center space-x-2 shadow-lg shadow-cyan-900/30 transition"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing Audio via AASIST & ECAPA...</span>
            </>
          ) : (
            <>
              <RefreshCw className="w-4 h-4" />
              <span>Analyze Audio Files</span>
            </>
          )}
        </button>
      </div>

      {/* Analysis Results Display */}
      {result && (
        <div className="bg-[#070b14]/90 border border-slate-800 p-5 rounded-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <span className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Inference Analysis Result
            </span>
            <span className="text-[11px] font-mono text-cyan-400">
              POST /api/v1/analyze-file (200 OK)
            </span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 items-center">
            {/* Visual Dial */}
            <div className="md:col-span-5 flex justify-center">
              <RiskGauge
                score={result.risk_score}
                classification={
                  result.risk_score >= 70
                    ? 'HIGH_RISK'
                    : result.risk_score >= 31
                    ? 'MEDIUM_RISK'
                    : 'LOW_RISK'
                }
              />
            </div>

            {/* Metrics Breakdown */}
            <div className="md:col-span-7 space-y-3">
              <div
                className={`p-3 rounded-xl border flex items-start space-x-3 ${
                  result.classification === 'HIGH_RISK_CLONE' || result.classification.includes('HIGH')
                    ? 'bg-red-950/60 border-red-500/40 text-red-200'
                    : result.classification === 'BONA_FIDE_GENUINE'
                    ? 'bg-emerald-950/60 border-emerald-500/40 text-emerald-200'
                    : 'bg-amber-950/60 border-amber-500/40 text-amber-200'
                }`}
              >
                {result.classification === 'HIGH_RISK_CLONE' ? (
                  <ShieldAlert className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                ) : result.classification === 'BONA_FIDE_GENUINE' ? (
                  <ShieldCheck className="w-5 h-5 text-emerald-400 flex-shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
                )}
                <div>
                  <div className="text-xs font-extrabold uppercase tracking-wide">
                    Classification: {result.classification}
                  </div>
                  <div className="text-xs mt-0.5">{result.message}</div>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="bg-slate-900/80 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">
                    AASIST Spoof Prob
                  </span>
                  <div className="text-xl font-bold font-mono text-cyan-400 mt-1">
                    {(result.telemetry.spoof_probability * 100).toFixed(1)}%
                  </div>
                </div>

                <div className="bg-slate-900/80 border border-slate-800 p-3 rounded-xl">
                  <span className="text-[10px] font-bold text-slate-400 uppercase">
                    ECAPA Cosine Similarity
                  </span>
                  <div className="text-xl font-bold font-mono text-purple-400 mt-1">
                    {result.telemetry.speaker_similarity.toFixed(4)}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
