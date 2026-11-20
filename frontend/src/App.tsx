import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ToastProvider } from './components/ui/Toast';
import { AppShell } from './components/layout/AppShell';
import { JobDescriptionPage } from './pages/JobDescriptionPage';
import { ResumesPage } from './pages/ResumesPage';
import { ResultsDashboardPage } from './pages/ResultsDashboardPage';
import { CandidateAnalysisPage } from './pages/CandidateAnalysisPage';

export const App: React.FC = () => {
  return (
    <ToastProvider>
      <BrowserRouter>
        <AppShell>
          <Routes>
            <Route path="/" element={<JobDescriptionPage />} />
            <Route path="/resumes" element={<ResumesPage />} />
            <Route path="/results" element={<ResultsDashboardPage />} />
            <Route path="/candidates/:id" element={<CandidateAnalysisPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AppShell>
      </BrowserRouter>
    </ToastProvider>
  );
};

export default App;

