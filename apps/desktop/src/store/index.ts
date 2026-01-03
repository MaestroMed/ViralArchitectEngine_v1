import { create } from 'zustand';
import { temporal } from 'zundo';

// Engine status store
interface EngineState {
  connected: boolean;
  port: number;
  services: {
    ffmpeg: boolean;
    whisper: boolean;
    nvenc: boolean;
    database: boolean;
  };
  setConnected: (connected: boolean) => void;
  setServices: (services: EngineState['services']) => void;
}

export const useEngineStore = create<EngineState>((set) => ({
  connected: false,
  port: 8420,
  services: {
    ffmpeg: false,
    whisper: false,
    nvenc: false,
    database: false,
  },
  setConnected: (connected) => set({ connected }),
  setServices: (services) => set({ services }),
}));

// Active jobs store
interface Job {
  id: string;
  type: string;
  projectId?: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  stage?: string;
  message?: string;
  error?: string;
}

interface JobsState {
  jobs: Job[];
  addJob: (job: Job) => void;
  updateJob: (id: string, updates: Partial<Job>) => void;
  upsertJob: (job: Job) => void;
  removeJob: (id: string) => void;
}

export const useJobsStore = create<JobsState>((set) => ({
  jobs: [],
  addJob: (job) => set((state) => ({ jobs: [...state.jobs, job] })),
  updateJob: (id, updates) => set((state) => ({
    jobs: state.jobs.map((j) => (j.id === id ? { ...j, ...updates } : j)),
  })),
  upsertJob: (job) => set((state) => {
    const index = state.jobs.findIndex((j) => j.id === job.id);
    if (index >= 0) {
      const newJobs = [...state.jobs];
      newJobs[index] = { ...newJobs[index], ...job };
      return { jobs: newJobs };
    }
    return { jobs: [...state.jobs, job] };
  }),
  removeJob: (id) => set((state) => ({
    jobs: state.jobs.filter((j) => j.id !== id),
  })),
}));

// UI state store
interface UIState {
  sidebarCollapsed: boolean;
  currentPanel: 'ingest' | 'analyze' | 'forge' | 'export';
  jobDrawerOpen: boolean;
  shortcutsModalOpen: boolean;
  toggleSidebar: () => void;
  setCurrentPanel: (panel: UIState['currentPanel']) => void;
  setJobDrawerOpen: (open: boolean) => void;
  setShortcutsModalOpen: (open: boolean) => void;
}

export const useUIStore = create<UIState>((set) => ({
  sidebarCollapsed: false,
  currentPanel: 'ingest',
  jobDrawerOpen: false,
  shortcutsModalOpen: false,
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setCurrentPanel: (panel) => set({ currentPanel: panel }),
  setJobDrawerOpen: (open) => set({ jobDrawerOpen: open }),
  setShortcutsModalOpen: (open) => set({ shortcutsModalOpen: open }),
}));

// Batch selection store for segments
interface BatchSelectionState {
  selectedIds: Set<string>;
  isSelectionMode: boolean;
  toggleSelection: (id: string) => void;
  selectAll: (ids: string[]) => void;
  clearSelection: () => void;
  setSelectionMode: (active: boolean) => void;
}

export const useBatchSelectionStore = create<BatchSelectionState>((set) => ({
  selectedIds: new Set(),
  isSelectionMode: false,
  toggleSelection: (id) =>
    set((state) => {
      const newSet = new Set(state.selectedIds);
      if (newSet.has(id)) {
        newSet.delete(id);
      } else {
        newSet.add(id);
      }
      return { selectedIds: newSet };
    }),
  selectAll: (ids) => set({ selectedIds: new Set(ids) }),
  clearSelection: () => set({ selectedIds: new Set(), isSelectionMode: false }),
  setSelectionMode: (active) =>
    set({ isSelectionMode: active, selectedIds: active ? new Set() : new Set() }),
}));

// Toast notifications
interface Toast {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message?: string;
  duration?: number;
}

interface ToastState {
  toasts: Toast[];
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
}

export const useToastStore = create<ToastState>((set) => ({
  toasts: [],
  addToast: (toast) => set((state) => ({
    toasts: [...state.toasts, { ...toast, id: crypto.randomUUID() }],
  })),
  removeToast: (id) => set((state) => ({
    toasts: state.toasts.filter((t) => t.id !== id),
  })),
}));

// Theme store
type Theme = 'light' | 'dark' | 'system';

interface ThemeState {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const getInitialTheme = (): Theme => {
  if (typeof window === 'undefined') return 'dark';
  const stored = localStorage.getItem('forge-theme') as Theme | null;
  if (stored) return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const applyTheme = (theme: Theme) => {
  const root = document.documentElement;
  const isDark = theme === 'dark' || 
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  
  if (isDark) {
    root.classList.add('dark');
  } else {
    root.classList.remove('dark');
  }
  localStorage.setItem('forge-theme', theme);
};

export const useThemeStore = create<ThemeState>((set, get) => {
  // Apply initial theme
  if (typeof window !== 'undefined') {
    const initial = getInitialTheme();
    setTimeout(() => applyTheme(initial), 0);
  }
  
  return {
    theme: typeof window !== 'undefined' ? getInitialTheme() : 'dark',
    setTheme: (theme) => {
      applyTheme(theme);
      set({ theme });
    },
    toggleTheme: () => {
      const current = get().theme;
      const next = current === 'dark' ? 'light' : 'dark';
      applyTheme(next);
      set({ theme: next });
    },
  };
});

// Clip Editor store
interface ClipEditorState {
  selectedSegmentId: string | null;
  playbackTime: number;
  isPlaying: boolean;
  trimStart: number;
  trimEnd: number;
  zoom: number;
  
  setSelectedSegment: (id: string | null) => void;
  setPlaybackTime: (time: number) => void;
  setIsPlaying: (playing: boolean) => void;
  setTrimRange: (start: number, end: number) => void;
  setZoom: (zoom: number) => void;
}

export const useClipEditorStore = create<ClipEditorState>((set) => ({
  selectedSegmentId: null,
  playbackTime: 0,
  isPlaying: false,
  trimStart: 0,
  trimEnd: 0,
  zoom: 1,
  
  setSelectedSegment: (id) => set({ selectedSegmentId: id }),
  setPlaybackTime: (time) => set({ playbackTime: time }),
  setIsPlaying: (playing) => set({ isPlaying: playing }),
  setTrimRange: (start, end) => set({ trimStart: start, trimEnd: end }),
  setZoom: (zoom) => set({ zoom: Math.max(0.5, Math.min(4, zoom)) }),
}));

// Layout Editor store  
interface SourceCrop {
  x: number;      // Normalized 0-1 position in source video
  y: number;
  width: number;
  height: number;
}

interface LayoutZone {
  id: string;
  type: 'facecam' | 'content' | 'custom';
  x: number;           // Target position in 9:16 canvas (%)
  y: number;
  width: number;
  height: number;
  sourceCrop?: SourceCrop;  // Source crop region in 16:9 video (normalized)
  autoTrack?: boolean;      // Enable auto-reframe for this zone
}

interface LayoutEditorState {
  zones: LayoutZone[];
  selectedZoneId: string | null;
  presetName: string;
  
  setZones: (zones: LayoutZone[]) => void;
  updateZone: (id: string, updates: Partial<LayoutZone>) => void;
  setSelectedZone: (id: string | null) => void;
  applyPreset: (preset: string) => void;
}

const LAYOUT_PRESETS: Record<string, LayoutZone[]> = {
  'facecam-top': [
    { id: 'facecam', type: 'facecam', x: 0, y: 0, width: 100, height: 35, 
      sourceCrop: { x: 0.7, y: 0, width: 0.3, height: 0.35 }, autoTrack: false },
    { id: 'content', type: 'content', x: 0, y: 35, width: 100, height: 65,
      sourceCrop: { x: 0, y: 0.25, width: 1, height: 0.75 }, autoTrack: false },
  ],
  'facecam-bottom': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 65,
      sourceCrop: { x: 0, y: 0, width: 1, height: 0.75 }, autoTrack: false },
    { id: 'facecam', type: 'facecam', x: 0, y: 65, width: 100, height: 35,
      sourceCrop: { x: 0.7, y: 0, width: 0.3, height: 0.35 }, autoTrack: false },
  ],
  'split-50-50': [
    { id: 'facecam', type: 'facecam', x: 0, y: 0, width: 100, height: 50,
      sourceCrop: { x: 0.6, y: 0, width: 0.4, height: 0.5 }, autoTrack: false },
    { id: 'content', type: 'content', x: 0, y: 50, width: 100, height: 50,
      sourceCrop: { x: 0, y: 0.3, width: 1, height: 0.7 }, autoTrack: false },
  ],
  'pip-corner': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 100,
      sourceCrop: { x: 0, y: 0, width: 1, height: 1 }, autoTrack: false },
    { id: 'facecam', type: 'facecam', x: 65, y: 5, width: 30, height: 25,
      sourceCrop: { x: 0.7, y: 0, width: 0.3, height: 0.3 }, autoTrack: false },
  ],
  'content-only': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 100,
      sourceCrop: { x: 0, y: 0, width: 1, height: 1 }, autoTrack: false },
  ],
};

export const useLayoutEditorStore = create<LayoutEditorState>()(
  temporal(
    (set) => ({
      zones: LAYOUT_PRESETS['facecam-top'],
      selectedZoneId: null,
      presetName: 'facecam-top',
      
      setZones: (zones) => set({ zones }),
      updateZone: (id, updates) => set((state) => ({
        zones: state.zones.map((z) => (z.id === id ? { ...z, ...updates } : z)),
      })),
      setSelectedZone: (id) => set({ selectedZoneId: id }),
      applyPreset: (preset) => set({
        zones: LAYOUT_PRESETS[preset] || LAYOUT_PRESETS['facecam-top'],
        presetName: preset,
      }),
    }),
    {
      limit: 50,
      partialize: (state) => ({ zones: state.zones }),
    }
  )
);

// Subtitle Style store
interface SubtitleStyle {
  fontFamily: string;
  fontSize: number;
  fontWeight: number;
  color: string;
  backgroundColor: string;
  outlineColor: string;
  outlineWidth: number;
  position: 'bottom' | 'center' | 'top';
  positionY?: number;  // Custom Y position (0-1920, overrides position preset)
  animation: 'none' | 'fade' | 'pop' | 'bounce' | 'glow' | 'wave' | 'typewriter';
  highlightColor: string;
  wordsPerLine: number;  // Max words to show at once (karaoke style)
}

interface SubtitleStyleState {
  style: SubtitleStyle;
  presetName: string;
  setStyle: (updates: Partial<SubtitleStyle>) => void;
  applyPreset: (preset: string) => void;
}

const SUBTITLE_PRESETS: Record<string, SubtitleStyle> = {
  'default': {
    fontFamily: 'Inter',
    fontSize: 48,
    fontWeight: 700,
    color: '#FFFFFF',
    backgroundColor: 'transparent',
    outlineColor: '#000000',
    outlineWidth: 2,
    position: 'bottom',
    animation: 'none',
    highlightColor: '#FFD700',
    wordsPerLine: 6,
  },
  'mrbeast': {
    fontFamily: 'Impact',
    fontSize: 56,
    fontWeight: 900,
    color: '#FFFFFF',
    backgroundColor: 'transparent',
    outlineColor: '#000000',
    outlineWidth: 4,
    position: 'center',
    animation: 'pop',
    highlightColor: '#FF0000',
    wordsPerLine: 4,
  },
  'minimalist': {
    fontFamily: 'Inter',
    fontSize: 42,
    fontWeight: 500,
    color: '#FFFFFF',
    backgroundColor: 'rgba(0,0,0,0.6)',
    outlineColor: 'transparent',
    outlineWidth: 0,
    position: 'bottom',
    animation: 'fade',
    highlightColor: '#00FF00',
    wordsPerLine: 8,
  },
  'karaoke': {
    fontFamily: 'Montserrat',
    fontSize: 52,
    fontWeight: 800,
    color: '#FFFFFF',
    backgroundColor: 'transparent',
    outlineColor: '#000000',
    outlineWidth: 3,
    position: 'bottom',
    animation: 'bounce',
    highlightColor: '#00BFFF',
    wordsPerLine: 5,
  },
  'viral-glow': {
    fontFamily: 'Poppins',
    fontSize: 54,
    fontWeight: 900,
    color: '#FFFFFF',
    backgroundColor: 'transparent',
    outlineColor: '#FF00FF',
    outlineWidth: 2,
    position: 'center',
    animation: 'glow',
    highlightColor: '#00FF88',
    wordsPerLine: 4,
  },
  'wave-gradient': {
    fontFamily: 'Inter',
    fontSize: 50,
    fontWeight: 700,
    color: '#FFFFFF',
    backgroundColor: 'rgba(0,0,0,0.4)',
    outlineColor: '#000000',
    outlineWidth: 1,
    position: 'bottom',
    animation: 'wave',
    highlightColor: '#FFD700',
    wordsPerLine: 5,
  },
};

export const useSubtitleStyleStore = create<SubtitleStyleState>((set) => ({
  style: SUBTITLE_PRESETS['default'],
  presetName: 'default',
  setStyle: (updates) => set((state) => ({
    style: { ...state.style, ...updates },
  })),
  applyPreset: (preset) => set({
    style: SUBTITLE_PRESETS[preset] || SUBTITLE_PRESETS['default'],
    presetName: preset,
  }),
}));

// Projects store - synced via WebSocket
export interface Project {
  id: string;
  name: string;
  status: string;
  sourcePath?: string;
  proxyPath?: string;
  width?: number;
  height?: number;
  duration?: number;
  createdAt?: string;
  updatedAt?: string;
}

interface ProjectsState {
  projects: Project[];
  lastUpdate: number;
  setProjects: (projects: Project[]) => void;
  updateProject: (project: Partial<Project> & { id: string }) => void;
  addProject: (project: Project) => void;
  removeProject: (id: string) => void;
}

export const useProjectsStore = create<ProjectsState>((set) => ({
  projects: [],
  lastUpdate: 0,
  setProjects: (projects) => set({ projects, lastUpdate: Date.now() }),
  updateProject: (project) => set((state) => {
    const index = state.projects.findIndex((p) => p.id === project.id);
    if (index >= 0) {
      const newProjects = [...state.projects];
      newProjects[index] = { ...newProjects[index], ...project };
      return { projects: newProjects, lastUpdate: Date.now() };
    }
    // Project not in list yet, add it
    return { projects: [...state.projects, project as Project], lastUpdate: Date.now() };
  }),
  addProject: (project) => set((state) => ({
    projects: [...state.projects, project],
    lastUpdate: Date.now(),
  })),
  removeProject: (id) => set((state) => ({
    projects: state.projects.filter((p) => p.id !== id),
    lastUpdate: Date.now(),
  })),
}));

// WebSocket store
interface WebSocketState {
  connected: boolean;
  connect: () => void;
  disconnect: () => void;
}

export const useWebSocketStore = create<WebSocketState>((set, get) => {
  let socket: WebSocket | null = null;
  let reconnectTimer: any = null;
  let pollingTimer: any = null;

  // Fallback polling for when WebSocket messages don't come through
  const startPolling = () => {
    if (pollingTimer) return;
    pollingTimer = setInterval(async () => {
      try {
        const response = await fetch('http://localhost:8420/v1/jobs');
        if (response.ok) {
          const data = await response.json();
          const jobs = data.data || [];
          // Update running jobs in store
          jobs.filter((j: any) => j.status === 'running').forEach((job: any) => {
            useJobsStore.getState().upsertJob(job);
          });
        }
      } catch (e) {
        // Ignore polling errors
      }
    }, 3000); // Poll every 3 seconds
  };

  const stopPolling = () => {
    if (pollingTimer) {
      clearInterval(pollingTimer);
      pollingTimer = null;
    }
  };

  const handleMessage = (event: MessageEvent) => {
    try {
      const data = JSON.parse(event.data);
      
      if (data.type === 'JOB_UPDATE') {
        const job = data.payload;
        const prevJob = useJobsStore.getState().jobs.find((j) => j.id === job.id);
        
        // Update jobs store directly
        useJobsStore.getState().upsertJob(job);
        
        // Check for job completion to trigger notifications
        // Now also trigger on pending -> completed (for fast jobs)
        const wasNotComplete = !prevJob || prevJob.status === 'running' || prevJob.status === 'pending';
        if (wasNotComplete && job.status === 'completed') {
          // Desktop notification
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('FORGE LAB', {
              body: `${getJobTypeLabel(job.type)} terminé avec succès`,
              icon: '/icon.png',
            });
          }
          // Toast notification
          useToastStore.getState().addToast({
            type: 'success',
            title: 'Tâche terminée',
            message: `${getJobTypeLabel(job.type)} complété`,
          });
        } else if (wasNotComplete && job.status === 'failed') {
          // Desktop notification for failure
          if ('Notification' in window && Notification.permission === 'granted') {
            new Notification('FORGE LAB', {
              body: `${getJobTypeLabel(job.type)} a échoué`,
              icon: '/icon.png',
            });
          }
          // Toast notification
          useToastStore.getState().addToast({
            type: 'error',
            title: 'Erreur',
            message: job.error || `${getJobTypeLabel(job.type)} a échoué`,
          });
        }
      } else if (data.type === 'PROJECT_UPDATE') {
        // Handle project status updates
        const project = data.payload;
        console.log('Project update received:', project.id, '->', project.status);
        
        // Update projects store
        useProjectsStore.getState().updateProject(project);
        
        // Show toast for status changes
        const statusMessages: Record<string, string> = {
          ingested: 'Ingestion terminée',
          analyzed: 'Analyse terminée',
          error: 'Erreur sur le projet',
        };
        
        if (statusMessages[project.status]) {
          useToastStore.getState().addToast({
            type: project.status === 'error' ? 'error' : 'info',
            title: statusMessages[project.status],
            message: project.name || project.id.slice(0, 8),
          });
        }
      }
    } catch (e) {
      console.error('WS Error:', e);
    }
  };
  
  const getJobTypeLabel = (type: string): string => {
    const labels: Record<string, string> = {
      ingest: 'Ingestion',
      analyze: 'Analyse',
      export: 'Export',
      render_proxy: 'Proxy',
      render_final: 'Rendu final',
    };
    return labels[type] || type;
  };

  const connect = () => {
    // Avoid multiple connections
    if (socket?.readyState === WebSocket.OPEN || socket?.readyState === WebSocket.CONNECTING) return;

    console.log('Connecting to WebSocket...');
    socket = new WebSocket('ws://localhost:8420/v1/ws');
    
    socket.onopen = () => {
      console.log('WS Connected');
      set({ connected: true });
      if (reconnectTimer) clearTimeout(reconnectTimer);
      // Start polling as fallback (in case WS messages don't come through)
      startPolling();
    };

    socket.onclose = () => {
      console.log('WS Disconnected');
      set({ connected: false });
      socket = null;
      // Reconnect logic
      reconnectTimer = setTimeout(connect, 3000);
    };
    
    socket.onerror = (error) => {
      console.error('WS Error:', error);
      // Close will trigger reconnection
      if (socket) socket.close();
    };

    socket.onmessage = handleMessage;
  };

  return {
    connected: false,
    connect,
    disconnect: () => {
      if (reconnectTimer) clearTimeout(reconnectTimer);
      stopPolling();
      if (socket) socket.close();
      socket = null;
      set({ connected: false });
    }
  };
});

// Intro configuration store
export interface IntroConfig {
  enabled: boolean;
  duration: number; // seconds (1-5)
  title: string;
  badgeText: string; // e.g. "@etostark"
  backgroundBlur: number; // 0-30
  titleFont: string;
  titleSize: number;
  titleColor: string;
  badgeColor: string;
  animation: 'fade' | 'slide' | 'zoom' | 'bounce';
}

interface IntroState {
  config: IntroConfig;
  setConfig: (config: Partial<IntroConfig>) => void;
  setEnabled: (enabled: boolean) => void;
  resetConfig: () => void;
  applyPreset: (presetName: string) => void;
}

const DEFAULT_INTRO_CONFIG: IntroConfig = {
  enabled: false,
  duration: 2,
  title: '',
  badgeText: '',
  backgroundBlur: 15,
  titleFont: 'Montserrat',
  titleSize: 72,
  titleColor: '#FFFFFF',
  badgeColor: '#00FF88',
  animation: 'fade',
};

export const INTRO_PRESETS: Record<string, Partial<IntroConfig>> = {
  minimal: {
    backgroundBlur: 20,
    titleFont: 'Inter',
    titleSize: 64,
    titleColor: '#FFFFFF',
    badgeColor: '#888888',
    animation: 'fade',
    duration: 2,
  },
  neon: {
    backgroundBlur: 15,
    titleFont: 'Space Grotesk',
    titleSize: 72,
    titleColor: '#00FFFF',
    badgeColor: '#FF00FF',
    animation: 'swoosh',
    duration: 2.5,
  },
  gaming: {
    backgroundBlur: 10,
    titleFont: 'Montserrat',
    titleSize: 80,
    titleColor: '#00FF88',
    badgeColor: '#FF0080',
    animation: 'zoom',
    duration: 2,
  },
  elegant: {
    backgroundBlur: 25,
    titleFont: 'Playfair Display',
    titleSize: 60,
    titleColor: '#FFD700',
    badgeColor: '#FFFFFF',
    animation: 'swoosh',
    duration: 3,
  },
};

export const useIntroStore = create<IntroState>((set) => ({
  config: DEFAULT_INTRO_CONFIG,
  
  setConfig: (updates) => set((state) => ({
    config: { ...state.config, ...updates },
  })),
  
  setEnabled: (enabled) => set((state) => ({
    config: { ...state.config, enabled },
  })),
  
  resetConfig: () => set({ config: DEFAULT_INTRO_CONFIG }),
  
  applyPreset: (presetName) => set((state) => {
    const preset = INTRO_PRESETS[presetName];
    if (preset) {
      return { config: { ...state.config, ...preset, enabled: true } };
    }
    return state;
  }),
}));
