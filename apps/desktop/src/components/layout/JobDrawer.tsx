import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, XCircle, Clock, Loader2, RefreshCw, Trash2, ExternalLink, Cpu, Zap, ChevronDown, ChevronUp, FolderOpen, AlertTriangle } from 'lucide-react';
import { useJobsStore, useUIStore, useToastStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { Progress } from '@/components/ui/Progress';

interface JobDetails {
  id: string;
  projectName?: string;
  device?: string;
  startedAt?: string;
  elapsedTime?: string;
}

export default function JobDrawer() {
  const navigate = useNavigate();
  const { jobDrawerOpen, setJobDrawerOpen } = useUIStore();
  const [expandedJobId, setExpandedJobId] = useState<string | null>(null);
  const [jobDetails, setJobDetails] = useState<Record<string, JobDetails>>({});
  const [deviceInfo, setDeviceInfo] = useState<{ device: string; gpu?: string } | null>(null);
  
  // Get all jobs from store
  const jobs = useJobsStore(useShallow((state) => [...state.jobs]));
  const { removeJob } = useJobsStore();
  
  // Fetch device info on mount
  useEffect(() => {
    const fetchDeviceInfo = async () => {
      try {
        const caps = await api.request<{ whisper: { device: string }; gpu: { name?: string } }>('/capabilities');
        setDeviceInfo({
          device: caps.whisper?.device || 'unknown',
          gpu: caps.gpu?.name,
        });
      } catch (e) {
        console.error('Failed to fetch capabilities:', e);
      }
    };
    fetchDeviceInfo();
  }, []);
  
  // Fetch project details for expanded job
  useEffect(() => {
    const fetchJobDetails = async (jobId: string, projectId?: string) => {
      if (!projectId || jobDetails[jobId]) return;
      
      try {
        const project = await api.getProject(projectId);
        const projectData = project.data;
        if (projectData) {
          setJobDetails(prev => ({
            ...prev,
            [jobId]: {
              id: jobId,
              projectName: projectData.name,
            }
          }));
        }
      } catch (e) {
        console.error('Failed to fetch project:', e);
      }
    };
    
    if (expandedJobId) {
      const job = jobs.find(j => j.id === expandedJobId);
      if (job?.projectId) {
        fetchJobDetails(expandedJobId, job.projectId);
      }
    }
  }, [expandedJobId, jobs, jobDetails]);

  // Auto-clear completed jobs after 2 minutes
  useEffect(() => {
    const interval = setInterval(() => {
      jobs.forEach((job) => {
        if (job.status === 'completed') {
          // Remove completed jobs after 2 minutes (120000ms)
          // Note: We don't have completedAt, so we remove after a fixed delay
          removeJob(job.id);
        }
      });
    }, 120000); // Check every 2 minutes
    
    return () => clearInterval(interval);
  }, [jobs, removeJob]);

  // Separate active and completed jobs
  const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending');
  const completedJobs = jobs.filter((j) => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled');

  const { addToast } = useToastStore();

  const handleCancel = async (jobId: string) => {
    try {
      await api.cancelJob(jobId);
      addToast({ type: 'info', title: 'Job annulé', message: 'La tâche a été annulée' });
    } catch (e) {
      console.error('Failed to cancel job:', e);
      addToast({ type: 'error', title: 'Erreur', message: 'Impossible d\'annuler le job' });
    }
  };

  const handleRetry = async (jobId: string) => {
    try {
      const response = await api.request<{ success: boolean; error?: string }>(`/jobs/${jobId}/retry`, { method: 'POST' });
      if (response.success) {
        addToast({ type: 'success', title: 'Relance', message: 'La tâche a été relancée' });
      } else {
        throw new Error(response.error || 'Échec de la relance');
      }
    } catch (e) {
      console.error('Failed to retry job:', e);
      addToast({ type: 'error', title: 'Erreur', message: 'Impossible de relancer le job' });
    }
  };

  const handleOpenFolder = async (projectId: string) => {
    try {
      const project = await api.getProject(projectId);
      const sourcePath = project.data?.sourcePath;
      if (sourcePath) {
        // Derive project directory from sourcePath (drop the filename)
        const projectDir = sourcePath.replace(/[\\/][^\\/]+$/, '');
        // Open exports folder
        const exportsPath = `${projectDir}\\exports`;
        window.forge?.openPath?.(exportsPath) || window.forge?.openPath?.(projectDir);
      }
    } catch (e) {
      console.error('Failed to open folder:', e);
    }
  };

  const handleClearCompleted = () => {
    completedJobs.forEach((job) => removeJob(job.id));
  };

  const jobTypeLabels: Record<string, string> = {
    download: 'Téléchargement',
    ingest: 'Ingestion',
    analyze: 'Analyse',
    export: 'Export',
    render_proxy: 'Proxy',
    render_final: 'Rendu final',
    generate_variants: 'Variantes',
  };

  const statusIcons: Record<string, React.ReactNode> = {
    running: <Loader2 className="w-4 h-4 animate-spin text-blue-400" />,
    pending: <Clock className="w-4 h-4 text-gray-400" />,
    completed: <CheckCircle className="w-4 h-4 text-green-400" />,
    failed: <XCircle className="w-4 h-4 text-red-400" />,
    cancelled: <X className="w-4 h-4 text-gray-400" />,
  };

  return (
    <AnimatePresence>
      {jobDrawerOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/40 z-40"
            onClick={() => setJobDrawerOpen(false)}
          />

          {/* Drawer */}
          <motion.div
            role="dialog"
            aria-modal="true"
            aria-labelledby="job-drawer-title"
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed bottom-0 left-0 right-0 z-50 glass border-t border-[var(--glass-border)] rounded-t-2xl shadow-2xl max-h-[60vh] overflow-hidden flex flex-col"
          >
            {/* Handle bar */}
            <div className="flex items-center justify-center py-2">
              <div aria-hidden="true" className="w-10 h-1 bg-[var(--text-muted)] rounded-full opacity-50" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-3">
                <h3 id="job-drawer-title" className="font-semibold text-[var(--text-primary)]">Tâches</h3>
                {activeJobs.length > 0 && (
                  <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs font-medium rounded-full">
                    {activeJobs.length} en cours
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {completedJobs.length > 0 && (
                  <button
                    onClick={handleClearCompleted}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
                  >
                    <Trash2 aria-hidden="true" className="w-3 h-3" />
                    Effacer l'historique
                  </button>
                )}
                <button
                  onClick={() => setJobDrawerOpen(false)}
                  aria-label="Fermer les tâches"
                  className="p-2 hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
                >
                  <X aria-hidden="true" className="w-4 h-4 text-[var(--text-muted)]" />
                </button>
              </div>
            </div>

            {/* Job list */}
            <div className="flex-1 overflow-auto p-4 space-y-2">
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Clock aria-hidden="true" className="w-12 h-12 text-[var(--text-muted)] opacity-30 mb-3" />
                  <p className="text-sm text-[var(--text-muted)]">Aucune tâche</p>
                </div>
              ) : (
                <>
                  {/* Active jobs first */}
                  {activeJobs.map((job) => (
                    <motion.div
                      key={job.id}
                      layout
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="bg-[var(--bg-secondary)] rounded-lg overflow-hidden"
                    >
                      {/* Main job row - clickable */}
                      <div
                        role="button"
                        tabIndex={0}
                        aria-expanded={expandedJobId === job.id}
                        aria-label={`${jobTypeLabels[job.type] || job.type} — ${job.progress.toFixed(0)}%`}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault();
                            setExpandedJobId(expandedJobId === job.id ? null : job.id);
                          }
                        }}
                        className="p-4 cursor-pointer hover:bg-[var(--bg-tertiary)] transition-colors"
                        onClick={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
                      >
                        <div className="flex items-center gap-3 mb-2">
                          {statusIcons[job.status]}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-[var(--text-primary)]">
                                {jobTypeLabels[job.type] || job.type}
                              </span>
                              <span className="text-xs text-[var(--text-muted)]">
                                {job.stage}
                              </span>
                              {/* Device indicator */}
                              {job.type === 'analyze' && deviceInfo && (
                                <span className={`flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                  deviceInfo.device === 'cuda' 
                                    ? 'bg-green-500/20 text-green-400' 
                                    : 'bg-amber-500/20 text-amber-400'
                                }`}>
                                  {deviceInfo.device === 'cuda' ? (
                                    <><Zap className="w-3 h-3" /> GPU</>
                                  ) : (
                                    <><Cpu className="w-3 h-3" /> CPU</>
                                  )}
                                </span>
                              )}
                            </div>
                            {job.message && (
                              <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                                {job.message}
                              </p>
                            )}
                          </div>
                          <span className="text-sm font-bold text-[var(--text-primary)] tabular-nums">
                            {job.progress.toFixed(0)}%
                          </span>
                          {expandedJobId === job.id ? (
                            <ChevronUp aria-hidden="true" className="w-4 h-4 text-[var(--text-muted)]" />
                          ) : (
                            <ChevronDown aria-hidden="true" className="w-4 h-4 text-[var(--text-muted)]" />
                          )}
                          <button
                            onClick={(e) => { 
                              e.stopPropagation(); 
                              // If job is at 100%, just remove it silently instead of "cancelling"
                              if (job.progress >= 100) {
                                removeJob(job.id);
                              } else {
                                handleCancel(job.id);
                              }
                            }}
                            className="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors"
                            title={job.progress >= 100 ? "Retirer" : "Annuler"}
                            aria-label={job.progress >= 100 ? 'Retirer la tâche' : 'Annuler la tâche'}
                          >
                            <X aria-hidden="true" className="w-4 h-4 text-[var(--text-muted)]" />
                          </button>
                        </div>
                        <Progress value={job.progress} label="Progression de la tâche" />
                      </div>
                      
                      {/* Expanded details */}
                      <AnimatePresence>
                        {expandedJobId === job.id && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="border-t border-[var(--border-color)] bg-[var(--bg-primary)]"
                          >
                            <div className="p-4 space-y-3 text-sm">
                              <div className="grid grid-cols-2 gap-4">
                                <div>
                                  <span className="text-[var(--text-muted)] text-xs">ID Job</span>
                                  <p className="font-mono text-xs text-[var(--text-secondary)]">{job.id}</p>
                                </div>
                                <div>
                                  <span className="text-[var(--text-muted)] text-xs">Projet</span>
                                  <p className="text-[var(--text-secondary)] truncate">
                                    {jobDetails[job.id]?.projectName || job.projectId?.slice(0, 8) || 'N/A'}
                                  </p>
                                </div>
                                {job.type === 'analyze' && deviceInfo && (
                                  <>
                                    <div>
                                      <span className="text-[var(--text-muted)] text-xs">Device</span>
                                      <p className={`font-medium ${
                                        deviceInfo.device === 'cuda' ? 'text-green-400' : 'text-amber-400'
                                      }`}>
                                        {deviceInfo.device === 'cuda' ? 'GPU (CUDA)' : 'CPU'}
                                      </p>
                                    </div>
                                    {deviceInfo.gpu && (
                                      <div>
                                        <span className="text-[var(--text-muted)] text-xs">GPU</span>
                                        <p className="text-[var(--text-secondary)] truncate">{deviceInfo.gpu}</p>
                                      </div>
                                    )}
                                  </>
                                )}
                                <div>
                                  <span className="text-[var(--text-muted)] text-xs">Étape</span>
                                  <p className="text-[var(--text-secondary)]">{job.stage || 'N/A'}</p>
                                </div>
                                <div>
                                  <span className="text-[var(--text-muted)] text-xs">Progression</span>
                                  <p className="text-[var(--text-secondary)]">{job.progress.toFixed(1)}%</p>
                                </div>
                              </div>
                              
                              {/* Actions */}
                              <div className="flex gap-2 pt-2 border-t border-[var(--border-color)]">
                                {job.projectId && (
                                  <button
                                    onClick={() => {
                                      setJobDrawerOpen(false);
                                      navigate(`/project/${job.projectId}`);
                                    }}
                                    className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[var(--accent-color)] text-white rounded-lg hover:opacity-90 transition-opacity"
                                  >
                                    <ExternalLink className="w-3 h-3" />
                                    Voir le projet
                                  </button>
                                )}
                                <button
                                  onClick={() => handleCancel(job.id)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-red-400 bg-red-500/10 rounded-lg hover:bg-red-500/20 transition-colors"
                                >
                                  <X className="w-3 h-3" />
                                  Annuler
                                </button>
                              </div>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  ))}

                  {/* Completed jobs */}
                  {completedJobs.length > 0 && (
                    <div className="mt-4">
                      <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2 px-1">
                        Historique
                      </p>
                      {completedJobs.slice(0, 10).map((job) => (
                        <motion.div
                          key={job.id}
                          layout
                          className="rounded-lg overflow-hidden"
                        >
                          <div
                            role="button"
                            tabIndex={0}
                            aria-expanded={expandedJobId === job.id}
                            aria-label={`${jobTypeLabels[job.type] || job.type} — ${job.status}`}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' || e.key === ' ') {
                                e.preventDefault();
                                setExpandedJobId(expandedJobId === job.id ? null : job.id);
                              }
                            }}
                            className="flex items-center gap-3 p-3 cursor-pointer hover:bg-[var(--bg-secondary)] transition-colors"
                            onClick={() => setExpandedJobId(expandedJobId === job.id ? null : job.id)}
                          >
                            {statusIcons[job.status]}
                            <div className="flex-1 min-w-0">
                              <span className="text-sm text-[var(--text-secondary)]">
                                {jobTypeLabels[job.type] || job.type}
                              </span>
                            </div>
                            {job.error && (
                              <span className="text-xs text-red-400 truncate max-w-[200px]">
                                {job.error.slice(0, 50)}...
                              </span>
                            )}
                            {expandedJobId === job.id ? (
                              <ChevronUp aria-hidden="true" className="w-3 h-3 text-[var(--text-muted)]" />
                            ) : (
                              <ChevronDown aria-hidden="true" className="w-3 h-3 text-[var(--text-muted)]" />
                            )}
                            <button
                              onClick={(e) => { e.stopPropagation(); removeJob(job.id); }}
                              aria-label="Supprimer cette tâche de l'historique"
                              className="p-1 opacity-50 hover:opacity-100 hover:bg-[var(--bg-tertiary)] rounded transition-all"
                            >
                              <X aria-hidden="true" className="w-3 h-3 text-[var(--text-muted)]" />
                            </button>
                          </div>
                          
                          {/* Expanded error details */}
                          <AnimatePresence>
                            {expandedJobId === job.id && (
                              <motion.div
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                className="bg-[var(--bg-secondary)] border-t border-[var(--border-color)]"
                              >
                                <div className="p-3 space-y-2 text-sm">
                                  <div>
                                    <span className="text-[var(--text-muted)] text-xs">ID</span>
                                    <p className="font-mono text-[10px] text-[var(--text-secondary)]">{job.id}</p>
                                  </div>
                                  {job.error && (
                                    <div>
                                      <span className="text-[var(--text-muted)] text-xs flex items-center gap-1">
                                        <AlertTriangle className="w-3 h-3 text-red-400" />
                                        Erreur
                                      </span>
                                      <p className="text-xs text-red-400 bg-red-500/10 p-2 rounded mt-1 break-all">
                                        {job.error}
                                      </p>
                                    </div>
                                  )}
                                  {/* Actions for completed/failed jobs */}
                                  <div className="flex flex-wrap gap-2 pt-2">
                                    {/* Retry button for failed/cancelled */}
                                    {(job.status === 'failed' || job.status === 'cancelled') && (
                                      <button
                                        onClick={() => handleRetry(job.id)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-green-500/20 text-green-400 rounded-lg hover:bg-green-500/30 transition-colors"
                                      >
                                        <RefreshCw className="w-3 h-3" />
                                        Relancer
                                      </button>
                                    )}
                                    {/* Open folder for completed exports */}
                                    {job.status === 'completed' && job.type === 'export' && job.projectId && (
                                      <button
                                        onClick={() => handleOpenFolder(job.projectId!)}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-blue-500/20 text-blue-400 rounded-lg hover:bg-blue-500/30 transition-colors"
                                      >
                                        <FolderOpen className="w-3 h-3" />
                                        Ouvrir le dossier
                                      </button>
                                    )}
                                    {job.projectId && (
                                      <button
                                        onClick={() => {
                                          setJobDrawerOpen(false);
                                          navigate(`/project/${job.projectId}`);
                                        }}
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-[var(--bg-tertiary)] text-[var(--text-secondary)] rounded-lg hover:bg-[var(--bg-primary)] transition-colors"
                                      >
                                        <ExternalLink className="w-3 h-3" />
                                        Voir le projet
                                      </button>
                                    )}
                                  </div>
                                </div>
                              </motion.div>
                            )}
                          </AnimatePresence>
                        </motion.div>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}

