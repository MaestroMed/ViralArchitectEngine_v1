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
interface LayoutZone {
  id: string;
  type: 'facecam' | 'content' | 'custom';
  x: number;
  y: number;
  width: number;
  height: number;
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
    { id: 'facecam', type: 'facecam', x: 0, y: 0, width: 100, height: 35 },
    { id: 'content', type: 'content', x: 0, y: 35, width: 100, height: 65 },
  ],
  'facecam-bottom': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 65 },
    { id: 'facecam', type: 'facecam', x: 0, y: 65, width: 100, height: 35 },
  ],
  'split-50-50': [
    { id: 'facecam', type: 'facecam', x: 0, y: 0, width: 100, height: 50 },
    { id: 'content', type: 'content', x: 0, y: 50, width: 100, height: 50 },
  ],
  'pip-corner': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 100 },
    { id: 'facecam', type: 'facecam', x: 65, y: 5, width: 30, height: 25 },
  ],
  'content-only': [
    { id: 'content', type: 'content', x: 0, y: 0, width: 100, height: 100 },
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
  animation: 'none' | 'fade' | 'pop' | 'bounce' | 'typewriter';
  highlightColor: string;
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
  },
  'karaoke': {
    fontFamily: 'Inter',
    fontSize: 52,
    fontWeight: 800,
    color: '#FFFFFF',
    backgroundColor: 'transparent',
    outlineColor: '#000000',
    outlineWidth: 3,
    position: 'bottom',
    animation: 'typewriter',
    highlightColor: '#00BFFF',
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
        if (prevJob?.status === 'running' && job.status === 'completed') {
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
        } else if (prevJob?.status === 'running' && job.status === 'failed') {
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
