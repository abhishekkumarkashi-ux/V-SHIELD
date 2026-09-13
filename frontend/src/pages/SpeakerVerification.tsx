import { useState } from 'react';
import { UserCheck, UploadCloud, CheckCircle2, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

const SpeakerVerification = () => {
  const [file, setFile] = useState<File | null>(null);
  const [enrolling, setEnrolling] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const handleEnroll = async () => {
    if (!file) return;
    setEnrolling(true);
    setError(null);
    setResult(null);

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await api.post('/enroll', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      // In a real app we'd update the user state or db.
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to enroll speaker');
    } finally {
      setEnrolling(false);
    }
  };

  return (
    <div className="max-w-4xl space-y-6">
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* CURRENT IDENTITY */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 bg-emerald-500/10 rounded-lg">
              <UserCheck className="w-6 h-6 text-emerald-400" />
            </div>
            <h3 className="text-xl font-semibold text-slate-200">Current Identity</h3>
          </div>
          
          <div className="flex flex-col items-center justify-center py-8">
            <div className="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mb-4 border-2 border-slate-700">
              <UserCheck className="w-8 h-8 text-slate-500" />
            </div>
            
            {result ? (
              <div className="text-center">
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-sm font-medium mb-2">
                  <CheckCircle2 className="w-4 h-4" /> Enrolled
                </span>
                <p className="text-slate-400 text-sm break-all">ID: {result.speaker_id}</p>
              </div>
            ) : (
              <div className="text-center">
                <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-slate-800 border border-slate-700 text-slate-400 text-sm font-medium mb-2">
                  Not Enrolled
                </span>
                <p className="text-slate-500 text-sm max-w-[200px]">Enroll a voice sample to enable speaker verification in Live Analysis.</p>
              </div>
            )}
          </div>
        </div>

        {/* ENROLLMENT */}
        <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl">
          <h3 className="text-lg font-medium text-slate-200 mb-6">Enroll New Speaker</h3>
          
          <div className="space-y-4">
            <div className="border-2 border-dashed border-slate-700 rounded-xl p-8 text-center hover:bg-slate-800/50 transition-colors cursor-pointer relative">
              <input 
                type="file" 
                accept="audio/*" 
                onChange={e => setFile(e.target.files?.[0] || null)}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={enrolling}
              />
              <UploadCloud className="w-10 h-10 text-blue-500 mx-auto mb-3" />
              <p className="text-slate-300 font-medium">Click to select audio file</p>
              <p className="text-slate-500 text-sm mt-1">WAV, FLAC, MP3, M4A up to 10MB</p>
              {file && (
                <div className="mt-4 inline-flex items-center gap-2 text-sm text-blue-400 bg-blue-500/10 px-3 py-1.5 rounded-lg border border-blue-500/20">
                  <CheckCircle2 className="w-4 h-4" /> {file.name}
                </div>
              )}
            </div>

            {error && (
              <div className="flex items-start gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
                <AlertCircle className="w-5 h-5 shrink-0" />
                <p>{error}</p>
              </div>
            )}

            <button
              onClick={handleEnroll}
              disabled={!file || enrolling}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 disabled:text-slate-500 text-white font-medium py-3 rounded-xl transition-colors shadow-lg shadow-blue-500/20 disabled:shadow-none flex justify-center items-center h-[52px]"
            >
              {enrolling ? 'Processing Voice Sample...' : 'Enroll Voice Pattern'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SpeakerVerification;
