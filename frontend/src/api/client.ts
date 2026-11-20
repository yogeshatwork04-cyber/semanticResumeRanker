import {
  CandidateAnalysisResponse,
  CandidateSummaryResponse,
  CandidateUploadBatchResponse,
  HealthResponse,
  JDResponse,
  JDUpdateRequest,
  MatchResultsListResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_URL || '/api';

class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;
  const response = await fetch(url, options);

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    let data;
    try {
      data = await response.json();
      if (data && data.detail) {
        errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
      }
    } catch {
      // not json
    }
    throw new ApiError(errorDetail, response.status, data);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // Health
  async getHealth(): Promise<HealthResponse> {
    return request<HealthResponse>('/health');
  },

  // Job Description
  async createJDFromText(text: string): Promise<JDResponse> {
    return request<JDResponse>('/jd', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
  },

  async createJDFromFile(file: File): Promise<JDResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return request<JDResponse>('/jd', {
      method: 'POST',
      body: formData,
    });
  },

  async getJD(id: number): Promise<JDResponse> {
    return request<JDResponse>(`/jd/${id}`);
  },

  async updateJD(id: number, payload: JDUpdateRequest): Promise<JDResponse> {
    return request<JDResponse>(`/jd/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  },

  // Resumes
  async uploadResumes(files: File[]): Promise<CandidateUploadBatchResponse> {
    const formData = new FormData();
    for (const file of files) {
      formData.append('files', file);
    }
    return request<CandidateUploadBatchResponse>('/resumes', {
      method: 'POST',
      body: formData,
    });
  },

  async listCandidates(): Promise<CandidateSummaryResponse[]> {
    return request<CandidateSummaryResponse[]>('/resumes');
  },

  // Matching & Results
  async runMatch(jdId: number): Promise<MatchResultsListResponse> {
    return request<MatchResultsListResponse>('/match', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ jd_id: jdId }),
    });
  },

  async getResults(jdId: number): Promise<MatchResultsListResponse> {
    return request<MatchResultsListResponse>(`/results?jd_id=${jdId}`);
  },

  async getCandidateAnalysis(id: number, jdId: number): Promise<CandidateAnalysisResponse> {
    return request<CandidateAnalysisResponse>(`/candidates/${id}?jd_id=${jdId}`);
  },

  getExportCsvUrl(jdId: number): string {
    return `${BASE_URL}/results/export.csv?jd_id=${jdId}`;
  },

  // Reset demo
  async resetAllData(): Promise<{ message: string; deleted: boolean }> {
    return request<{ message: string; deleted: boolean }>('/reset', {
      method: 'DELETE',
    });
  },
};
