/**
 * TypeScript domain types exactly mirroring the backend FastAPI Pydantic v2 schemas.
 */

export interface JDResponse {
  id: number;
  title: string;
  raw_text: string;
  required_skills: string[];
  preferred_skills: string[];
  min_experience_years: number;
  education_level: string;
  responsibilities: string[];
  created_at: string;
}

export interface JDUpdateRequest {
  title?: string;
  required_skills?: string[];
  preferred_skills?: string[];
  min_experience_years?: number;
  education_level?: string;
  responsibilities?: string[];
}

export interface CandidateSummaryResponse {
  id: number;
  filename: string;
  name: string;
  email: string | null;
  phone: string | null;
  total_experience_years: number;
  education_level: string;
  skills: string[];
  parse_status: 'parsed' | 'failed';
  parse_error: string | null;
  created_at: string;
}

export interface CandidateUploadBatchResponse {
  total_uploaded: number;
  successful: number;
  failed: number;
  candidates: CandidateSummaryResponse[];
  errors: Array<{ filename: string; error: string }>;
}

export interface RankedCandidateItem {
  candidate_id: number;
  name: string;
  filename: string;
  experience_years: number;
  relevant_years?: number;
  total_years?: number;
  final_score: number;
  status_label: 'HIGH' | 'MEDIUM' | 'LOW';
  sub_scores: {
    skill: number;
    semantic: number;
    experience: number;
    education: number;
    project: number;
  };
  matched_skills_top: string[];
  matched_skills_count: number;
  missing_skills_count: number;
  experience_cap_applied: boolean;
  possible_keyword_stuffing?: boolean;
  required_years: number;
  found_years: number;
  cap_ratio: number;
}

export interface MatchResultsListResponse {
  jd_id: number;
  job_title: string;
  total_candidates: number;
  results: RankedCandidateItem[];
}

export interface SkillMatchDetail {
  skill: string;
  matched_via?: string;
  rule?: 'exact' | 'alias' | 'curated' | 'embedding' | string;
  evidence_source?: 'demonstrated' | 'listed' | string;
  credit?: number;
  weight?: number;
  similarity?: number;
}

export interface PartialSkillDetail {
  jd_skill: string;
  matched_via: string;
  similarity: number;
  rule: 'curated' | 'embedding' | string;
  evidence_source: 'demonstrated' | 'listed' | string;
  credit: number;
  weight: number;
}

export interface ExperienceComparison {
  required_years: number;
  found_years: number;
  relevant_years?: number;
  total_years?: number;
  ratio: number;
  percentage: number;
  meets_requirement: boolean;
  cap_ratio?: number;
  experience_cap_applied?: boolean;
}

export interface CandidateAnalysisResponse {
  candidate_id: number;
  name: string;
  email: string | null;
  phone: string | null;
  filename: string;
  overall_score: number;
  relevant_years?: number;
  total_years?: number;
  status_label: 'HIGH' | 'MEDIUM' | 'LOW';
  experience_cap_applied: boolean;
  possible_keyword_stuffing?: boolean;
  required_years: number;
  found_years: number;
  cap_ratio: number;
  sub_scores: {
    skill: number;
    semantic: number;
    experience: number;
    education: number;
    project: number;
  };
  extracted_info: {
    total_experience_years: number;
    education_level: string;
    job_titles: string[];
    sections_found: string[];
    skills_count: number;
  };
  matched_skills: SkillMatchDetail[];
  partial_skills: PartialSkillDetail[];
  missing_skills: string[];
  experience_comparison: ExperienceComparison;
  explanation_bullets: string[];
  headline: string;
  recommendation: string;
  raw_evidence: Record<string, unknown>;
}

export interface HealthResponse {
  status: string;
  app_name: string;
  version: string;
  database: string;
  database_type: string;
  models_loaded: boolean;
  models: Record<string, string>;
  weights: Record<string, number>;
}
