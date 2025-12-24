import { useState, useEffect, useCallback, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { ArrowLeft, Upload, Search, Sparkles, Download } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { useJobsStore, useToastStore, useUIStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import IngestPanel from '@/components/project/IngestPanel';
import AnalyzePanel from '@/components/project/AnalyzePanel';
import ForgePanel from '@/components/project/ForgePanel';
import ExportPanel from '@/components/project/ExportPanel';
import ProgressOverlay from '@/components/project/ProgressOverlay';

interface Project {
  id: string;
  name: string;
  sourceFilename: string;
  sourcePath: string;
  duration?: number;
  resolution?: { width: number; height: number };
  fps?: number;
  audioTracks: number;
  proxyPath?: string;
  audioPath?: string;
  status: string;
  createdAt: string;
  updatedAt: string;
}

const panels = [
  { id: 'ingest', label: 'Ingest', icon: Upload },
  { id: 'analyze', label: 'Analyze', icon: Search },
  { id: 'forge', label: 'Forge', icon: Sparkles },
  { id: 'export', label: 'Export', icon: Download },
];

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { currentPanel, setCurrentPanel } = useUIStore();
  const { addToast } = useToastStore();
  const { addJob } = useJobsStore();
  const previousJobStatusRef = useRef<Record<string, string>>({});

  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  // Get active jobs for this project from the WebSocket-synced store
  const projectJobs = useJobsStore(
    useShallow((state) => 
      state.jobs.filter((j) => j.projectId === id)
    )
  );

  // Watch for job completion via WebSocket (no polling needed)
  useEffect(() => {
    projectJobs.forEach((job) => {
      const prevStatus = previousJobStatusRef.current[job.id];
      
      // Job just completed
      if (prevStatus === 'running' && job.status === 'completed') {
        loadProject();
        
        // Auto-advance to next panel
        if (job.type === 'ingest') {
          setCurrentPanel('analyze');
        } else if (job.type === 'analyze') {
          setCurrentPanel('forge');
        }
      }
      
      previousJobStatusRef.current[job.id] = job.status;
    });
  }, [projectJobs]);

  const loadProject = useCallback(async () => {
    if (!id) return;
    
    try {
      const response = await api.getProject(id);
      setProject(response.data);
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Impossible de charger le projet',
      });
      navigate('/');
    } finally {
      setLoading(false);
    }
  }, [id, addToast, navigate]);

  useEffect(() => {
    loadProject();
  }, [loadProject]);

  // Determine which panels are available based on project status
  const getPanelStatus = (panelId: string): 'locked' | 'available' | 'active' | 'complete' => {
    if (!project) return 'locked';

    const statusMap: Record<string, string[]> = {
      created: ['ingest'],
      ingesting: ['ingest'],
      ingested: ['ingest', 'analyze'],
      analyzing: ['ingest', 'analyze'],
      analyzed: ['ingest', 'analyze', 'forge', 'export'],
      ready: ['ingest', 'analyze', 'forge', 'export'],
    };

    const available = statusMap[project.status] || ['ingest'];
    
    if (!available.includes(panelId)) return 'locked';
    if (panelId === currentPanel) return 'active';
    
    // Check completion
    if (panelId === 'ingest' && ['ingested', 'analyzed', 'ready'].includes(project.status)) {
      return 'complete';
    }
    if (panelId === 'analyze' && ['analyzed', 'ready'].includes(project.status)) {
      return 'complete';
    }

    return 'available';
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-[var(--text-primary)] border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!project) {
    return null;
  }

  // Check if there's an active job for this project
  const hasActiveJob = projectJobs.some((j) => j.status === 'running');

  return (
    <div className="h-full flex flex-col">
      {/* Progress Overlay for active jobs */}
      {hasActiveJob && <ProgressOverlay projectId={id!} />}

      {/* Header */}
      <header className="px-6 py-4 border-b border-[var(--border-color)] bg-[var(--bg-card)] flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => navigate('/')}>
          <ArrowLeft className="w-4 h-4" />
        </Button>

        <div className="flex-1 min-w-0">
          <h1 className="text-lg font-semibold text-[var(--text-primary)] truncate">
            {project.name}
          </h1>
          <p className="text-xs text-[var(--text-muted)] truncate">
            {project.sourceFilename}
          </p>
        </div>

        {/* Panel tabs - Door navigation */}
        <nav className="flex items-center bg-[var(--bg-tertiary)] rounded-lg p-1">
          {panels.map((panel) => {
            const status = getPanelStatus(panel.id);
            const Icon = panel.icon;

            return (
              <button
                key={panel.id}
                onClick={() => status !== 'locked' && setCurrentPanel(panel.id as any)}
                disabled={status === 'locked'}
                className={`
                  relative px-4 py-2 rounded-md text-sm font-medium transition-all
                  flex items-center gap-2
                  ${status === 'active' 
                    ? 'bg-[var(--bg-card)] text-[var(--text-primary)] shadow-sm' 
                    : status === 'locked'
                    ? 'text-[var(--text-muted)] opacity-50 cursor-not-allowed'
                    : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                  }
                `}
              >
                <Icon className="w-4 h-4" />
                <span>{panel.label}</span>
                
                {status === 'complete' && (
                  <div className="w-1.5 h-1.5 rounded-full bg-viral-high" />
                )}
              </button>
            );
          })}
        </nav>
      </header>

      {/* Panel content with door animation */}
      <div className="flex-1 overflow-hidden relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentPanel}
            initial={{ opacity: 0, x: 50 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -50 }}
            transition={{ duration: 0.3, ease: 'easeInOut' }}
            className="h-full"
          >
            {currentPanel === 'ingest' && (
              <IngestPanel
                project={project}
                onJobStart={(jobId) => {
                  // Add job to store - WebSocket will update progress
                  addJob({
                    id: jobId,
                    type: 'ingest',
                    projectId: project.id,
                    status: 'running',
                    progress: 0,
                  });
                }}
                onComplete={() => {
                  loadProject();
                  setCurrentPanel('analyze');
                }}
              />
            )}
            {currentPanel === 'analyze' && (
              <AnalyzePanel
                project={project}
                onJobStart={(jobId) => {
                  // Add job to store - WebSocket will update progress
                  addJob({
                    id: jobId,
                    type: 'analyze',
                    projectId: project.id,
                    status: 'running',
                    progress: 0,
                  });
                }}
                onComplete={() => {
                  loadProject();
                  setCurrentPanel('forge');
                }}
              />
            )}
            {currentPanel === 'forge' && (
              <ForgePanel project={project} />
            )}
            {currentPanel === 'export' && (
              <ExportPanel project={project} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
}




