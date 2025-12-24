import { useJobsStore, useUIStore } from '@/store';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronUp, Layers } from 'lucide-react';

export default function StatusBar() {
  const { jobs } = useJobsStore();
  const { setJobDrawerOpen } = useUIStore();
  const activeJobs = jobs.filter((j) => j.status === 'running');
  const totalJobs = jobs.length;

  return (
    <footer className="h-7 bg-[var(--bg-card)] border-t border-[var(--border-color)] flex items-center px-4 text-2xs text-[var(--text-muted)]">
      {/* Active jobs - clickable to open drawer */}
      <button
        onClick={() => setJobDrawerOpen(true)}
        className="flex items-center gap-3 hover:text-[var(--text-primary)] transition-colors group"
      >
        <AnimatePresence mode="popLayout">
          {activeJobs.length > 0 ? (
            activeJobs.slice(0, 2).map((job) => (
              <motion.div
                key={job.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-2"
              >
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span className="max-w-[150px] truncate">{job.stage || job.type}</span>
                <span className="text-[var(--text-primary)] font-medium tabular-nums">
                  {job.progress.toFixed(0)}%
                </span>
              </motion.div>
            ))
          ) : (
            <motion.span
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="flex items-center gap-1.5"
            >
              <div className="w-2 h-2 rounded-full bg-green-500" />
              Prêt
            </motion.span>
          )}
        </AnimatePresence>

        {activeJobs.length > 2 && (
          <span className="text-[var(--text-muted)]">
            +{activeJobs.length - 2} autres
          </span>
        )}

        {/* Show drawer hint */}
        <ChevronUp className="w-3 h-3 text-[var(--text-muted)] opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>

      {/* Spacer */}
      <div className="flex-1" />

      {/* Job count badge */}
      {totalJobs > 0 && (
        <button
          onClick={() => setJobDrawerOpen(true)}
          className="flex items-center gap-1.5 px-2 py-0.5 rounded hover:bg-[var(--bg-tertiary)] transition-colors mr-3"
        >
          <Layers className="w-3 h-3" />
          <span>{totalJobs} tâche{totalJobs > 1 ? 's' : ''}</span>
        </button>
      )}

      {/* Version */}
      <span className="opacity-50">FORGE LAB v1.0.0</span>
    </footer>
  );
}


