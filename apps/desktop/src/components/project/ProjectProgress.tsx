import { useMemo } from 'react';
import { motion } from 'framer-motion';
import { Download, HardDrive, Brain, Loader2 } from 'lucide-react';
import { useJobsStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';

interface ProjectProgressProps {
  projectId: string;
  projectStatus: string;
}

// Phase weights for global progress calculation
const PHASE_WEIGHTS = {
  download: { start: 0, end: 15 },
  ingest: { start: 15, end: 30 },
  analyze: { start: 30, end: 100 },
};

const PHASE_LABELS: Record<string, string> = {
  download: 'Téléchargement',
  ingest: 'Préparation',
  analyze: 'Analyse',
};

const PHASE_ICONS: Record<string, typeof Download> = {
  download: Download,
  ingest: HardDrive,
  analyze: Brain,
};

export default function ProjectProgress({ projectId, projectStatus }: ProjectProgressProps) {
  // Get all jobs for this project
  const projectJobs = useJobsStore(
    useShallow((state) =>
      state.jobs.filter((j) => j.projectId === projectId)
    )
  );

  // Calculate global progress from all jobs
  const { globalProgress, currentPhase, isActive } = useMemo(() => {
    // Find active or most recent job
    const activeJob = projectJobs.find((j) => j.status === 'running' || j.status === 'pending');
    
    if (!activeJob) {
      // No active job - determine from project status
      if (['analyzed', 'ready'].includes(projectStatus)) {
        return { globalProgress: 100, currentPhase: null, phaseProgress: 100, isActive: false };
      }
      if (projectStatus === 'ingested') {
        return { globalProgress: 30, currentPhase: null, phaseProgress: 100, isActive: false };
      }
      if (projectStatus === 'error') {
        return { globalProgress: 0, currentPhase: null, phaseProgress: 0, isActive: false };
      }
      return { globalProgress: 0, currentPhase: null, phaseProgress: 0, isActive: false };
    }

    // Map job type to phase
    const jobType = activeJob.type;
    let phase: keyof typeof PHASE_WEIGHTS = 'download';
    
    if (jobType === 'download') phase = 'download';
    else if (jobType === 'ingest') phase = 'ingest';
    else if (jobType === 'analyze') phase = 'analyze';
    else phase = 'analyze'; // Default for other types

    const phaseWeight = PHASE_WEIGHTS[phase];
    const jobProgress = activeJob.progress || 0;
    
    // Calculate global progress
    const phaseRange = phaseWeight.end - phaseWeight.start;
    const globalProg = phaseWeight.start + (jobProgress / 100) * phaseRange;

    return {
      globalProgress: Math.min(99, globalProg), // Cap at 99 until truly complete
      currentPhase: phase,
      phaseProgress: jobProgress,
      isActive: activeJob.status === 'running',
    };
  }, [projectJobs, projectStatus]);

  // Don't render if complete or no activity
  if (!currentPhase && globalProgress >= 100) return null;
  if (!currentPhase && !projectJobs.length) return null;

  const PhaseIcon = currentPhase ? PHASE_ICONS[currentPhase] : Loader2;

  return (
    <div className="absolute inset-0 bg-gradient-to-t from-black/90 via-black/60 to-transparent flex flex-col justify-end p-3">
      {/* Phase indicator */}
      <div className="flex items-center gap-2 mb-2">
        <motion.div
          aria-hidden="true"
          animate={isActive ? { rotate: 360 } : {}}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="shrink-0"
        >
          {isActive ? (
            <Loader2 className="w-4 h-4 text-cyan-400" />
          ) : (
            <PhaseIcon className="w-4 h-4 text-cyan-400" />
          )}
        </motion.div>
        <span className="text-xs font-medium text-white truncate">
          {currentPhase ? PHASE_LABELS[currentPhase] : 'En attente...'}
        </span>
        <span className="text-xs text-white/70 ml-auto tabular-nums">
          {Math.round(globalProgress)}%
        </span>
      </div>

      {/* Progress bar with phases */}
      <div
        className="relative h-2 bg-white/10 rounded-full overflow-hidden"
        role="progressbar"
        aria-label={`Progression${currentPhase ? ` : ${PHASE_LABELS[currentPhase]}` : ''}`}
        aria-valuenow={Math.round(globalProgress)}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        {/* Phase markers */}
        <div 
          className="absolute top-0 bottom-0 w-px bg-white/20" 
          style={{ left: '15%' }} 
        />
        <div 
          className="absolute top-0 bottom-0 w-px bg-white/20" 
          style={{ left: '30%' }} 
        />

        {/* Progress fill */}
        <motion.div
          className="absolute inset-y-0 left-0 rounded-full"
          style={{
            background: 'linear-gradient(90deg, #06b6d4 0%, #10b981 50%, #22c55e 100%)',
          }}
          initial={{ width: 0 }}
          animate={{ width: `${globalProgress}%` }}
          transition={{ duration: 0.5, ease: 'easeOut' }}
        />

        {/* Animated shimmer */}
        {isActive && (
          <motion.div
            className="absolute inset-y-0 w-20 bg-gradient-to-r from-transparent via-white/30 to-transparent"
            animate={{ x: [-80, 300] }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
          />
        )}
      </div>

      {/* Phase labels */}
      <div className="flex justify-between mt-1 text-[9px] text-white/40">
        <span className={currentPhase === 'download' ? 'text-cyan-400' : ''}>DL</span>
        <span className={currentPhase === 'ingest' ? 'text-cyan-400' : ''}>Prep</span>
        <span className={currentPhase === 'analyze' ? 'text-cyan-400' : ''}>IA</span>
      </div>
    </div>
  );
}
