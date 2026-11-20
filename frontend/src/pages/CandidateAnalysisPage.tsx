import React, { useEffect, useState } from 'react';
import { useParams, useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  AlertTriangle,
  Award,
  CheckCircle2,
  XCircle,
  Briefcase,
  GraduationCap,
  Layers,
  Sparkles,
  Mail,
  Phone,
  FileCode,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts';
import { api } from '../api/client';
import {
  CandidateAnalysisResponse,
  RankedCandidateItem,
} from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/Badge';
import { Chip } from '../components/ui/Chip';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';

const FACTOR_WEIGHTS = [
  { key: 'skill', label: 'Skill Match', weight: 40, weightText: '40%' },
  { key: 'experience', label: 'Experience', weight: 25, weightText: '25%' },
  { key: 'semantic', label: 'Semantic Fit', weight: 20, weightText: '20%' },
  { key: 'project', label: 'Project Depth', weight: 10, weightText: '10%' },
  { key: 'education', label: 'Role & Domain', weight: 5, weightText: '5%' },
];

export const CandidateAnalysisPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const candidateId = parseInt(id || '0', 10);
  const jdIdParam = searchParams.get('jd_id') || sessionStorage.getItem('active_jd_id') || '1';
  const jdId = parseInt(jdIdParam, 10);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<CandidateAnalysisResponse | null>(null);
  const [rankedList, setRankedList] = useState<RankedCandidateItem[]>([]);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      if (!candidateId || !jdId) return;
      setLoading(true);
      setError(null);
      try {
        const [candData, resultsData] = await Promise.all([
          api.getCandidateAnalysis(candidateId, jdId),
          api.getResults(jdId).catch(() => null),
        ]);

        if (isMounted) {
          setAnalysis(candData);
          if (resultsData && resultsData.results) {
            setRankedList(resultsData.results);
          }
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Failed to load candidate analysis');
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadData();

    return () => {
      isMounted = false;
    };
  }, [candidateId, jdId]);

  if (loading) {
    return (
      <div className="py-24 text-center">
        <Spinner size="lg" className="mx-auto mb-4" />
        <h3 className="text-base font-semibold text-slate-800">Generating Candidate Analysis...</h3>
        <p className="text-sm text-slate-500 mt-1">
          Loading 5-factor breakdown, skill evidence sources, and explanation rationale.
        </p>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={AlertCircle}
          title="Analysis Not Found"
          description={error || `Could not find candidate analysis for ID #${candidateId}`}
          actionLabel="Return to Dashboard"
          onAction={() => navigate(`/results?jd_id=${jdId}`)}
        />
      </div>
    );
  }

  // Calculate Next and Previous candidate for cycling
  const currentIndex = rankedList.findIndex((c) => c.candidate_id === candidateId);
  const prevCandidate = currentIndex > 0 ? rankedList[currentIndex - 1] : null;
  const nextCandidate =
    currentIndex >= 0 && currentIndex < rankedList.length - 1
      ? rankedList[currentIndex + 1]
      : null;

  // Chart data for 5 sub-scores
  const chartData = [
    {
      factor: 'Skills (40%)',
      score: Number(analysis.sub_scores.skill.toFixed(1)),
      weight: '40%',
      color: '#3b82f6',
    },
    {
      factor: 'Semantic (25%)',
      score: Number(analysis.sub_scores.semantic.toFixed(1)),
      weight: '25%',
      color: '#8b5cf6',
    },
    {
      factor: 'Experience (20%)',
      score: Number(analysis.sub_scores.experience.toFixed(1)),
      weight: '20%',
      color: '#10b981',
    },
    {
      factor: 'Education (10%)',
      score: Number(analysis.sub_scores.education.toFixed(1)),
      weight: '10%',
      color: '#ec4899',
    },
    {
      factor: 'Projects (5%)',
      score: Number(analysis.sub_scores.project.toFixed(1)),
      weight: '5%',
      color: '#f59e0b',
    },
  ];

  const overallScore = analysis.overall_score;

  // Color for overall score
  let scoreBadgeColor = 'text-primary-600 bg-primary-50 border-primary-200';
  if (overallScore >= 80) {
    scoreBadgeColor = 'text-emerald-700 bg-emerald-50 border-emerald-200';
  } else if (overallScore >= 60) {
    scoreBadgeColor = 'text-amber-700 bg-amber-50 border-amber-200';
  } else {
    scoreBadgeColor = 'text-slate-600 bg-slate-100 border-slate-200';
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Navigation Bar: Back & Prev/Next */}
      <div className="flex items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <Link
          to={`/results?jd_id=${jdId}`}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Rankings</span>
        </Link>

        {rankedList.length > 0 && (
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400 font-mono hidden sm:inline">
              Rank {currentIndex >= 0 ? currentIndex + 1 : '-'} of {rankedList.length}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={!prevCandidate}
              onClick={() => {
                if (prevCandidate) {
                  navigate(`/candidates/${prevCandidate.candidate_id}?jd_id=${jdId}`);
                }
              }}
              leftIcon={<ArrowLeft className="w-3.5 h-3.5" />}
            >
              Previous
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={!nextCandidate}
              onClick={() => {
                if (nextCandidate) {
                  navigate(`/candidates/${nextCandidate.candidate_id}?jd_id=${jdId}`);
                }
              }}
              rightIcon={<ArrowRight className="w-3.5 h-3.5" />}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Candidate Header Card */}
      <Card className="p-6 bg-white border-slate-200 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
          {/* Candidate Info */}
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight">
                {analysis.name}
              </h1>
              <div className="flex items-center gap-1.5 flex-wrap">
                <StatusBadge status={analysis.status_label} />

                {analysis.possible_keyword_stuffing && (
                  <span
                    title="Possible keyword stuffing: Over 70% of matched skills appear only in a skills list without documented experience, and fewer than 2 demonstrated skills were found."
                    className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300"
                  >
                    Possible keyword stuffing
                  </span>
                )}

                {/* Experience Cap Warning icon next to LOW if applied */}
                {analysis.experience_cap_applied && (
                  <span
                    title="Capped at LOW (years < 50% of requirement)"
                    className="inline-flex items-center text-amber-600 hover:text-amber-700 cursor-help"
                  >
                    <AlertTriangle className="w-5 h-5 text-amber-500" />
                  </span>
                )}
              </div>
            </div>

            {/* Sub-contact details */}
            <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-1">
              {analysis.email && (
                <span className="flex items-center gap-1">
                  <Mail className="w-3.5 h-3.5 text-slate-400" />
                  <span>{analysis.email}</span>
                </span>
              )}
              {analysis.phone && (
                <span className="flex items-center gap-1">
                  <Phone className="w-3.5 h-3.5 text-slate-400" />
                  <span>{analysis.phone}</span>
                </span>
              )}
              <span className="flex items-center gap-1 font-mono text-slate-400">
                <FileCode className="w-3.5 h-3.5" />
                <span>{analysis.filename}</span>
              </span>
            </div>
          </div>

          {/* Prominent Overall Score Gauge */}
          <div className="flex items-center gap-4">
            <div
              className={`flex flex-col items-center justify-center w-28 h-28 rounded-2xl border-2 shadow-sm ${scoreBadgeColor}`}
            >
              <span className="text-xs font-bold uppercase tracking-wider opacity-75">
                Match Score
              </span>
              <span className="text-3xl font-black font-mono tracking-tight mt-0.5">
                {overallScore.toFixed(1)}
              </span>
              <span className="text-[10px] font-medium opacity-60">out of 100</span>
            </div>
          </div>
        </div>

        {/* Experience Cap Warning Banner if applied */}
        {analysis.experience_cap_applied && (
          <div className="mt-5 p-3.5 bg-amber-50 border border-amber-200 rounded-xl flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-800">
              <span className="font-bold">Experience Cap Policy Applied:</span> Candidate has{' '}
              <strong>{analysis.found_years.toFixed(1)} years</strong> of verified experience, which
              is below 50% of the <strong>{analysis.required_years.toFixed(1)} years</strong> hard
              requirement (threshold: {(analysis.cap_ratio * 100).toFixed(0)}%). The status label has
              been restricted to <strong>LOW</strong>.
            </div>
          </div>
        )}
      </Card>

      {/* 2-Column Overview: Extracted Profile & Sub-Score Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Extracted Profile Info */}
        <Card className="p-5 bg-white border-slate-200 space-y-4">
          <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
            <Briefcase className="w-4 h-4 text-primary-600" />
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Extracted Profile
            </h2>
          </div>

          <div className="space-y-3 text-xs">
            {/* Total Experience */}
            <div className="flex items-center justify-between py-1.5 border-b border-slate-50">
              <span className="text-slate-500 font-medium">Total Experience</span>
              <span className="font-bold font-mono text-slate-800">
                {analysis.extracted_info.total_experience_years.toFixed(1)} years
              </span>
            </div>

            {/* Education */}
            <div className="flex items-center justify-between py-1.5 border-b border-slate-50">
              <span className="text-slate-500 font-medium flex items-center gap-1">
                <GraduationCap className="w-3.5 h-3.5 text-slate-400" />
                Education
              </span>
              <span className="font-semibold text-slate-800 capitalize">
                {analysis.extracted_info.education_level || 'Not specified'}
              </span>
            </div>

            {/* Recent / Extracted Titles */}
            <div className="py-1.5 border-b border-slate-50">
              <span className="text-slate-500 font-medium block mb-1">Recent Titles / Roles</span>
              <div className="flex flex-wrap gap-1">
                {analysis.extracted_info.job_titles.length > 0 ? (
                  analysis.extracted_info.job_titles.map((title, i) => (
                    <span
                      key={i}
                      className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium text-[11px]"
                    >
                      {title}
                    </span>
                  ))
                ) : (
                  <span className="text-slate-400 italic">None detected</span>
                )}
              </div>
            </div>

            {/* Sections Found */}
            <div className="py-1.5">
              <span className="text-slate-500 font-medium flex items-center gap-1 mb-1">
                <Layers className="w-3.5 h-3.5 text-slate-400" />
                Detected Sections ({analysis.extracted_info.sections_found.length})
              </span>
              <div className="flex flex-wrap gap-1">
                {analysis.extracted_info.sections_found.map((sec) => (
                  <span
                    key={sec}
                    className="px-2 py-0.5 rounded bg-primary-50 text-primary-700 font-mono text-[10px]"
                  >
                    {sec}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Card>

        {/* Right Column (2 spans): 5-Factor Sub-Score Breakdown */}
        <Card className="lg:col-span-2 p-5 bg-white border-slate-200 space-y-4">
          <div className="flex items-center justify-between pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-primary-600" />
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                5-Factor Scoring Breakdown
              </h2>
            </div>
            <span className="text-xs font-mono text-slate-400">Sum = Final Score</span>
          </div>

          {/* Recharts Bar Chart */}
          <div className="h-44 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={chartData}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
              >
                <XAxis type="number" domain={[0, 100]} tick={{ fontSize: 11 }} />
                <YAxis
                  type="category"
                  dataKey="factor"
                  tick={{ fontSize: 11, fill: '#475569' }}
                  width={110}
                />
                <Tooltip
                  formatter={(value: unknown) => [
                    `${typeof value === 'number' ? value.toFixed(1) : value}%`,
                    'Score',
                  ]}
                />
                <Bar dataKey="score" radius={[0, 4, 4, 0]}>
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* Detailed factors table / list */}
          <div className="grid grid-cols-1 sm:grid-cols-5 gap-2 pt-2 border-t border-slate-100">
            {FACTOR_WEIGHTS.map(({ key, label, weightText }) => {
              const val = (analysis.sub_scores as Record<string, number>)[key] || 0;
              return (
                <div key={key} className="p-2.5 rounded-lg bg-slate-50 border border-slate-100">
                  <div className="flex items-center justify-between text-[11px] text-slate-500 mb-0.5">
                    <span>{label}</span>
                    <span className="font-semibold text-primary-600">{weightText}</span>
                  </div>
                  <div className="text-base font-bold font-mono text-slate-900">
                    {val.toFixed(1)}%
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      {/* Experience Comparison Bar */}
      <Card className="p-5 bg-white border-slate-200 space-y-3">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Briefcase className="w-4 h-4 text-primary-600" />
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Experience Requirement Evaluation
            </h2>
          </div>
          <div className="text-xs font-semibold">
            {analysis.found_years >= analysis.required_years ? (
              <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200">
                ✓ Meets Requirement
              </span>
            ) : (
              <span className="text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200">
                Below Requirement
              </span>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium text-slate-600">
              Required: <strong className="text-slate-900">{analysis.required_years.toFixed(1)} years</strong>
            </span>
            <span className="font-medium text-slate-600">
              Candidate:{' '}
              <strong className="text-slate-900">
                {analysis.relevant_years !== undefined && analysis.total_years !== undefined
                  ? `${analysis.relevant_years.toFixed(1)}y relevant (${analysis.total_years.toFixed(1)}y total)`
                  : `${analysis.found_years.toFixed(1)} years`}
              </strong>{' '}
              ({((analysis.found_years / (analysis.required_years || 1)) * 100).toFixed(0)}% of target)
            </span>
          </div>

          {/* Dual bar showing required vs found */}
          <div className="w-full bg-slate-100 h-3 rounded-full overflow-hidden flex">
            <div
              className={`h-full transition-all duration-500 ${
                analysis.found_years >= analysis.required_years ? 'bg-emerald-500' : 'bg-amber-500'
              }`}
              style={{
                width: `${Math.min(
                  100,
                  Math.max(5, (analysis.found_years / (analysis.required_years || 1)) * 100)
                )}%`,
              }}
            />
          </div>
        </div>
      </Card>

      {/* Skills Analysis: Matched, Partial, Missing */}
      <Card className="p-6 bg-white border-slate-200 space-y-6">
        <div className="flex items-center justify-between pb-2 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <Award className="w-4 h-4 text-primary-600" />
            <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
              Skills Matching Analysis
            </h2>
          </div>
          <span className="text-xs text-slate-400">
            Work history credit: 100% | Listed-only credit: 50%
          </span>
        </div>

        {/* Group 1: Matched Skills (Green) */}
        <div className="space-y-2.5">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Matched Skills ({analysis.matched_skills.length})
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {analysis.matched_skills.length > 0 ? (
              analysis.matched_skills.map((m, idx) => {
                const isDemonstrated = m.evidence_source === 'demonstrated';
                return (
                  <div
                    key={idx}
                    className="inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium bg-emerald-50 text-emerald-800 border border-emerald-200 shadow-2xs"
                  >
                    <span>{m.skill}</span>
                    {isDemonstrated ? (
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-200/70 text-emerald-900 uppercase">
                        Work
                      </span>
                    ) : (
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-slate-200/80 text-slate-600 uppercase">
                        Listed
                      </span>
                    )}
                  </div>
                );
              })
            ) : (
              <p className="text-xs text-slate-400 italic">No exact skill matches found.</p>
            )}
          </div>
        </div>

        {/* Group 2: Partial Matches (Amber) */}
        <div className="space-y-2.5 pt-2 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Partial Matches ({analysis.partial_skills.length})
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {analysis.partial_skills.length > 0 ? (
              analysis.partial_skills.map((p, idx) => (
                <div
                  key={idx}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-amber-50 text-amber-900 border border-amber-200 shadow-2xs"
                >
                  <span className="font-semibold">{p.matched_via}</span>
                  <span className="text-amber-500 font-mono">→</span>
                  <span className="font-bold text-amber-800">{p.jd_skill}</span>
                  <span className="px-1.5 py-0.2 rounded text-[10px] bg-amber-200/80 text-amber-950 font-mono">
                    {p.rule}, {(p.credit * 100).toFixed(0)}%
                  </span>
                </div>
              ))
            ) : (
              <p className="text-xs text-slate-400 italic">No partial skill matches found.</p>
            )}
          </div>
        </div>

        {/* Group 3: Missing Skills (Red/Rose) */}
        <div className="space-y-2.5 pt-2 border-t border-slate-100">
          <div className="flex items-center gap-2">
            <XCircle className="w-4 h-4 text-rose-600" />
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
              Missing Skills ({analysis.missing_skills.length})
            </h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {analysis.missing_skills.length > 0 ? (
              analysis.missing_skills.map((m, idx) => (
                <Chip key={idx} label={m} variant="missing" />
              ))
            ) : (
              <p className="text-xs text-emerald-600 font-medium">All required JD skills matched!</p>
            )}
          </div>
        </div>
      </Card>

      {/* Why This Score: Headline, Bullets, Recommendation */}
      <Card className="p-6 bg-white border-slate-200 space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-100">
          <Sparkles className="w-4 h-4 text-primary-600" />
          <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
            Explainable Rationale & Recruiter Insights
          </h2>
        </div>

        {/* Headline */}
        <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl">
          <p className="text-sm font-bold text-slate-800 leading-snug">
            {analysis.headline}
          </p>
        </div>

        {/* Explanation Bullets */}
        <div className="space-y-2">
          <h3 className="text-xs font-bold text-slate-500 uppercase tracking-wider">
            Evaluation Breakdown
          </h3>
          <ul className="space-y-2 text-xs text-slate-700">
            {analysis.explanation_bullets.map((bullet, idx) => {
              const isPositive =
                bullet.includes('Demonstrated') ||
                bullet.includes('Matched') ||
                bullet.includes('Strong') ||
                bullet.includes('exceeds');
              const isNegative =
                bullet.includes('Missing') ||
                bullet.includes('below') ||
                bullet.includes('capped') ||
                bullet.includes('listed only');

              return (
                <li
                  key={idx}
                  className={`flex items-start gap-2.5 p-2 rounded-lg border ${
                    isNegative
                      ? 'bg-rose-50/50 border-rose-100 text-rose-900'
                      : isPositive
                      ? 'bg-emerald-50/40 border-emerald-100 text-slate-800'
                      : 'bg-slate-50 border-slate-100 text-slate-700'
                  }`}
                >
                  <span className="shrink-0 mt-0.5">
                    {isNegative ? (
                      <XCircle className="w-3.5 h-3.5 text-rose-500" />
                    ) : isPositive ? (
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500" />
                    ) : (
                      <span className="w-1.5 h-1.5 rounded-full bg-slate-400 inline-block" />
                    )}
                  </span>
                  <span className="leading-relaxed">{bullet}</span>
                </li>
              );
            })}
          </ul>
        </div>

        {/* Recommendation */}
        {analysis.recommendation && (
          <div className="pt-3 border-t border-slate-100">
            <div className="flex items-center gap-1.5 text-xs font-bold text-slate-700 uppercase tracking-wider mb-1">
              <ShieldCheck className="w-4 h-4 text-primary-600" />
              <span>Next Steps Recommendation</span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed bg-primary-50/50 p-3 rounded-lg border border-primary-100">
              {analysis.recommendation}
            </p>
          </div>
        )}
      </Card>
    </div>
  );
};

export default CandidateAnalysisPage;
