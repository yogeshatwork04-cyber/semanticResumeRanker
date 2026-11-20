import React, { useEffect, useState, useMemo, useCallback } from 'react';
import { useSearchParams, useNavigate, Link } from 'react-router-dom';
import {
  Download,
  Search,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  AlertTriangle,
  Users,
  Trophy,
  BarChart3,
  CheckCircle2,
  ChevronRight,
  Filter,
  RefreshCw,
  FolderOpen,
} from 'lucide-react';
import { api } from '../api/client';
import { MatchResultsListResponse, RankedCandidateItem } from '../types';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/Badge';
import { Chip } from '../components/ui/Chip';
import { Spinner } from '../components/ui/Spinner';
import { EmptyState } from '../components/ui/EmptyState';
import { useToast } from '../components/ui/Toast';

type SortField = 'rank' | 'score' | 'experience';
type SortOrder = 'asc' | 'desc';

export const ResultsDashboardPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { info } = useToast();

  const jdIdParam = searchParams.get('jd_id') || sessionStorage.getItem('active_jd_id') || '1';
  const jdId = parseInt(jdIdParam, 10);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resultsData, setResultsData] = useState<MatchResultsListResponse | null>(null);

  // Filters & Sorting state
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'HIGH' | 'MEDIUM' | 'LOW'>('ALL');
  const [minScore, setMinScore] = useState<number>(0);
  const [sortField, setSortField] = useState<SortField>('rank');
  const [sortOrder, setSortOrder] = useState<SortOrder>('asc');

  const fetchResults = useCallback(async () => {
    if (!jdId || isNaN(jdId)) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.getResults(jdId);
      setResultsData(data);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load matching results';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [jdId]);

  useEffect(() => {
    fetchResults();
  }, [fetchResults]);

  // Derived filtered & sorted list
  const filteredAndSortedCandidates = useMemo(() => {
    if (!resultsData || !resultsData.results) return [];

    let list = [...resultsData.results];

    // Status filter
    if (statusFilter !== 'ALL') {
      list = list.filter((c) => c.status_label === statusFilter);
    }

    // Min score slider
    if (minScore > 0) {
      list = list.filter((c) => c.final_score >= minScore);
    }

    // Search query: candidate name or matched skills
    if (searchTerm.trim()) {
      const q = searchTerm.toLowerCase().trim();
      list = list.filter((c) => {
        const nameMatches = c.name.toLowerCase().includes(q);
        const skillMatches = c.matched_skills_top?.some((s) => s.toLowerCase().includes(q));
        const filenameMatches = c.filename.toLowerCase().includes(q);
        return nameMatches || skillMatches || filenameMatches;
      });
    }

    // Sorting
    list.sort((a, b) => {
      let comp = 0;
      if (sortField === 'score') {
        comp = a.final_score - b.final_score;
      } else if (sortField === 'experience') {
        comp = a.experience_years - b.experience_years;
      } else {
        // default rank (by final_score desc)
        comp = b.final_score - a.final_score;
      }
      return sortOrder === 'asc' ? comp : -comp;
    });

    return list;
  }, [resultsData, statusFilter, minScore, searchTerm, sortField, sortOrder]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortOrder(field === 'rank' ? 'asc' : 'desc');
    }
  };

  const handleExportCsv = () => {
    if (!jdId) return;
    const url = api.getExportCsvUrl(jdId);
    window.open(url, '_blank');
    info('Exporting CSV', 'Downloading results CSV export...');
  };

  if (loading) {
    return (
      <div className="py-24 text-center">
        <Spinner size="lg" className="mx-auto mb-4" />
        <h3 className="text-base font-semibold text-slate-800">Calculating Candidate Match Scores...</h3>
        <p className="text-sm text-slate-500 mt-1">
          Evaluating 5-factor scoring model across skills, semantic similarity, and experience.
        </p>
      </div>
    );
  }

  if (error || !resultsData || resultsData.results.length === 0) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={FolderOpen}
          title="No Match Results Available"
          description={
            error
              ? `Error: ${error}. Make sure you have uploaded resumes and run matching for this job description.`
              : 'You have not run matching against this Job Description yet.'
          }
          actionLabel="Go to Upload & Match"
          onAction={() => navigate(`/resumes?jd_id=${jdId}`)}
        />
      </div>
    );
  }

  // Summary Metrics
  const totalScored = resultsData.results.length;
  const scores = resultsData.results.map((c) => c.final_score);
  const topScore = Math.max(...scores);
  const avgScore = (scores.reduce((a, b) => a + b, 0) / totalScored).toFixed(1);
  const highCount = resultsData.results.filter((c) => c.status_label === 'HIGH').length;
  const mediumCount = resultsData.results.filter((c) => c.status_label === 'MEDIUM').length;
  const lowCount = resultsData.results.filter((c) => c.status_label === 'LOW').length;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
      {/* Top Banner / Title */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-2 border-b border-slate-200">
        <div>
          <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-primary-600">
            <span>Evaluation Results</span>
            <span>•</span>
            <span>JD #{resultsData.jd_id}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight mt-1">
            {resultsData.job_title}
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Ranked {totalScored} candidates using deterministic 5-factor scoring (Skills, Semantic, Experience, Projects, Education).
          </p>
        </div>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchResults}
            leftIcon={<RefreshCw className="w-4 h-4" />}
          >
            Refresh
          </Button>
          <Button
            variant="primary"
            size="sm"
            onClick={handleExportCsv}
            leftIcon={<Download className="w-4 h-4" />}
          >
            Export CSV
          </Button>
        </div>
      </div>

      {/* Summary Metrics Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4 flex items-center gap-3 border-slate-200 bg-white">
          <div className="p-2.5 rounded-xl bg-blue-50 text-blue-600">
            <Users className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Candidates</p>
            <p className="text-xl font-bold text-slate-900">{totalScored}</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3 border-slate-200 bg-white">
          <div className="p-2.5 rounded-xl bg-emerald-50 text-emerald-600">
            <Trophy className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Top Match</p>
            <p className="text-xl font-bold text-slate-900">{topScore.toFixed(1)}%</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3 border-slate-200 bg-white">
          <div className="p-2.5 rounded-xl bg-purple-50 text-purple-600">
            <BarChart3 className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Average Score</p>
            <p className="text-xl font-bold text-slate-900">{avgScore}%</p>
          </div>
        </Card>

        <Card className="p-4 flex items-center gap-3 border-slate-200 bg-white">
          <div className="p-2.5 rounded-xl bg-amber-50 text-amber-600">
            <CheckCircle2 className="w-5 h-5" />
          </div>
          <div>
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider">Distribution</p>
            <div className="flex items-center gap-1.5 text-xs font-semibold mt-0.5">
              <span className="text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">{highCount} High</span>
              <span className="text-amber-700 bg-amber-50 px-1.5 py-0.5 rounded">{mediumCount} Med</span>
              <span className="text-slate-600 bg-slate-100 px-1.5 py-0.5 rounded">{lowCount} Low</span>
            </div>
          </div>
        </Card>
      </div>

      {/* Filter and Control Bar */}
      <Card className="p-4 bg-white border-slate-200 space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search candidate name, skills (e.g. Docker, Python)..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:bg-white transition-all"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400 hover:text-slate-600"
              >
                Clear
              </button>
            )}
          </div>

          {/* Status Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Status:</span>
            <div className="inline-flex rounded-lg border border-slate-200 bg-slate-50 p-0.5 text-xs font-medium">
              {(['ALL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-3 py-1 rounded-md transition-colors ${
                    statusFilter === status
                      ? 'bg-white text-slate-900 shadow-sm font-semibold'
                      : 'text-slate-600 hover:text-slate-900'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

          {/* Min-Score Slider */}
          <div className="flex items-center gap-3 min-w-[200px]">
            <span className="text-xs font-semibold text-slate-500 uppercase tracking-wider whitespace-nowrap">
              Min Score: <span className="text-slate-900 font-bold">{minScore}%</span>
            </span>
            <input
              type="range"
              min="0"
              max="95"
              step="5"
              value={minScore}
              onChange={(e) => setMinScore(parseInt(e.target.value, 10))}
              className="w-28 accent-primary-600 cursor-pointer"
            />
          </div>
        </div>

        {/* Results Count indicator */}
        <div className="flex items-center justify-between text-xs text-slate-500 pt-1 border-t border-slate-100">
          <span>
            Showing <strong className="text-slate-800">{filteredAndSortedCandidates.length}</strong> of{' '}
            {resultsData.results.length} candidates
          </span>
          {(searchTerm || statusFilter !== 'ALL' || minScore > 0) && (
            <button
              onClick={() => {
                setSearchTerm('');
                setStatusFilter('ALL');
                setMinScore(0);
              }}
              className="text-primary-600 hover:underline font-medium"
            >
              Reset Filters
            </button>
          )}
        </div>
      </Card>

      {/* Candidates Ranking Table */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="bg-slate-50/80 border-b border-slate-200 text-xs font-bold text-slate-600 uppercase tracking-wider select-none">
                <th
                  className="py-3.5 px-4 cursor-pointer hover:bg-slate-100/70 transition-colors"
                  onClick={() => toggleSort('rank')}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Rank</span>
                    {sortField === 'rank' ? (
                      sortOrder === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-primary-600" /> : <ArrowDown className="w-3.5 h-3.5 text-primary-600" />
                    ) : (
                      <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                    )}
                  </div>
                </th>
                <th className="py-3.5 px-4">Candidate</th>
                <th
                  className="py-3.5 px-4 cursor-pointer hover:bg-slate-100/70 transition-colors"
                  onClick={() => toggleSort('experience')}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Experience</span>
                    {sortField === 'experience' ? (
                      sortOrder === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-primary-600" /> : <ArrowDown className="w-3.5 h-3.5 text-primary-600" />
                    ) : (
                      <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                    )}
                  </div>
                </th>
                <th
                  className="py-3.5 px-4 cursor-pointer hover:bg-slate-100/70 transition-colors"
                  onClick={() => toggleSort('score')}
                >
                  <div className="flex items-center gap-1.5">
                    <span>Match %</span>
                    {sortField === 'score' ? (
                      sortOrder === 'asc' ? <ArrowUp className="w-3.5 h-3.5 text-primary-600" /> : <ArrowDown className="w-3.5 h-3.5 text-primary-600" />
                    ) : (
                      <ArrowUpDown className="w-3.5 h-3.5 text-slate-400" />
                    )}
                  </div>
                </th>
                <th className="py-3.5 px-4">Matched Skills</th>
                <th className="py-3.5 px-4">Status</th>
                <th className="py-3.5 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 text-sm">
              {filteredAndSortedCandidates.map((candidate: RankedCandidateItem) => {
                // Find rank in the master results
                const rank = resultsData.results.findIndex((c) => c.candidate_id === candidate.candidate_id) + 1;
                const scorePercent = candidate.final_score;

                // Color coding for score bar
                let scoreColor = 'bg-primary-500';
                if (scorePercent >= 80) scoreColor = 'bg-emerald-500';
                else if (scorePercent >= 60) scoreColor = 'bg-amber-500';
                else scoreColor = 'bg-slate-400';

                return (
                  <tr
                    key={candidate.candidate_id}
                    onClick={() => navigate(`/candidates/${candidate.candidate_id}?jd_id=${jdId}`)}
                    className="hover:bg-slate-50/80 cursor-pointer transition-colors group"
                  >
                    {/* Rank */}
                    <td className="py-4 px-4 font-mono font-bold text-slate-700">
                      <div className="flex items-center gap-2">
                        {rank === 1 && (
                          <span className="w-6 h-6 rounded-full bg-amber-100 text-amber-700 flex items-center justify-center text-xs font-extrabold">
                            1
                          </span>
                        )}
                        {rank === 2 && (
                          <span className="w-6 h-6 rounded-full bg-slate-200 text-slate-700 flex items-center justify-center text-xs font-extrabold">
                            2
                          </span>
                        )}
                        {rank === 3 && (
                          <span className="w-6 h-6 rounded-full bg-amber-50 text-amber-800 border border-amber-200 flex items-center justify-center text-xs font-extrabold">
                            3
                          </span>
                        )}
                        {rank > 3 && (
                          <span className="text-slate-500 pl-1.5 font-medium">#{rank}</span>
                        )}
                      </div>
                    </td>

                    {/* Candidate */}
                    <td className="py-4 px-4">
                      <div>
                        <div className="font-semibold text-slate-900 group-hover:text-primary-600 transition-colors flex items-center gap-1.5">
                          <span>{candidate.name}</span>
                        </div>
                        <div className="text-xs text-slate-400 font-mono mt-0.5 truncate max-w-[200px]">
                          {candidate.filename}
                        </div>
                      </div>
                    </td>

                    {/* Experience */}
                    <td className="py-4 px-4 font-mono text-slate-700 font-medium">
                      {candidate.relevant_years !== undefined && candidate.total_years !== undefined ? (
                        <div>
                          <span className="text-slate-800">{candidate.relevant_years.toFixed(1)}y rel</span>
                          <span className="text-slate-400 text-xs ml-1.5">({candidate.total_years.toFixed(1)}y total)</span>
                        </div>
                      ) : (
                        <span>{candidate.experience_years.toFixed(1)} years</span>
                      )}
                    </td>

                    {/* Match Score & Color bar */}
                    <td className="py-4 px-4">
                      <div className="w-36">
                        <div className="flex items-center justify-between text-xs font-bold text-slate-800 mb-1 font-mono">
                          <span>{candidate.final_score.toFixed(1)}%</span>
                        </div>
                        <div className="w-full bg-slate-100 h-2 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${scoreColor}`}
                            style={{ width: `${Math.min(100, Math.max(0, candidate.final_score))}%` }}
                          />
                        </div>
                      </div>
                    </td>

                    {/* Matched Skills */}
                    <td className="py-4 px-4">
                      <div className="flex flex-wrap items-center gap-1 max-w-sm">
                        {candidate.matched_skills_top?.map((sk) => (
                          <Chip key={sk} label={sk} variant="matched" />
                        ))}
                        {candidate.matched_skills_count > (candidate.matched_skills_top?.length ?? 0) && (
                          <span
                            className="text-xs text-slate-500 font-medium bg-slate-100 px-1.5 py-0.5 rounded-full cursor-default"
                            title={`${candidate.matched_skills_count} total matched skills`}
                          >
                            +{candidate.matched_skills_count - (candidate.matched_skills_top?.length ?? 0)} more
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Status Badge + Cap marker */}
                    <td className="py-4 px-4 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <StatusBadge status={candidate.status_label} />

                        {candidate.possible_keyword_stuffing && (
                          <span
                            title="Possible keyword stuffing: Over 70% of matched skills appear only in a skills list without documented experience, and fewer than 2 demonstrated skills were found."
                            className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-amber-100 text-amber-800 border border-amber-300 whitespace-nowrap"
                          >
                            Possible keyword stuffing
                          </span>
                        )}

                        {/* Experience Cap Marker: only if experience_cap_applied === true */}
                        {candidate.experience_cap_applied && (
                          <span
                            title="Capped at LOW (years < 50% of requirement)"
                            className="inline-flex items-center text-amber-600 hover:text-amber-700 cursor-help"
                          >
                            <AlertTriangle className="w-4 h-4 text-amber-500" />
                          </span>
                        )}
                      </div>
                    </td>

                    {/* Action */}
                    <td className="py-4 px-4 text-right">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-slate-400 group-hover:text-primary-600"
                      >
                        <ChevronRight className="w-4 h-4" />
                      </Button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredAndSortedCandidates.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-sm text-slate-500">No candidates match your search and filter criteria.</p>
          </div>
        )}
      </div>

      {/* Footer Navigation */}
      <div className="flex items-center justify-between pt-2">
        <Link
          to={`/resumes?jd_id=${jdId}`}
          className="text-sm font-semibold text-slate-600 hover:text-slate-900 flex items-center gap-1"
        >
          ← Upload More Resumes
        </Link>
        <span className="text-xs text-slate-400">
          Score threshold: HIGH ≥ 80% | MEDIUM 60-79.9% | LOW &lt; 60%
        </span>
      </div>
    </div>
  );
};

export default ResultsDashboardPage;
