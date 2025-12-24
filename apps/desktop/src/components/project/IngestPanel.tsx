import { useState, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Upload, CheckCircle, Film, Music, Clock, Layers } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Progress';
import { api } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import { useJobsStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';

interface IngestPanelProps {
  project: {
    id: string;
    sourcePath: string;
    sourceFilename: string;
    duration?: number;
    resolution?: { width: number; height: number };
    fps?: number;
    audioTracks: number;
    proxyPath?: string;
    audioPath?: string;
    status: string;
  };
  onJobStart: (jobId: string) => void;
  onComplete: () => void;
}

export default function IngestPanel({ project, onJobStart, onComplete }: IngestPanelProps) {
  // Use shallow selector to ensure re-renders when job properties change
  const activeJob = useJobsStore(
    useShallow((state) => {
      const job = state.jobs.find(
        (j) => j.projectId === project.id && j.type === 'ingest' && j.status === 'running'
      );
      // Return a new object reference when job changes to trigger re-render
      return job ? { ...job } : null;
    })
  );

  const [options, setOptions] = useState({
    createProxy: true,
    extractAudio: true,
    audioTrack: 0,
    normalizeAudio: true,
  });

  const isIngested = ['ingested', 'analyzing', 'analyzed', 'ready'].includes(project.status);

  const handleIngest = async () => {
    try {
      const response = await api.ingestProject(project.id, options);
      if (response.data?.jobId) {
        onJobStart(response.data.jobId);
      }
    } catch (error) {
      console.error('Ingest failed:', error);
    }
  };

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="max-w-4xl mx-auto">
        {/* Status */}
        {isIngested ? (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mb-8"
          >
            <div className="flex items-center gap-4 p-6 bg-viral-high/5 border border-viral-high/20 rounded-xl">
              <div className="w-12 h-12 rounded-full bg-viral-high/10 flex items-center justify-center">
                <CheckCircle className="w-6 h-6 text-viral-high" />
              </div>
              <div>
                <h3 className="font-semibold text-[var(--text-primary)]">Ingestion terminée</h3>
                <p className="text-sm text-[var(--text-muted)]">
                  La vidéo est prête pour l'analyse
                </p>
              </div>
              <Button variant="secondary" className="ml-auto" onClick={onComplete}>
                Passer à l'analyse →
              </Button>
            </div>
          </motion.div>
        ) : activeJob ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="mb-8"
          >
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center gap-4 mb-4">
                  <div className="w-10 h-10 rounded-full bg-viral-medium/10 flex items-center justify-center">
                    <div className="w-5 h-5 border-2 border-viral-medium border-t-transparent rounded-full animate-spin" />
                  </div>
                  <div>
                    <h3 className="font-semibold text-[var(--text-primary)]">
                      {activeJob.stage || 'Ingestion en cours...'}
                    </h3>
                    <p className="text-sm text-[var(--text-muted)]">
                      {activeJob.message || 'Préparation des fichiers'}
                    </p>
                  </div>
                  <span className="ml-auto text-lg font-bold text-[var(--text-primary)]">
                    {activeJob.progress.toFixed(0)}%
                  </span>
                </div>
                <Progress value={activeJob.progress} />
              </CardContent>
            </Card>
          </motion.div>
        ) : null}

        {/* Source info */}
        <Card className="mb-6">
          <CardContent className="p-6">
            <h3 className="font-semibold text-[var(--text-primary)] mb-4">Fichier source</h3>
            
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <InfoItem
                icon={Film}
                label="Fichier"
                value={project.sourceFilename}
              />
              {project.resolution && (
                <InfoItem
                  icon={Layers}
                  label="Résolution"
                  value={`${project.resolution.width}×${project.resolution.height}`}
                />
              )}
              {project.duration && (
                <InfoItem
                  icon={Clock}
                  label="Durée"
                  value={formatDuration(project.duration)}
                />
              )}
              <InfoItem
                icon={Music}
                label="Pistes audio"
                value={`${project.audioTracks} piste${project.audioTracks > 1 ? 's' : ''}`}
              />
            </div>
          </CardContent>
        </Card>

        {/* Options */}
        {!isIngested && !activeJob && (
          <Card className="mb-6">
            <CardContent className="p-6">
              <h3 className="font-semibold text-[var(--text-primary)] mb-4">Options d'ingestion</h3>

              <div className="space-y-4">
                <OptionToggle
                  label="Créer un proxy"
                  description="Génère une version légère pour la prévisualisation"
                  checked={options.createProxy}
                  onChange={(checked) =>
                    setOptions((o) => ({ ...o, createProxy: checked }))
                  }
                />

                <OptionToggle
                  label="Extraire l'audio"
                  description="Extrait l'audio pour la transcription"
                  checked={options.extractAudio}
                  onChange={(checked) =>
                    setOptions((o) => ({ ...o, extractAudio: checked }))
                  }
                />

                {options.extractAudio && (
                  <>
                    <OptionToggle
                      label="Normaliser l'audio"
                      description="Ajuste le niveau sonore pour une meilleure qualité"
                      checked={options.normalizeAudio}
                      onChange={(checked) =>
                        setOptions((o) => ({ ...o, normalizeAudio: checked }))
                      }
                    />

                    {project.audioTracks > 1 && (
                      <div>
                        <label className="text-sm font-medium text-[var(--text-primary)] block mb-2">
                          Piste audio
                        </label>
                        <select
                          value={options.audioTrack}
                          onChange={(e) =>
                            setOptions((o) => ({
                              ...o,
                              audioTrack: parseInt(e.target.value),
                            }))
                          }
                          className="input"
                        >
                          {[...Array(project.audioTracks)].map((_, i) => (
                            <option key={i} value={i}>
                              Piste {i + 1}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Action */}
        {!isIngested && !activeJob && (
          <div className="flex justify-end">
            <Button onClick={handleIngest} size="lg">
              <Upload className="w-5 h-5 mr-2" />
              Lancer l'ingestion
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}

function InfoItem({
  icon: Icon,
  label,
  value,
}: {
  icon: any;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="w-8 h-8 rounded-lg bg-[var(--bg-tertiary)] flex items-center justify-center flex-shrink-0">
        <Icon className="w-4 h-4 text-[var(--text-muted)]" />
      </div>
      <div className="min-w-0">
        <p className="text-xs text-[var(--text-muted)]">{label}</p>
        <p className="text-sm font-medium text-[var(--text-primary)] truncate">{value}</p>
      </div>
    </div>
  );
}

function OptionToggle({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  return (
    <label className="flex items-start gap-4 cursor-pointer group">
      <div className="pt-0.5">
        <button
          type="button"
          role="switch"
          aria-checked={checked}
          onClick={() => onChange(!checked)}
          className={`
            relative w-10 h-6 rounded-full transition-colors
            ${checked ? 'bg-[var(--accent-color)]' : 'bg-[var(--border-color)]'}
          `}
        >
          <span
            className={`
              absolute top-1 left-1 w-4 h-4 rounded-full bg-white transition-transform
              ${checked ? 'translate-x-4' : 'translate-x-0'}
            `}
          />
        </button>
      </div>
      <div>
        <p className="font-medium text-[var(--text-primary)] group-hover:text-[var(--accent-color)]">
          {label}
        </p>
        <p className="text-sm text-[var(--text-muted)]">{description}</p>
      </div>
    </label>
  );
}




