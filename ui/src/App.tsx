import { BrowserRouter, Routes, Route, Navigate, Link } from 'react-router-dom';
import { UploadPage } from './pages/UploadPage';
import { ProgressPage } from './pages/ProgressPage';
import { ResultPage } from './pages/ResultPage';
import { EvidencePage } from './pages/EvidencePage';
import { AnalysesPage } from './pages/AnalysesPage';

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-slate-100 bg-[radial-gradient(circle_at_top,_rgba(34,197,94,0.18),_transparent_55%),radial-gradient(circle_at_bottom,_rgba(8,47,73,0.9),_rgba(2,6,23,1))] flex flex-col">
        <header className="bg-slate-950/80 border-b border-slate-800 backdrop-blur">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <Link to="/" className="flex items-center">
                <img src="/logo.png" alt="BioVerify" className="h-15 object-contain" />
              </Link>
              <nav className="flex items-center gap-3">
                <Link
                  to="/analyses"
                  className="px-3 py-1.5 rounded-full text-xs font-medium border border-slate-600 text-slate-300 hover:bg-slate-800 hover:border-slate-500 transition-colors"
                >
                  Previous Analyses
                </Link>
                <Link
                  to="/upload"
                  className="px-3 py-1.5 rounded-full text-xs font-medium border border-emerald-400/60 text-emerald-300 hover:bg-emerald-400/10 hover:border-emerald-300 transition-colors"
                >
                  New Analysis
                </Link>
              </nav>
            </div>
          </div>
        </header>

        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Navigate to="/upload" replace />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/analyses" element={<AnalysesPage />} />
            <Route path="/analysis/:id" element={<ProgressPage />} />
            <Route path="/analysis/:id/result" element={<ResultPage />} />
            <Route path="/analysis/:id/evidence" element={<EvidencePage />} />
          </Routes>
        </main>

        <footer className="bg-slate-950/80 border-t border-slate-800 mt-8">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <p className="text-center text-[11px] tracking-[0.18em] uppercase text-slate-500">
              BioVerify · Invariant Deepfake Detection via rPPG
            </p>
          </div>
        </footer>
      </div>
    </BrowserRouter>
  );
}

export default App;
