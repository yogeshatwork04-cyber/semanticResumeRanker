import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileText,
  AlertTriangle,
  CheckCircle,
  Play,
  RotateCcw,
  Trash2,
  Users,
  Info,
} from 'lucide-react';
import { api } from '../api/client';
import { CandidateSummaryResponse } from '../types';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Modal } from '../components/ui/Modal';
import { Spinner } from '../components/ui/Spinner';
import { useToast } from '../components/ui/Toast';

const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5 MB
const MAX_BATCH_FILES = 30;
const ALLOWED_EXTENSIONS = ['.pdf', '.docx'];

export const ResumesPage: React.FC = () => {
  const navigate = useNavigate();
  const { success, error, info } = useToast();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isMatching, setIsMatching] = useState(false);
  const [existingCandidates, setExistingCandidates] = useState<CandidateSummaryResponse[]>([]);
  const [isLoadingExisting, setIsLoadingExisting] = useState(true);
  const [isResetModalOpen, setIsResetModalOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  const currentJdId = sessionStorage.getItem('current_jd_id');

  // Load existing uploaded candidates
  const loadCandidates = async () => {
    try {
      const candidates = await api.listCandidates();
      setExistingCandidates(candidates);
    } catch {
      // ignore
    } finally {
      setIsLoadingExisting(false);
    }
  };

  useEffect(() => {
    loadCandidates();
  }, []);

  const validateFiles = (files: File[]): File[] => {
    const valid: File[] = [];

    if (files.length + selectedFiles.length > MAX_BATCH_FILES) {
      error('Limit Exceeded', `Maximum ${MAX_BATCH_FILES} files allowed per batch.`);
      return [];
    }

    for (const f of files) {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (!ALLOWED_EXTENSIONS.includes(ext)) {
        error('Invalid Format', `${f.name}: Only .pdf and .docx files are supported.`);
        continue;
      }
      if (f.size > MAX_FILE_SIZE) {
        error('File Too Large', `${f.name}: Exceeds 5 MB limit (${(f.size / (1024 * 1024)).toFixed(1)} MB).`);
        continue;
      }
      valid.push(f);
    }

    return valid;
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    const valid = validateFiles(droppedFiles);
    if (valid.length > 0) {
      setSelectedFiles((prev) => [...prev, ...valid]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const chosen = Array.from(e.target.files);
      const valid = validateFiles(chosen);
      if (valid.length > 0) {
        setSelectedFiles((prev) => [...prev, ...valid]);
      }
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0) {
      error('No Files Selected', 'Please select or drag-and-drop resume files first.');
      return;
    }

    setIsUploading(true);
    try {
      const res = await api.uploadResumes(selectedFiles);
      success(
        'Upload Complete',
        `Processed ${res.total_uploaded} files: ${res.successful} parsed successfully, ${res.failed} unparseable.`
      );
      setSelectedFiles([]);
      await loadCandidates();
    } catch (err: any) {
      error('Upload Failed', err?.message || 'Failed to upload resumes.');
    } finally {
      setIsUploading(false);
    }
  };

  const handleRunMatching = async () => {
    if (!currentJdId) {
      error('Missing JD', 'No active Job Description found. Please extract a Job Description first.');
      navigate('/');
      return;
    }

    const parsedCount = existingCandidates.filter((c) => c.parse_status === 'parsed').length;
    if (parsedCount === 0) {
      error('No Resumes', 'Please upload at least one valid resume before running matching.');
      return;
    }

    setIsMatching(true);
    try {
      await api.runMatch(Number(currentJdId));
      success('Matching Complete', `Deterministic 5-factor scoring finished for ${parsedCount} candidates.`);
      navigate('/results');
    } catch (err: any) {
      error('Matching Failed', err?.message || 'Failed to execute matching pipeline.');
    } finally {
      setIsMatching(false);
    }
  };

  const handleReset = async () => {
    try {
      await api.resetAllData();
      setExistingCandidates([]);
      setSelectedFiles([]);
      setIsResetModalOpen(false);
      info('Reset Complete', 'All candidate records have been cleared.');
    } catch (err: any) {
      error('Reset Failed', err?.message || 'Failed to reset data.');
    }
  };

  const parsedCandidates = existingCandidates.filter((c) => c.parse_status === 'parsed');
  const failedCandidates = existingCandidates.filter((c) => c.parse_status === 'failed');

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200/80">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Step 2: Candidate Resumes</h2>
          <p className="text-sm text-slate-500 mt-1">
            Upload candidate resumes (.pdf, .docx). Multi-file drag-and-drop up to 30 files per batch.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {existingCandidates.length > 0 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setIsResetModalOpen(true)}
              leftIcon={<RotateCcw className="w-3.5 h-3.5" />}
            >
              Reset Data
            </Button>
          )}
          <Button
            variant="primary"
            size="md"
            onClick={handleRunMatching}
            isLoading={isMatching}
            disabled={parsedCandidates.length === 0}
            leftIcon={<Play className="w-4 h-4 fill-current" />}
          >
            Run Matching Engine ({parsedCandidates.length})
          </Button>
        </div>
      </div>

      {/* Drag & Drop Upload Card */}
      <Card>
        <CardContent>
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-2xl p-8 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
              isDragging
                ? 'border-brand-500 bg-brand-50/50 scale-[1.005]'
                : 'border-slate-300 hover:border-brand-400 bg-slate-50/40 hover:bg-slate-50'
            }`}
          >
            <div className="w-12 h-12 rounded-xl bg-brand-50 border border-brand-100 flex items-center justify-center text-brand-600 mb-3 shadow-xs">
              <UploadCloud className="w-6 h-6" />
            </div>
            <h3 className="text-sm font-bold text-slate-800">
              Drag & Drop Resumes Here, or <span className="text-brand-600 underline">Browse</span>
            </h3>
            <p className="text-xs text-slate-400 mt-1">
              Supports PDF and DOCX documents • Up to 30 files • Max 5 MB each
            </p>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf,.docx"
              onChange={handleFileInputChange}
              className="hidden"
            />
          </div>

          {/* Staged file list ready for upload */}
          {selectedFiles.length > 0 && (
            <div className="mt-5 p-4 rounded-xl bg-slate-50 border border-slate-200/80">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                  Staged Files ({selectedFiles.length})
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedFiles([])}
                  className="text-xs text-rose-600 hover:text-rose-700 hover:bg-rose-50"
                >
                  Clear All
                </Button>
              </div>
              <div className="max-h-52 overflow-y-auto space-y-1.5 pr-1">
                {selectedFiles.map((file, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between p-2 rounded-lg bg-white border border-slate-200 text-xs"
                  >
                    <div className="flex items-center gap-2 truncate">
                      <FileText className="w-4 h-4 text-brand-600 shrink-0" />
                      <span className="font-medium text-slate-800 truncate">{file.name}</span>
                      <span className="text-slate-400 text-[11px]">({(file.size / 1024).toFixed(1)} KB)</span>
                    </div>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedFiles(selectedFiles.filter((_, i) => i !== idx));
                      }}
                      className="text-slate-400 hover:text-rose-600 p-1"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex justify-end">
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleUpload}
                  isLoading={isUploading}
                  leftIcon={<UploadCloud className="w-4 h-4" />}
                >
                  Upload & Parse {selectedFiles.length} Resumes
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Uploaded Candidates Status Table */}
      <Card>
        <CardHeader className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
          <div>
            <h3 className="text-base font-bold text-slate-900">Uploaded Profiles ({existingCandidates.length})</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Parsed profiles stored in database. Scanned or empty documents are flagged with clear errors.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 text-xs text-emerald-700 bg-emerald-50 px-2.5 py-1 rounded-md border border-emerald-200 font-semibold">
              <CheckCircle className="w-3.5 h-3.5" /> {parsedCandidates.length} Ready
            </span>
            {failedCandidates.length > 0 && (
              <span className="inline-flex items-center gap-1.5 text-xs text-rose-700 bg-rose-50 px-2.5 py-1 rounded-md border border-rose-200 font-semibold">
                <AlertTriangle className="w-3.5 h-3.5" /> {failedCandidates.length} Failed
              </span>
            )}
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {isLoadingExisting ? (
            <div className="py-12">
              <Spinner label="Loading profiles..." />
            </div>
          ) : existingCandidates.length === 0 ? (
            <div className="p-8 text-center text-slate-400 text-sm">
              <Users className="w-8 h-8 mx-auto mb-2 opacity-50" />
              No resumes uploaded yet. Upload sample resumes from <code className="bg-slate-100 px-1 py-0.5 rounded text-xs font-mono">sample_data/resumes</code> to begin.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 font-semibold uppercase tracking-wider">
                    <th className="py-3 px-4">Candidate / File</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4">Experience</th>
                    <th className="py-3 px-4">Education</th>
                    <th className="py-3 px-4">Detected Skills</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {existingCandidates.map((c) => {
                    const isParsed = c.parse_status === 'parsed';
                    return (
                      <tr key={c.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-semibold text-slate-900">{c.name}</div>
                          <div className="text-[11px] text-slate-400 font-mono mt-0.5">{c.filename}</div>
                        </td>
                        <td className="py-3 px-4">
                          {isParsed ? (
                            <Badge variant="high" size="sm">
                              Parsed
                            </Badge>
                          ) : (
                            <div>
                              <Badge variant="low" size="sm">
                                Failed
                              </Badge>
                              {c.parse_error && (
                                <p className="text-[11px] text-rose-600 mt-1 max-w-xs break-words">
                                  {c.parse_error}
                                </p>
                              )}
                            </div>
                          )}
                        </td>
                        <td className="py-3 px-4 text-slate-600 font-mono">
                          {isParsed ? `${c.total_experience_years.toFixed(1)} yrs` : '—'}
                        </td>
                        <td className="py-3 px-4 text-slate-600 capitalize">
                          {isParsed ? c.education_level : '—'}
                        </td>
                        <td className="py-3 px-4">
                          {isParsed ? (
                            <div className="text-slate-600">
                              <span className="font-semibold text-slate-800">{c.skills.length}</span> skills found
                              {c.skills.length > 0 && (
                                <div className="text-[11px] text-slate-400 truncate max-w-sm mt-0.5">
                                  {c.skills.slice(0, 5).join(', ')}
                                  {c.skills.length > 5 ? ` +${c.skills.length - 5} more` : ''}
                                </div>
                              )}
                            </div>
                          ) : (
                            <span className="text-slate-400">—</span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>

        <CardFooter className="flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Info className="w-3.5 h-3.5 text-brand-500" />
            <span>Overlapping concurrent job dates are merged automatically with zero double-counting.</span>
          </div>
          <Button
            variant="primary"
            size="md"
            onClick={handleRunMatching}
            isLoading={isMatching}
            disabled={parsedCandidates.length === 0}
            leftIcon={<Play className="w-4 h-4 fill-current" />}
          >
            Run Matching Engine
          </Button>
        </CardFooter>
      </Card>

      {/* Reset Confirmation Modal */}
      <Modal
        isOpen={isResetModalOpen}
        onClose={() => setIsResetModalOpen(false)}
        title="Reset All Uploaded Resumes?"
        description="This will clear all uploaded candidate profiles and match scores from the database."
        confirmLabel="Reset Data"
        confirmVariant="danger"
        onConfirm={handleReset}
      />
    </div>
  );
};

