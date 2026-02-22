import axios, { AxiosInstance } from 'axios';
import type {
  UploadResponse,
  AnalysisStatusResponse,
  EvidenceResponse,
  HealthResponse,
} from '../types/api';

class ApiClient {
  private client: AxiosInstance;

  constructor() {
    const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
    const authToken = import.meta.env.VITE_AUTH_TOKEN || '';

    this.client = axios.create({
      baseURL,
      headers: {
        'Content-Type': 'application/json',
        ...(authToken && { Authorization: `Bearer ${authToken}` }),
      },
    });

    // Request interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          // Server responded with error
          throw new Error(
            error.response.data?.error_message ||
            error.response.data?.message ||
            `API Error: ${error.response.status}`
          );
        } else if (error.request) {
          // Request made but no response
          throw new Error('Network error: Could not reach server');
        } else {
          // Something else happened
          throw new Error(error.message || 'An unexpected error occurred');
        }
      }
    );
  }

  async uploadVideo(file: File, policyName?: string): Promise<UploadResponse> {
    const formData = new FormData();
    formData.append('video', file);
    if (policyName) {
      formData.append('policy_name', policyName);
    }

    const response = await this.client.post<UploadResponse>(
      '/analyses',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    );
    return response.data;
  }

  async getAnalysis(analysisId: string): Promise<AnalysisStatusResponse> {
    const response = await this.client.get<AnalysisStatusResponse>(
      `/analyses/${analysisId}`
    );
    return response.data;
  }

  async getEvidence(analysisId: string): Promise<EvidenceResponse> {
    const response = await this.client.get<EvidenceResponse>(
      `/analyses/${analysisId}/evidence`
    );
    return response.data;
  }

  async listAnalyses(limit = 50, offset = 0): Promise<AnalysisStatusResponse[]> {
    const response = await this.client.get<AnalysisStatusResponse[]>(
      `/analyses?limit=${limit}&offset=${offset}`
    );
    return response.data;
  }

  async getHealth(): Promise<HealthResponse> {
    const response = await this.client.get<HealthResponse>('/health');
    return response.data;
  }
}

export const api = new ApiClient();
