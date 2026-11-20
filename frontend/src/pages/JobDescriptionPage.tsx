import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileUp, AlignLeft, Sparkles, Check, ArrowRight, Plus, RefreshCw } from 'lucide-react';
import { api } from '../api/client';
import { JDResponse } from '../types';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardContent, CardFooter } from '../components/ui/Card';
import { Chip } from '../components/ui/Chip';
import { useToast } from '../components/ui/Toast';

const SAMPLE_JD_TEXT = `Job Title: Senior Backend Python Engineer

About The Role:
We are looking for a Senior Backend Python Engineer to join our core engineering team. You will build and scale reliable, high-performance web services and backend architectures powering our cloud platform.

Key Responsibilities:
- Design, build, and maintain robust, scalable REST APIs using Python and FastAPI.
- Architect and optimize relational database schemas and complex queries using PostgreSQL and SQLAlchemy.
- Containerize application services using Docker and manage deployments.
- Build clean unit and integration test suites with Pytest to maintain high code quality.
- Collaborate with frontend engineers and DevOps on CI/CD pipelines and cloud deployments.
- Participate in code reviews, technical architecture designs, and system scaling discussions.

Required Qualifications:
- 3+ years of professional software development experience in backend engineering.
- Strong proficiency in Python and modern frameworks like FastAPI.
- Hands-on experience with PostgreSQL, relational database design, and ORMs.
- Practical experience with Docker and containerization concepts.
- Demonstrated experience in REST APIs design, HTTP protocols, and microservices architecture.
- Bachelor's degree in Computer Science, Software Engineering, or equivalent practical experience.

Preferred Qualifications (Nice to Have):
- Experience with in-memory caching solutions such as Redis.
- Familiarity with Kubernetes, Helm, and container orchestration.
- Cloud experience with AWS (ECS, S3, RDS, Lambda) or GCP.
- Experience with CI/CD automation tools like GitHub Actions or GitLab CI.
- Experience with automated testing workflows and Pytest.
- Knowledge of asynchronous programming (asyncio, Celery) and message queues.`;

export const JobDescriptionPage: React.FC = () => {
  const navigate = useNavigate();
  const { success, error, info } = useToast();

  const [activeTab, setActiveTab] = useState<'paste' | 'upload'>('paste');
  const [pastedText, setPastedText] = useState('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Extracted JD State
  const [extractedJD, setExtractedJD] = useState<JDResponse | null>(null);
  const [title, setTitle] = useState('');
  const [requiredSkills, setRequiredSkills] = useState<string[]>([]);
  const [preferredSkills, setPreferredSkills] = useState<string[]>([]);
  const [minExpYears, setMinExpYears] = useState<number>(0);
  const [educationLevel, setEducationLevel] = useState('bachelor');
  const [responsibilities, setResponsibilities] = useState<string[]>([]);

  // Chip addition inputs
  const [newReqSkill, setNewReqSkill] = useState('');
  const [newPrefSkill, setNewPrefSkill] = useState('');
  const [newResp, setNewResp] = useState('');

  // Check for existing JD in session
  useEffect(() => {
    const savedJdId = sessionStorage.getItem('current_jd_id');
    if (savedJdId) {
      api.getJD(Number(savedJdId))
        .then((data) => {
          populateFields(data);
        })
        .catch(() => {
          sessionStorage.removeItem('current_jd_id');
        });
    }
  }, []);

  const populateFields = (data: JDResponse) => {
    setExtractedJD(data);
    setTitle(data.title);
    setRequiredSkills(data.required_skills);
    setPreferredSkills(data.preferred_skills);
    setMinExpYears(data.min_experience_years);
    setEducationLevel(data.education_level);
    setResponsibilities(data.responsibilities);
    sessionStorage.setItem('current_jd_id', data.id.toString());
  };

  const handleUseSample = () => {
    setActiveTab('paste');
    setPastedText(SAMPLE_JD_TEXT);
    info('Sample Loaded', 'Loaded Senior Backend Python Engineer job description.');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      let jd: JDResponse;
      if (activeTab === 'upload') {
        if (!selectedFile) {
          error('File Missing', 'Please select a PDF, DOCX, or TXT file to upload.');
          setIsSubmitting(false);
          return;
        }
        jd = await api.createJDFromFile(selectedFile);
      } else {
        if (!pastedText.trim() || pastedText.trim().length < 10) {
          error('Text Too Short', 'Please enter at least 10 characters for the Job Description.');
          setIsSubmitting(false);
          return;
        }
        jd = await api.createJDFromText(pastedText);
      }

      populateFields(jd);
      success('Requirements Extracted', `Parsed ${jd.required_skills.length} required and ${jd.preferred_skills.length} preferred skills.`);
    } catch (err: any) {
      error('Extraction Failed', err?.message || 'Failed to extract requirements from JD.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveChanges = async () => {
    if (!extractedJD) return;
    setIsSaving(true);

    try {
      const updated = await api.updateJD(extractedJD.id, {
        title: title.trim(),
        required_skills: requiredSkills,
        preferred_skills: preferredSkills,
        min_experience_years: minExpYears,
        education_level: educationLevel,
        responsibilities,
      });

      populateFields(updated);
      success('Saved', 'Job description requirements updated successfully.');
    } catch (err: any) {
      error('Save Failed', err?.message || 'Failed to update job description.');
    } finally {
      setIsSaving(false);
    }
  };

  const handleContinue = () => {
    if (!extractedJD) {
      error('No JD Selected', 'Please extract or save a Job Description before proceeding.');
      return;
    }
    navigate('/resumes');
  };

  return (
    <div className="space-y-8 animate-fade-in max-w-5xl mx-auto">
      {/* Top Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200/80">
        <div>
          <h2 className="text-2xl font-extrabold text-slate-900 tracking-tight">Step 1: Job Description</h2>
          <p className="text-sm text-slate-500 mt-1">
            Provide the role description. The engine will extract skills, experience thresholds, and responsibilities.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={handleUseSample}
          leftIcon={<Sparkles className="w-4 h-4 text-brand-600" />}
        >
          Use Sample Python JD
        </Button>
      </div>

      {/* Input Section */}
      <Card>
        <CardHeader className="flex items-center justify-between">
          <div className="flex gap-2 p-1 bg-slate-100 rounded-lg">
            <button
              type="button"
              onClick={() => setActiveTab('paste')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === 'paste' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <AlignLeft className="w-3.5 h-3.5" />
              <span>Paste Text</span>
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('upload')}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-md text-xs font-semibold transition-all ${
                activeTab === 'upload' ? 'bg-white text-slate-900 shadow-xs' : 'text-slate-500 hover:text-slate-800'
              }`}
            >
              <FileUp className="w-3.5 h-3.5" />
              <span>Upload Document</span>
            </button>
          </div>
          <span className="text-xs text-slate-400">Deterministic NLP Parsing</span>
        </CardHeader>

        <form onSubmit={handleSubmit}>
          <CardContent>
            {activeTab === 'paste' ? (
              <div>
                <textarea
                  value={pastedText}
                  onChange={(e) => setPastedText(e.target.value)}
                  placeholder="Paste job description text here (including responsibilities and qualifications)..."
                  rows={8}
                  className="w-full text-xs font-mono p-3.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 bg-slate-50/50 leading-relaxed text-slate-800"
                />
              </div>
            ) : (
              <div className="p-8 border-2 border-dashed border-slate-200 hover:border-brand-400 rounded-xl flex flex-col items-center justify-center bg-slate-50/50 transition-colors">
                <FileUp className="w-8 h-8 text-slate-400 mb-2" />
                <p className="text-sm font-medium text-slate-700">Choose a JD file (.pdf, .docx, or .txt)</p>
                <p className="text-xs text-slate-400 mt-0.5">Maximum size: 5 MB</p>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="mt-4 text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-brand-50 file:text-brand-700 hover:file:bg-brand-100 cursor-pointer"
                />
              </div>
            )}
          </CardContent>

          <CardFooter className="flex items-center justify-between">
            <span className="text-xs text-slate-400">
              SpaCy PhraseMatcher + SentenceTransformer embeddings
            </span>
            <Button
              type="submit"
              variant="primary"
              size="md"
              isLoading={isSubmitting}
              leftIcon={<Sparkles className="w-4 h-4" />}
            >
              Extract Requirements
            </Button>
          </CardFooter>
        </form>
      </Card>

      {/* Extracted & Editable Fields */}
      {extractedJD && (
        <Card className="border-brand-200/80 shadow-md animate-slide-in">
          <CardHeader className="bg-gradient-to-r from-brand-50/50 to-white flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex-1 min-w-0">
              <span className="text-[11px] font-bold text-brand-700 uppercase tracking-wider">
                Extracted Job Profile #{extractedJD.id}
              </span>
              <input
                type="text"
                value={title}
                title={title}
                onChange={(e) => setTitle(e.target.value)}
                className="block text-lg font-bold text-slate-900 border-b border-transparent hover:border-slate-300 focus:border-brand-500 focus:outline-none bg-transparent w-full mt-0.5 truncate"
              />
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <Button
                variant="outline"
                size="sm"
                onClick={handleSaveChanges}
                isLoading={isSaving}
                leftIcon={<RefreshCw className="w-3.5 h-3.5" />}
              >
                Save Corrections
              </Button>
              <Button
                variant="primary"
                size="sm"
                onClick={handleContinue}
                rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
              >
                Continue to Resumes
              </Button>
            </div>
          </CardHeader>

          <CardContent className="space-y-6">
            {/* Required Skills (Weight 2.0) */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                  Required Skills (Weight 2.0) • {requiredSkills.length}
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={newReqSkill}
                    onChange={(e) => setNewReqSkill(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newReqSkill.trim()) {
                        e.preventDefault();
                        if (!requiredSkills.includes(newReqSkill.trim())) {
                          setRequiredSkills([...requiredSkills, newReqSkill.trim()]);
                        }
                        setNewReqSkill('');
                      }
                    }}
                    placeholder="+ Add required skill..."
                    className="text-xs px-2.5 py-1 rounded-md border border-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (newReqSkill.trim() && !requiredSkills.includes(newReqSkill.trim())) {
                        setRequiredSkills([...requiredSkills, newReqSkill.trim()]);
                        setNewReqSkill('');
                      }
                    }}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 p-3 bg-slate-50/80 rounded-xl border border-slate-200/60 min-h-[50px]">
                {requiredSkills.map((skill) => (
                  <Chip
                    key={skill}
                    label={skill}
                    variant="brand"
                    onRemove={() => setRequiredSkills(requiredSkills.filter((s) => s !== skill))}
                  />
                ))}
              </div>
            </div>

            {/* Preferred Skills (Weight 1.0) */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                  Preferred Skills (Weight 1.0) • {preferredSkills.length}
                </label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="text"
                    value={newPrefSkill}
                    onChange={(e) => setNewPrefSkill(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newPrefSkill.trim()) {
                        e.preventDefault();
                        if (!preferredSkills.includes(newPrefSkill.trim())) {
                          setPreferredSkills([...preferredSkills, newPrefSkill.trim()]);
                        }
                        setNewPrefSkill('');
                      }
                    }}
                    placeholder="+ Add preferred skill..."
                    className="text-xs px-2.5 py-1 rounded-md border border-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      if (newPrefSkill.trim() && !preferredSkills.includes(newPrefSkill.trim())) {
                        setPreferredSkills([...preferredSkills, newPrefSkill.trim()]);
                        setNewPrefSkill('');
                      }
                    }}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </Button>
                </div>
              </div>
              <div className="flex flex-wrap gap-2 p-3 bg-slate-50/80 rounded-xl border border-slate-200/60 min-h-[50px]">
                {preferredSkills.map((skill) => (
                  <Chip
                    key={skill}
                    label={skill}
                    variant="default"
                    onRemove={() => setPreferredSkills(preferredSkills.filter((s) => s !== skill))}
                  />
                ))}
              </div>
            </div>

            {/* Thresholds: Min Experience & Education Level */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
              <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/60">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                  Minimum Experience (Years)
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    step="0.5"
                    min="0"
                    max="30"
                    value={minExpYears}
                    onChange={(e) => setMinExpYears(Math.max(0, parseFloat(e.target.value) || 0))}
                    className="text-sm font-semibold px-3 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 w-28 bg-white"
                  />
                  <span className="text-xs text-slate-500">years required for full credit</span>
                </div>
              </div>

              <div className="p-4 bg-slate-50/80 rounded-xl border border-slate-200/60">
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">
                  Required Education Level
                </label>
                <select
                  value={educationLevel}
                  onChange={(e) => setEducationLevel(e.target.value)}
                  className="text-sm font-semibold px-3 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-500 bg-white capitalize w-full"
                >
                  <option value="none">None Required</option>
                  <option value="diploma">Diploma / Associate</option>
                  <option value="bachelor">Bachelor's Degree</option>
                  <option value="master">Master's Degree</option>
                  <option value="phd">PhD / Doctorate</option>
                </select>
              </div>
            </div>

            {/* Responsibilities list */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold text-slate-700 uppercase tracking-wide">
                  Target Responsibilities (Semantic Embeddings Anchor) • {responsibilities.length}
                </label>
              </div>
              <div className="space-y-2 p-3 bg-slate-50/80 rounded-xl border border-slate-200/60">
                {responsibilities.map((resp, idx) => (
                  <div key={idx} className="flex items-start gap-2 bg-white p-2.5 rounded-lg border border-slate-200 text-xs text-slate-700">
                    <span className="w-4 h-4 rounded-full bg-brand-100 text-brand-700 flex items-center justify-center font-bold text-[10px] shrink-0 mt-0.5">
                      {idx + 1}
                    </span>
                    <span className="flex-1 leading-relaxed">{resp}</span>
                    <button
                      type="button"
                      onClick={() => setResponsibilities(responsibilities.filter((_, i) => i !== idx))}
                      className="text-slate-400 hover:text-rose-600 transition-colors"
                    >
                      ×
                    </button>
                  </div>
                ))}

                <div className="flex items-center gap-2 pt-2">
                  <input
                    type="text"
                    value={newResp}
                    onChange={(e) => setNewResp(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && newResp.trim()) {
                        e.preventDefault();
                        setResponsibilities([...responsibilities, newResp.trim()]);
                        setNewResp('');
                      }
                    }}
                    placeholder="+ Add a key responsibility sentence..."
                    className="flex-1 text-xs px-3 py-1.5 rounded-lg border border-slate-200 focus:outline-none focus:ring-1 focus:ring-brand-500"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      if (newResp.trim()) {
                        setResponsibilities([...responsibilities, newResp.trim()]);
                        setNewResp('');
                      }
                    }}
                  >
                    Add
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>

          <CardFooter className="flex items-center justify-between">
            <span className="text-xs text-slate-500">
              Recruiter edits are applied directly to the matching engine.
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="md"
                onClick={handleSaveChanges}
                isLoading={isSaving}
                leftIcon={<Check className="w-4 h-4 text-emerald-600" />}
              >
                Save Changes
              </Button>
              <Button
                variant="primary"
                size="md"
                onClick={handleContinue}
                rightIcon={<ArrowRight className="w-4 h-4" />}
              >
                Proceed to Resume Upload
              </Button>
            </div>
          </CardFooter>
        </Card>
      )}
    </div>
  );
};

