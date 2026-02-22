import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { VideoUpload } from '../components/VideoUpload';
import { api } from '../services/api';

export function UploadPage() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [policyName, setPolicyName] = useState<string>('');
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setError(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setError('Please select a video file');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const response = await api.uploadVideo(selectedFile, policyName || undefined);
      navigate(`/analysis/${response.analysis_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to upload video');
      setIsUploading(false);
    }
  };

  return (
    <div className="py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-3xl mx-auto">
        <div className="text-center mb-10">
          <p className="text-xs font-semibold tracking-[0.25em] text-emerald-400/80 uppercase mb-3">
            Invariant Deepfake Detection
          </p>
          <h1 className="text-4xl md:text-5xl font-semibold text-slate-50 mb-3 tracking-tight">
            Analyze a video for{" "}
            <span className="text-emerald-400 drop-shadow-[0_0_18px_rgba(16,185,129,0.7)]">
              biological liveness
            </span>
          </h1>
          <p className="text-sm md:text-base text-slate-400 max-w-2xl mx-auto">
            BioVerify uses remote photoplethysmography (rPPG) to detect human pulse signals in
            facial skin, moving beyond pixel artifacts to physiological invariants.
          </p>
        </div>

        <div className="bg-slate-950/70 border border-slate-800 rounded-2xl shadow-[0_0_40px_rgba(15,23,42,0.9)] backdrop-blur-md p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-xs font-semibold tracking-wide text-slate-300 mb-2 uppercase">
                Video File
              </label>
              <VideoUpload onFileSelect={handleFileSelect} />
              {selectedFile && (
                <div className="mt-4 p-3 bg-slate-900/80 rounded-lg border border-slate-800">
                  <p className="text-sm text-slate-200">
                    <span className="font-medium">Selected:</span> {selectedFile.name}
                  </p>
                  <p className="text-xs text-slate-500">
                    Size: {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>
              )}
            </div>

            <div>
              <label
                htmlFor="policy"
                className="block text-xs font-semibold tracking-wide text-slate-300 mb-2 uppercase"
              >
                Policy (Optional)
              </label>
              <select
                id="policy"
                value={policyName}
                onChange={(e) => setPolicyName(e.target.value)}
                className="w-full px-3 py-2 rounded-lg bg-slate-900/80 border border-slate-700 text-slate-100 focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500"
              >
                <option value="">Default Policy</option>
                <option value="strict">Strict</option>
                <option value="balanced">Balanced</option>
                <option value="permissive">Permissive</option>
              </select>
            </div>

            {error && (
              <div className="bg-red-950/60 border border-red-500/60 rounded-lg p-4">
                <p className="text-sm text-red-100">{error}</p>
              </div>
            )}

            <button
              type="submit"
              disabled={!selectedFile || isUploading}
              className="w-full bg-emerald-500 text-slate-950 py-3 px-4 rounded-lg font-semibold hover:bg-emerald-400 disabled:bg-slate-700 disabled:text-slate-400 disabled:cursor-not-allowed transition-colors shadow-[0_0_25px_rgba(34,197,94,0.7)]"
            >
              {isUploading ? (
                <span className="flex items-center justify-center gap-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-slate-950"></div>
                  Uploading...
                </span>
              ) : (
                'Start Analysis'
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
