import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { FileText, Users, Award, RotateCcw, Sparkles } from 'lucide-react';
import { Button } from '../ui/Button';
import { Modal } from '../ui/Modal';
import { useToast } from '../ui/Toast';
import { api } from '../../api/client';

export const AppShell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { success, error } = useToast();
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isResetting, setIsResetting] = useState(false);

  const steps = [
    { number: 1, label: 'Job Description', path: '/', icon: FileText },
    { number: 2, label: 'Resumes', path: '/resumes', icon: Users },
    { number: 3, label: 'Results & Ranking', path: '/results', icon: Award },
  ];

  const currentStep = steps.findIndex((s) => s.path === location.pathname) + 1 || (location.pathname.startsWith('/candidates') ? 3 : 1);

  const handleReset = async () => {
    setIsResetting(true);
    try {
      await api.resetAllData();
      sessionStorage.removeItem('current_jd_id');
      success('System Reset', 'All database records and cached states have been cleared.');
      setIsResetModalOpen(false);
      navigate('/');
    } catch (err: any) {
      error('Reset Failed', err?.message || 'Failed to clear system data.');
    } finally {
      setIsResetting(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col bg-slate-50/70 text-slate-800">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-slate-200/80 shadow-xs">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-brand-700 to-brand-500 flex items-center justify-center text-white shadow-md shadow-brand-500/25">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h1 className="text-base font-bold text-slate-900 tracking-tight leading-tight">
                Semantic Resume Ranker
              </h1>
              <p className="text-[11px] font-medium text-slate-400">Offline AI Matching Engine</p>
            </div>
          </div>

          {/* Stepper Navigation */}
          <nav className="hidden md:flex items-center gap-1 bg-slate-100/80 p-1.5 rounded-xl border border-slate-200/60">
            {steps.map((step) => {
              const Icon = step.icon;
              const isActive = currentStep === step.number;
              const isPast = currentStep > step.number;

              return (
                <button
                  key={step.number}
                  onClick={() => navigate(step.path)}
                  className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                    isActive
                      ? 'bg-white text-brand-700 shadow-xs'
                      : isPast
                      ? 'text-slate-700 hover:text-slate-900 hover:bg-white/50'
                      : 'text-slate-400 hover:text-slate-600'
                  }`}
                >
                  <span
                    className={`w-5 h-5 rounded-md flex items-center justify-center text-[10px] font-bold ${
                      isActive
                        ? 'bg-brand-600 text-white'
                        : isPast
                        ? 'bg-slate-300 text-slate-700'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {step.number}
                  </span>
                  <span>{step.label}</span>
                  <Icon className="w-3.5 h-3.5 opacity-60" />
                </button>
              );
            })}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              leftIcon={<RotateCcw className="w-3.5 h-3.5 text-slate-500" />}
              onClick={() => setIsResetModalOpen(true)}
            >
              Reset Data
            </Button>
          </div>
        </div>
      </header>

      {/* Main Page Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>

      {/* Global Footer */}
      <footer className="border-t border-slate-200/60 bg-white py-4 text-center text-xs text-slate-400">
        Deterministic Multi-Factor Scoring: 40% Skills • 25% Semantic • 20% Experience • 10% Education • 5% Projects
      </footer>

      {/* Reset Confirmation Modal */}
      <Modal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        title="Reset All Match & Candidate Data?"
        description="This will permanently delete all uploaded job descriptions, candidate resumes, and matching results from the database."
        confirmLabel="Reset Everything"
        confirmVariant="danger"
        onConfirm={handleReset}
        isConfirmLoading={isResetting}
      >
        <p className="text-sm text-slate-600">
          Use this to clear out sample data and start fresh for a new demonstration run.
        </p>
      </Modal>
    </div>
  );
};

