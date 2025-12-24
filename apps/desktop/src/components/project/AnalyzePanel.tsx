import { useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Search, CheckCircle, Mic, Film, UserCircle, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Progress';
import { api } from '@/lib/api';
import { useJobsStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';

interface AnalyzePanelProps {
  project: {
    id: string;
    status: string;
    duration?: number;
  };
  onJobStart: (jobId: string) => void;
  onComplete: () => void;
}

export default function AnalyzePanel({ project, onJobStart, onComplete }: AnalyzePanelProps) {
  // Use shallow selector to ensure re-renders when job properties change
  const activeJob = useJobsStore(
    useShallow((state) => {
      const job = state.jobs.find(
        (j) => j.projectId === project.id && j.type === 'analyze' && j.status === 'running'
      );
      // Return a new object reference when job changes to trigger re-render
      return job ? { ...job } : null;
    })
  );

  const [options, setOptions] = useState({
    transcribe: true,
    whisperModel: 'large-v3',
    language: '',
    detectScenes: true,
    analyzeAudio: true,
    detectFaces: true,
    scoreSegments: true,
    customDictionary: [] as string[],
  });

  const isAnalyzed = ['analyzed', 'ready'].includes(project.status);

  const handleAnalyze = async () => {
    try {
      const response = await api.analyzeProject(project.id, options);
      if (response.data?.jobId) {
        onJobStart(response.data.jobId);
      }
    } catch (error) {
      console.error('Analysis failed:', error);
    }
  };

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="max-w-4xl mx-auto">
        {/* Status */}
        {isAnalyzed ? (
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
                <h3 className="font-semibold text-[var(--text-primary)]">Analyse terminée</h3>
                <p className="text-sm text-[var(--text-muted)]">
                  Les segments viraux ont été détectés
                </p>
              </div>
              <Button variant="secondary" className="ml-auto" onClick={onComplete}>
                Voir les segments →
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
                      {activeJob.stage || 'Analyse en cours...'}
                    </h3>
                    <p className="text-sm text-[var(--text-muted)]">
                      {activeJob.message || 'Traitement de la vidéo'}
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

        {/* Analysis options */}
        {!isAnalyzed && !activeJob && (
          <>
            {/* Analysis steps */}
            <div className="grid grid-cols-2 gap-4 mb-6">
              <AnalysisStep
                icon={Mic}
                title="Transcription"
                description="Transcrit l'audio avec Whisper"
                enabled={options.transcribe}
                onToggle={() =>
                  setOptions((o) => ({ ...o, transcribe: !o.transcribe }))
                }
              />
              <AnalysisStep
                icon={Film}
                title="Détection de scènes"
                description="Identifie les changements de scène"
                enabled={options.detectScenes}
                onToggle={() =>
                  setOptions((o) => ({ ...o, detectScenes: !o.detectScenes }))
                }
              />
              <AnalysisStep
                icon={UserCircle}
                title="Détection facecam"
                description="Localise la caméra du streamer"
                enabled={options.detectFaces}
                onToggle={() =>
                  setOptions((o) => ({ ...o, detectFaces: !o.detectFaces }))
                }
              />
              <AnalysisStep
                icon={Sparkles}
                title="Scoring viral"
                description="Évalue le potentiel de chaque segment"
                enabled={options.scoreSegments}
                onToggle={() =>
                  setOptions((o) => ({ ...o, scoreSegments: !o.scoreSegments }))
                }
              />
            </div>

            {/* Advanced options */}
            <Card className="mb-6">
              <CardContent className="p-6">
                <h3 className="font-semibold text-[var(--text-primary)] mb-4">
                  Options avancées
                </h3>

                <div className="space-y-4">
                  {/* Whisper model */}
                  <div>
                    <label className="text-sm font-medium text-[var(--text-primary)] block mb-2">
                      Modèle Whisper
                    </label>
                    <select
                      value={options.whisperModel}
                      onChange={(e) =>
                        setOptions((o) => ({ ...o, whisperModel: e.target.value }))
                      }
                      className="input"
                    >
                      <option value="tiny">Tiny (rapide, qualité basse)</option>
                      <option value="base">Base (rapide)</option>
                      <option value="small">Small (équilibré)</option>
                      <option value="medium">Medium (bonne qualité)</option>
                      <option value="large-v3">Large v3 (meilleure qualité)</option>
                    </select>
                  </div>

                  {/* Language */}
                  <div>
                    <label className="text-sm font-medium text-[var(--text-primary)] block mb-2">
                      Langue (optionnel)
                    </label>
                    <input
                      type="text"
                      placeholder="fr, en... (auto-détection si vide)"
                      value={options.language}
                      onChange={(e) =>
                        setOptions((o) => ({ ...o, language: e.target.value }))
                      }
                      className="input"
                    />
                  </div>

                  {/* Custom dictionary */}
                  <div>
                    <label className="text-sm font-medium text-[var(--text-primary)] block mb-2">
                      Dictionnaire personnalisé
                    </label>
                    <textarea
                      placeholder={"Noms propres, un par ligne :\nEtoStark\nKC\nCoach en séduction"}
                      value={options.customDictionary.join('\n')}
                      onChange={(e) => {
                        // Keep all lines (including empty) for editing
                        const lines = e.target.value.split('\n');
                        setOptions((o) => ({
                          ...o,
                          customDictionary: lines,
                        }));
                      }}
                      onBlur={(e) => {
                        // Clean up empty lines only when leaving the field
                        setOptions((o) => ({
                          ...o,
                          customDictionary: o.customDictionary.filter((s) => s.trim()),
                        }));
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.stopPropagation();
                        }
                      }}
                      rows={5}
                      className="input min-h-[120px] resize-y font-mono text-sm"
                    />
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Appuie sur Entrée pour ajouter un nouveau mot
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Action */}
            <div className="flex justify-end">
              <Button onClick={handleAnalyze} size="lg">
                <Search className="w-5 h-5 mr-2" />
                Lancer l'analyse
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function AnalysisStep({
  icon: Icon,
  title,
  description,
  enabled,
  onToggle,
}: {
  icon: any;
  title: string;
  description: string;
  enabled: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      onClick={onToggle}
      className={`
        p-4 rounded-xl border text-left transition-all
        ${enabled
          ? 'bg-[var(--bg-card)] border-[var(--accent-color)] shadow-sm'
          : 'bg-[var(--bg-secondary)] border-[var(--border-color)] hover:border-[var(--text-muted)]'
        }
      `}
    >
      <div className="flex items-start gap-3">
        <div
          className={`
            w-10 h-10 rounded-lg flex items-center justify-center
            ${enabled ? 'bg-[var(--accent-color)] text-white' : 'bg-[var(--bg-tertiary)] text-[var(--text-muted)]'}
          `}
        >
          <Icon className="w-5 h-5" />
        </div>
        <div>
          <h4 className="font-medium text-[var(--text-primary)]">{title}</h4>
          <p className="text-xs text-[var(--text-muted)] mt-0.5">{description}</p>
        </div>
      </div>
    </button>
  );
}


