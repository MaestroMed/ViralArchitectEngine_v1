import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Loader2 } from 'lucide-react';
import { useJobsStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';
import { api } from '@/lib/api';

interface ProgressOverlayProps {
  projectId: string;
}

export default function ProgressOverlay({ projectId }: ProgressOverlayProps) {
  const [hidden, setHidden] = useState(false);

  // Get active job for this project
  const activeJob = useJobsStore(
    useShallow((state) => {
      const job = state.jobs.find(
        (j) => j.projectId === projectId && j.status === 'running'
      );
      return job ? { ...job } : null;
    })
  );

  // Reset hidden state when a new job starts
  useEffect(() => {
    if (activeJob) {
      setHidden(false);
    }
  }, [activeJob?.id]);

  // If hidden or no active job, don't render
  if (hidden || !activeJob) return null;

  const progress = activeJob.progress || 0;
  const circumference = 2 * Math.PI * 90; // radius = 90
  const strokeDashoffset = circumference - (progress / 100) * circumference;

  const jobTypeLabels: Record<string, string> = {
    ingest: 'Ingestion',
    analyze: 'Analyse',
    export: 'Export',
    render_proxy: 'Proxy',
    render_final: 'Rendu final',
  };

  const handleCancel = async () => {
    try {
      await api.cancelJob(activeJob.id);
    } catch (e) {
      console.error('Failed to cancel job:', e);
    }
  };

  const handleBackground = () => {
    // Hide overlay - job continues in background, accessible via JobDrawer in footer
    setHidden(true);
  };

  // Full overlay
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
      >
        {/* Backdrop with blur */}
        <div className="absolute inset-0 bg-black/80 backdrop-blur-md" />

        {/* Content */}
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.9, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="relative z-10 flex flex-col items-center"
        >
          {/* Animated Progress Ring */}
          <div
            className="relative w-56 h-56 mb-8"
            role="progressbar"
            aria-label="Progression de la tâche"
            aria-valuenow={Math.floor(progress)}
            aria-valuemin={0}
            aria-valuemax={100}
          >
            {/* Background ring */}
            <svg aria-hidden="true" className="w-full h-full -rotate-90" viewBox="0 0 200 200">
              <circle
                cx="100"
                cy="100"
                r="90"
                fill="none"
                stroke="rgba(255,255,255,0.1)"
                strokeWidth="8"
              />
              {/* Progress ring */}
              <motion.circle
                cx="100"
                cy="100"
                r="90"
                fill="none"
                stroke="url(#progressGradient)"
                strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={circumference}
                initial={{ strokeDashoffset: circumference }}
                animate={{ strokeDashoffset }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
              />
              <defs>
                <linearGradient id="progressGradient" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#10B981" />
                  <stop offset="100%" stopColor="#06B6D4" />
                </linearGradient>
              </defs>
            </svg>

            {/* Center content */}
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <motion.span
                key={Math.floor(progress)}
                initial={{ scale: 1.2, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="text-5xl font-bold text-white tabular-nums"
              >
                {Math.floor(progress)}%
              </motion.span>
              <span className="text-sm text-gray-400 mt-1">
                {jobTypeLabels[activeJob.type] || activeJob.type}
              </span>
            </div>

            {/* Spinning loader overlay */}
            <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <Loader2 className="w-56 h-56 text-white/5 animate-spin" style={{ animationDuration: '3s' }} />
            </div>
          </div>

          {/* Stage label */}
          <motion.div
            key={activeJob.stage}
            role="status"
            aria-live="polite"
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            className="text-center mb-4"
          >
            <h2 className="text-xl font-semibold text-white mb-1">
              {activeJob.stage || 'Traitement en cours...'}
            </h2>
            {activeJob.message && (
              <p className="text-sm text-gray-400 max-w-md">
                {activeJob.message}
              </p>
            )}
          </motion.div>

          {/* ETA estimation */}
          {progress > 5 && progress < 95 && (
            <div className="text-xs text-gray-500 mb-6">
              Estimation basée sur la progression...
            </div>
          )}

          {/* Action buttons */}
          <div className="flex items-center gap-3">
            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleBackground}
              className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-r from-emerald-500/20 to-cyan-500/20 hover:from-emerald-500/30 hover:to-cyan-500/30 border border-emerald-500/30 rounded-lg text-sm text-emerald-300 font-medium transition-all"
            >
              Arrière-plan
            </motion.button>

            <motion.button
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              onClick={handleCancel}
              className="flex items-center gap-2 px-4 py-2.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-lg text-sm text-red-400 transition-colors"
            >
              <X aria-hidden="true" className="w-4 h-4" />
              Annuler
            </motion.button>
          </div>

          {/* Hint about JobDrawer */}
          <p className="text-xs text-gray-500 mt-4">
            💡 Suivi disponible dans la barre des tâches en bas
          </p>

          {/* Subtle animated dots */}
          <div aria-hidden="true" className="flex gap-1 mt-8">
            {[0, 1, 2].map((i) => (
              <motion.div
                key={i}
                className="w-1.5 h-1.5 rounded-full bg-white/30"
                animate={{
                  opacity: [0.3, 1, 0.3],
                  scale: [1, 1.2, 1],
                }}
                transition={{
                  duration: 1.5,
                  repeat: Infinity,
                  delay: i * 0.2,
                }}
              />
            ))}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
