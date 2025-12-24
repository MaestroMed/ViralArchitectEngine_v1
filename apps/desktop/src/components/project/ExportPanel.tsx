import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Play, Pause, FolderOpen, CheckCircle, Clock, FileVideo } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card, CardContent } from '@/components/ui/Card';
import { Progress } from '@/components/ui/Progress';
import { api } from '@/lib/api';
import { formatDuration, formatFileSize, formatDate } from '@/lib/utils';
import { useJobsStore, useToastStore } from '@/store';
import { useShallow } from 'zustand/react/shallow';

interface ExportPanelProps {
  project: {
    id: string;
  };
}

interface Artifact {
  id: string;
  segmentId: string;
  variant: string;
  type: string;
  path: string;
  filename: string;
  size: number;
  createdAt: string;
}

export default function ExportPanel({ project }: ExportPanelProps) {
  const { addJob } = useJobsStore();
  const { addToast } = useToastStore();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const previousJobStatusRef = useRef<Record<string, string>>({});

  // Get export jobs for this project via WebSocket-synced store
  const exportJobs = useJobsStore(
    useShallow((state) =>
      state.jobs.filter((j) => j.projectId === project.id && j.type === 'export')
    )
  );

  const activeJob = exportJobs.find((j) => j.status === 'running');

  // Watch for job completion via WebSocket
  useEffect(() => {
    exportJobs.forEach((job) => {
      const prevStatus = previousJobStatusRef.current[job.id];
      if (prevStatus === 'running' && job.status === 'completed') {
        loadArtifacts();
      }
      previousJobStatusRef.current[job.id] = job.status;
    });
  }, [exportJobs]);

  useEffect(() => {
    loadArtifacts();
  }, [project.id]);

  const loadArtifacts = async () => {
    try {
      const response = await api.listArtifacts(project.id);
      setArtifacts(response.data || []);
    } catch (error) {
      console.error('Failed to load artifacts:', error);
    } finally {
      setLoading(false);
    }
  };

  const openInFolder = async (path: string) => {
    if (window.forge) {
      await window.forge.showItem(path);
    }
  };

  // Group artifacts by segment/variant
  const groupedArtifacts = artifacts.reduce((acc, artifact) => {
    const key = `${artifact.segmentId}-${artifact.variant}`;
    if (!acc[key]) {
      acc[key] = [];
    }
    acc[key].push(artifact);
    return acc;
  }, {} as Record<string, Artifact[]>);

  return (
    <div className="h-full p-6 overflow-auto">
      <div className="max-w-4xl mx-auto">
        {/* Active export */}
        {activeJob && (
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
                      {activeJob.stage || 'Export en cours...'}
                    </h3>
                    <p className="text-sm text-[var(--text-muted)]">
                      {activeJob.message || 'Génération du clip'}
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
        )}

        {/* Export list */}
        <div>
          <h3 className="font-semibold text-[var(--text-primary)] mb-4">
            Exports ({Object.keys(groupedArtifacts).length})
          </h3>

          {loading ? (
            <div className="space-y-4">
              {[...Array(3)].map((_, i) => (
                <div
                  key={i}
                  className="h-24 bg-[var(--bg-tertiary)] rounded-xl animate-pulse"
                />
              ))}
            </div>
          ) : Object.keys(groupedArtifacts).length === 0 ? (
            <Card>
              <CardContent className="p-12 text-center">
                <Download className="w-12 h-12 mx-auto mb-4 text-[var(--text-muted)] opacity-30" />
                <h4 className="font-medium text-[var(--text-primary)] mb-2">
                  Aucun export
                </h4>
                <p className="text-sm text-[var(--text-muted)] mb-4">
                  Sélectionnez un segment dans l'onglet Forge et exportez-le
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              <AnimatePresence>
                {Object.entries(groupedArtifacts).map(([key, items], index) => (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: index * 0.05 }}
                  >
                    <ExportCard
                      artifacts={items}
                      onOpen={openInFolder}
                    />
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ExportCard({
  artifacts,
  onOpen,
}: {
  artifacts: Artifact[];
  onOpen: (path: string) => void;
}) {
  const video = artifacts.find((a) => a.type === 'video');
  const cover = artifacts.find((a) => a.type === 'cover');
  const metadata = artifacts.find((a) => a.type === 'metadata');

  if (!video) return null;

  return (
    <Card className="hover:shadow-panel-hover transition-shadow">
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Thumbnail */}
          <div className="w-24 h-24 bg-[var(--bg-tertiary)] rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden">
            {cover ? (
              <img
                src={`file://${cover.path}`}
                alt="Cover"
                className="w-full h-full object-cover"
              />
            ) : (
              <FileVideo className="w-8 h-8 text-[var(--text-muted)] opacity-30" />
            )}
          </div>

          {/* Info */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h4 className="font-medium text-[var(--text-primary)] truncate">
                  {video.filename}
                </h4>
                <p className="text-xs text-[var(--text-muted)] mt-1">
                  Variant {artifacts[0].variant} • {formatFileSize(video.size)}
                </p>
              </div>

              <div className="flex items-center gap-2">
                <span className="badge-success">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Exporté
                </span>
              </div>
            </div>

            {/* Files */}
            <div className="flex items-center gap-2 mt-3 text-xs text-[var(--text-muted)]">
              <span>{artifacts.length} fichiers</span>
              <span>•</span>
              <span>{formatDate(artifacts[0].createdAt)}</span>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-2 mt-3">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onOpen(video.path)}
              >
                <FolderOpen className="w-4 h-4 mr-1" />
                Ouvrir le dossier
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}




