const API_BASE = 'http://localhost:8420/v1';

interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
  message?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || error.message || `HTTP ${response.status}`);
    }

    return response.json();
  }

  // Projects
  async createProject(name: string, sourcePath: string, profileId?: string) {
    return this.request<ApiResponse<any>>('/projects', {
      method: 'POST',
      body: JSON.stringify({ name, source_path: sourcePath, profile_id: profileId }),
    });
  }

  async listProjects(page = 1, pageSize = 20, search?: string) {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    if (search) params.set('search', search);
    
    return this.request<ApiResponse<any>>(`/projects?${params}`);
  }

  async getProject(id: string) {
    return this.request<ApiResponse<any>>(`/projects/${id}`);
  }

  async ingestProject(id: string, options: {
    createProxy?: boolean;
    extractAudio?: boolean;
    audioTrack?: number;
    normalizeAudio?: boolean;
  } = {}) {
    return this.request<ApiResponse<{ jobId: string }>>(`/projects/${id}/ingest`, {
      method: 'POST',
      body: JSON.stringify({
        create_proxy: options.createProxy ?? true,
        extract_audio: options.extractAudio ?? true,
        audio_track: options.audioTrack ?? 0,
        normalize_audio: options.normalizeAudio ?? true,
      }),
    });
  }

  async analyzeProject(id: string, options: {
    transcribe?: boolean;
    whisperModel?: string;
    language?: string;
    detectScenes?: boolean;
    analyzeAudio?: boolean;
    detectFaces?: boolean;
    scoreSegments?: boolean;
    customDictionary?: string[];
  } = {}) {
    return this.request<ApiResponse<{ jobId: string }>>(`/projects/${id}/analyze`, {
      method: 'POST',
      body: JSON.stringify({
        transcribe: options.transcribe ?? true,
        whisper_model: options.whisperModel ?? 'large-v3',
        language: options.language,
        detect_scenes: options.detectScenes ?? true,
        analyze_audio: options.analyzeAudio ?? true,
        detect_faces: options.detectFaces ?? true,
        score_segments: options.scoreSegments ?? true,
        custom_dictionary: options.customDictionary,
      }),
    });
  }

  async getTimeline(projectId: string) {
    return this.request<ApiResponse<any>>(`/projects/${projectId}/timeline`);
  }

  async listSegments(projectId: string, options: {
    page?: number;
    pageSize?: number;
    sortBy?: 'score' | 'startTime' | 'duration';
    sortOrder?: 'asc' | 'desc';
    minScore?: number;
  } = {}) {
    const params = new URLSearchParams({
      page: (options.page ?? 1).toString(),
      page_size: (options.pageSize ?? 20).toString(),
      sort_by: options.sortBy ?? 'score',
      sort_order: options.sortOrder ?? 'desc',
    });
    if (options.minScore !== undefined) {
      params.set('min_score', options.minScore.toString());
    }
    
    return this.request<ApiResponse<any>>(`/projects/${projectId}/segments?${params}`);
  }

  // Alias for getSegments
  async getSegments(projectId: string, options: {
    page?: number;
    pageSize?: number;
    sortBy?: 'score' | 'startTime' | 'duration';
    sortOrder?: 'asc' | 'desc';
    minScore?: number;
  } = {}) {
    return this.listSegments(projectId, options);
  }

  async getSegment(projectId: string, segmentId: string) {
    return this.request<ApiResponse<any>>(`/projects/${projectId}/segments/${segmentId}`);
  }

  async generateVariants(projectId: string, segmentId: string, variants: any[], renderProxy = true) {
    return this.request<ApiResponse<{ jobId: string }>>(`/projects/${projectId}/segments/${segmentId}/variants`, {
      method: 'POST',
      body: JSON.stringify({ variants, render_proxy: renderProxy }),
    });
  }

  async exportSegment(projectId: string, options: {
    segmentId: string;
    variant?: string;
    templateId?: string;
    platform?: string;
    includeCaptions?: boolean;
    includeCover?: boolean;
    includeMetadata?: boolean;
    includePost?: boolean;
    useNvenc?: boolean;
  }) {
    return this.request<ApiResponse<{ jobId: string }>>(`/projects/${projectId}/export`, {
      method: 'POST',
      body: JSON.stringify({
        segment_id: options.segmentId,
        variant: options.variant ?? 'A',
        template_id: options.templateId,
        platform: options.platform ?? 'tiktok',
        include_captions: options.includeCaptions ?? true,
        include_cover: options.includeCover ?? true,
        include_metadata: options.includeMetadata ?? true,
        include_post: options.includePost ?? true,
        use_nvenc: options.useNvenc ?? true,
      }),
    });
  }

  async listArtifacts(projectId: string) {
    return this.request<ApiResponse<any[]>>(`/projects/${projectId}/artifacts`);
  }

  // Jobs
  async getJob(jobId: string) {
    return this.request<ApiResponse<any>>(`/jobs/${jobId}`);
  }

  async getProjectJobs(projectId: string) {
    return this.request<ApiResponse<any[]>>(`/jobs?project_id=${projectId}`);
  }

  async cancelJob(jobId: string) {
    return this.request<ApiResponse<{ cancelled: boolean }>>(`/jobs/${jobId}/cancel`, {
      method: 'POST',
    });
  }

  // Templates
  async listTemplates() {
    return this.request<ApiResponse<any[]>>('/templates');
  }

  async createTemplate(template: any) {
    return this.request<ApiResponse<any>>('/templates', {
      method: 'POST',
      body: JSON.stringify(template),
    });
  }

  // Profiles
  async listProfiles() {
    return this.request<ApiResponse<any[]>>('/profiles');
  }

  async createProfile(profile: any) {
    return this.request<ApiResponse<any>>('/profiles', {
      method: 'POST',
      body: JSON.stringify(profile),
    });
  }

  // System
  async getCapabilities() {
    return this.request<any>('/capabilities');
  }

  async checkHealth() {
    return fetch('http://localhost:8420/health').then(r => r.json());
  }
}

export const api = new ApiClient();


