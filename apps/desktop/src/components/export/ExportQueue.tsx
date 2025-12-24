import { motion, AnimatePresence } from 'framer-motion';
import { 
  Download, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Loader2, 
  Folder, 
  Play,
  Trash2,
  X,
  FileVideo,
  ExternalLink,
} from 'lucide-react';
import { useJobsStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import { Progress } from '@/components/ui/Progress';
import { Button } from '@/components/ui/Button';
import { formatDuration } from '@/lib/utils';

interface ExportQueueProps {
  projectId?: string;
}

export default function ExportQueue({ projectId }: ExportQueueProps) {
  // Get export jobs from store
  const exportJobs = useJobsStore(
    useShallow((state) => {
      const jobs = state.jobs.filter((j) => j.type === 'export');
      if (projectId) {
        return jobs.filter((j) => j.projectId === projectId);
      }
      return jobs;
    })
  );
  const { removeJob } = useJobsStore();

  // Separate by status
  const pendingJobs = exportJobs.filter((j) => j.status === 'pending');
  const runningJobs = exportJobs.filter((j) => j.status === 'running');
  const completedJobs = exportJobs.filter((j) => j.status === 'completed');
  const failedJobs = exportJobs.filter((j) => j.status === 'failed');

  const hasJobs = exportJobs.length > 0;

  const handleOpenFolder = (outputPath?: string) => {
    if (outputPath && window.electron) {
      // Open folder in file explorer
      window.electron.shell.showItemInFolder(outputPath);
    }
  };

  const handlePlayVideo = (outputPath?: string) => {
    if (outputPath && window.electron) {
      // Open video with default player
      window.electron.shell.openPath(outputPath);
    }
  };

  const handleClearCompleted = () => {
    [...completedJobs, ...failedJobs].forEach((job) => removeJob(job.id));
  };

  const statusIcons: Record<string, React.ReactNode> = {
    running: <Loader2 className="w-5 h-5 animate-spin text-blue-400" />,
    pending: <Clock className="w-5 h-5 text-gray-400" />,
    completed: <CheckCircle className="w-5 h-5 text-green-400" />,
    failed: <XCircle className="w-5 h-5 text-red-400" />,
  };

  return (
    <div className="h-full flex flex-col bg-[var(--bg-secondary)]">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-viral flex items-center justify-center">
            <Download className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-[var(--text-primary)] font-display">
              File d'export
            </h2>
            <p className="text-xs text-[var(--text-muted)]">
              {runningJobs.length > 0
                ? `${runningJobs.length} en cours`
                : pendingJobs.length > 0
                ? `${pendingJobs.length} en attente`
                : completedJobs.length > 0
                ? `${completedJobs.length} terminé${completedJobs.length > 1 ? 's' : ''}`
                : 'Aucun export'}
            </p>
          </div>
        </div>

        {(completedJobs.length > 0 || failedJobs.length > 0) && (
          <Button variant="ghost" size="sm" onClick={handleClearCompleted}>
            <Trash2 className="w-4 h-4 mr-2" />
            Effacer l'historique
          </Button>
        )}
      </div>

      {/* Queue content */}
      <div className="flex-1 overflow-auto p-4">
        {!hasJobs ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <FileVideo className="w-16 h-16 text-[var(--text-muted)] opacity-20 mb-4" />
            <p className="text-[var(--text-muted)]">Aucun export en cours</p>
            <p className="text-sm text-[var(--text-muted)] mt-1 opacity-70">
              Sélectionnez un segment et cliquez sur Exporter
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {/* Running jobs first */}
            <AnimatePresence>
              {runningJobs.map((job) => (
                <motion.div
                  key={job.id}
                  layout
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.95 }}
                  className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl p-4"
                >
                  <div className="flex items-center gap-4 mb-3">
                    {statusIcons[job.status]}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-[var(--text-primary)] truncate">
                          {job.stage || 'Export en cours...'}
                        </span>
                        <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded-full">
                          En cours
                        </span>
                      </div>
                      {job.message && (
                        <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                          {job.message}
                        </p>
                      )}
                    </div>
                    <span className="text-lg font-bold text-[var(--text-primary)] tabular-nums font-mono">
                      {job.progress.toFixed(0)}%
                    </span>
                  </div>
                  <Progress value={job.progress} className="h-2" />
                </motion.div>
              ))}
            </AnimatePresence>

            {/* Pending jobs */}
            {pendingJobs.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2 px-1">
                  En attente ({pendingJobs.length})
                </p>
                {pendingJobs.map((job) => (
                  <motion.div
                    key={job.id}
                    layout
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
                  >
                    {statusIcons[job.status]}
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-[var(--text-secondary)]">
                        {job.stage || 'En attente...'}
                      </span>
                    </div>
                    <button
                      onClick={() => removeJob(job.id)}
                      className="p-1.5 hover:bg-[var(--bg-secondary)] rounded-lg opacity-50 hover:opacity-100 transition-opacity"
                    >
                      <X className="w-4 h-4 text-[var(--text-muted)]" />
                    </button>
                  </motion.div>
                ))}
              </div>
            )}

            {/* Completed jobs */}
            {completedJobs.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-[var(--text-muted)] uppercase tracking-wider mb-2 px-1">
                  Terminés ({completedJobs.length})
                </p>
                {completedJobs.map((job) => (
                  <motion.div
                    key={job.id}
                    layout
                    className="flex items-center gap-3 p-3 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors group"
                  >
                    {statusIcons[job.status]}
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-[var(--text-primary)]">
                        {job.stage || 'Export terminé'}
                      </span>
                      {job.outputPath && (
                        <p className="text-xs text-[var(--text-muted)] truncate mt-0.5">
                          {job.outputPath}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <button
                        onClick={() => handlePlayVideo(job.outputPath)}
                        className="p-2 hover:bg-[var(--bg-secondary)] rounded-lg"
                        title="Lire"
                      >
                        <Play className="w-4 h-4 text-[var(--text-muted)]" />
                      </button>
                      <button
                        onClick={() => handleOpenFolder(job.outputPath)}
                        className="p-2 hover:bg-[var(--bg-secondary)] rounded-lg"
                        title="Ouvrir le dossier"
                      >
                        <Folder className="w-4 h-4 text-[var(--text-muted)]" />
                      </button>
                      <button
                        onClick={() => removeJob(job.id)}
                        className="p-2 hover:bg-[var(--bg-secondary)] rounded-lg"
                        title="Supprimer"
                      >
                        <X className="w-4 h-4 text-[var(--text-muted)]" />
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}

            {/* Failed jobs */}
            {failedJobs.length > 0 && (
              <div className="mt-4">
                <p className="text-xs text-red-400 uppercase tracking-wider mb-2 px-1">
                  Échecs ({failedJobs.length})
                </p>
                {failedJobs.map((job) => (
                  <motion.div
                    key={job.id}
                    layout
                    className="flex items-center gap-3 p-3 rounded-lg bg-red-500/5 border border-red-500/20"
                  >
                    {statusIcons[job.status]}
                    <div className="flex-1 min-w-0">
                      <span className="text-sm text-red-400">
                        Export échoué
                      </span>
                      {job.error && (
                        <p className="text-xs text-red-400/70 truncate mt-0.5">
                          {job.error}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => removeJob(job.id)}
                      className="p-2 hover:bg-red-500/10 rounded-lg"
                    >
                      <X className="w-4 h-4 text-red-400" />
                    </button>
                  </motion.div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
