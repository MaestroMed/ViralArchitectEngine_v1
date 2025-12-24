import { motion, AnimatePresence } from 'framer-motion';
import { X, CheckCircle, XCircle, Clock, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { useJobsStore, useUIStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import { api } from '@/lib/api';
import { Progress } from '@/components/ui/Progress';

export default function JobDrawer() {
  const { jobDrawerOpen, setJobDrawerOpen } = useUIStore();
  
  // Get all jobs from store
  const jobs = useJobsStore(useShallow((state) => [...state.jobs]));
  const { removeJob } = useJobsStore();

  // Separate active and completed jobs
  const activeJobs = jobs.filter((j) => j.status === 'running' || j.status === 'pending');
  const completedJobs = jobs.filter((j) => j.status === 'completed' || j.status === 'failed' || j.status === 'cancelled');

  const handleCancel = async (jobId: string) => {
    try {
      await api.cancelJob(jobId);
    } catch (e) {
      console.error('Failed to cancel job:', e);
    }
  };

  const handleClearCompleted = () => {
    completedJobs.forEach((job) => removeJob(job.id));
  };

  const jobTypeLabels: Record<string, string> = {
    ingest: 'Ingestion',
    analyze: 'Analyse',
    export: 'Export',
    render_proxy: 'Proxy',
    render_final: 'Rendu final',
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
            initial={{ y: '100%' }}
            animate={{ y: 0 }}
            exit={{ y: '100%' }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
            className="fixed bottom-0 left-0 right-0 z-50 glass border-t border-[var(--glass-border)] rounded-t-2xl shadow-2xl max-h-[60vh] overflow-hidden flex flex-col"
          >
            {/* Handle bar */}
            <div className="flex items-center justify-center py-2">
              <div className="w-10 h-1 bg-[var(--text-muted)] rounded-full opacity-50" />
            </div>

            {/* Header */}
            <div className="flex items-center justify-between px-6 py-3 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-3">
                <h3 className="font-semibold text-[var(--text-primary)]">Tâches</h3>
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
                    <Trash2 className="w-3 h-3" />
                    Effacer l'historique
                  </button>
                )}
                <button
                  onClick={() => setJobDrawerOpen(false)}
                  className="p-2 hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
                >
                  <X className="w-4 h-4 text-[var(--text-muted)]" />
                </button>
              </div>
            </div>

            {/* Job list */}
            <div className="flex-1 overflow-auto p-4 space-y-2">
              {jobs.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-center">
                  <Clock className="w-12 h-12 text-[var(--text-muted)] opacity-30 mb-3" />
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
                      className="bg-[var(--bg-secondary)] rounded-lg p-4"
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
                        <button
                          onClick={() => handleCancel(job.id)}
                          className="p-1.5 hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
                          title="Annuler"
                        >
                          <X className="w-4 h-4 text-[var(--text-muted)]" />
                        </button>
                      </div>
                      <Progress value={job.progress} />
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
                          className="flex items-center gap-3 p-3 rounded-lg hover:bg-[var(--bg-secondary)] transition-colors"
                        >
                          {statusIcons[job.status]}
                          <div className="flex-1 min-w-0">
                            <span className="text-sm text-[var(--text-secondary)]">
                              {jobTypeLabels[job.type] || job.type}
                            </span>
                          </div>
                          {job.error && (
                            <span className="text-xs text-red-400 truncate max-w-[200px]">
                              {job.error}
                            </span>
                          )}
                          <button
                            onClick={() => removeJob(job.id)}
                            className="p-1 opacity-0 hover:opacity-100 hover:bg-[var(--bg-tertiary)] rounded transition-all"
                          >
                            <X className="w-3 h-3 text-[var(--text-muted)]" />
                          </button>
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

