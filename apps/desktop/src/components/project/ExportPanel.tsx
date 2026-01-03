import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Download, Play, Pause, FolderOpen, CheckCircle, Clock, FileVideo, X, Trash2, Volume2, VolumeX, Maximize2, RefreshCw } from 'lucide-react';
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
  const { addToast } = useToastStore();
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVideo, setSelectedVideo] = useState<Artifact | null>(null);
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
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-[var(--text-primary)]">
              Exports ({Object.keys(groupedArtifacts).length})
            </h3>
            <button
              onClick={loadArtifacts}
              className="p-2 rounded-lg hover:bg-white/5 transition-colors text-gray-400 hover:text-gray-200"
              title="Actualiser"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

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
                {Object.entries(groupedArtifacts).map(([key, items], index) => {
                  const video = items.find((a) => a.type === 'video');
                  return (
                    <motion.div
                      key={key}
                      initial={{ opacity: 0, y: 20 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                    >
                      <ExportCard
                        artifacts={items}
                        onOpen={openInFolder}
                        onSelect={setSelectedVideo}
                        isSelected={selectedVideo?.id === video?.id}
                      />
                    </motion.div>
                  );
                })}
              </AnimatePresence>
            </div>
          )}
        </div>
      </div>

      {/* Video Player Modal */}
      <AnimatePresence>
        {selectedVideo && (
          <VideoPlayerModal
            video={selectedVideo}
            onClose={() => setSelectedVideo(null)}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

function ExportCard({
  artifacts,
  onOpen,
  onSelect,
  isSelected,
}: {
  artifacts: Artifact[];
  onOpen: (path: string) => void;
  onSelect: (video: Artifact) => void;
  isSelected: boolean;
}) {
  const video = artifacts.find((a) => a.type === 'video');
  const cover = artifacts.find((a) => a.type === 'cover');

  if (!video) return null;

  const videoUrl = `file:///${video.path.replace(/\\/g, '/')}`;

  return (
    <Card 
      className={`hover:shadow-panel-hover transition-all cursor-pointer ${
        isSelected ? 'ring-2 ring-blue-500 bg-blue-500/5' : ''
      }`}
      onClick={() => onSelect(video)}
    >
      <CardContent className="p-4">
        <div className="flex gap-4">
          {/* Thumbnail with play overlay */}
          <div className="w-28 h-40 bg-[var(--bg-tertiary)] rounded-lg flex-shrink-0 flex items-center justify-center overflow-hidden relative group">
            {cover ? (
              <img
                src={`file:///${cover.path.replace(/\\/g, '/')}`}
                alt="Cover"
                className="w-full h-full object-cover"
              />
            ) : (
              <video
                src={videoUrl}
                className="w-full h-full object-cover"
                muted
                preload="metadata"
              />
            )}
            {/* Play overlay */}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
              <div className="w-12 h-12 rounded-full bg-white/20 backdrop-blur flex items-center justify-center">
                <Play className="w-6 h-6 text-white ml-1" />
              </div>
            </div>
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
                <span className="px-2 py-1 rounded-full text-[10px] font-medium bg-green-500/10 text-green-400 border border-green-500/20 flex items-center">
                  <CheckCircle className="w-3 h-3 mr-1" />
                  Prêt
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
                onClick={(e) => {
                  e.stopPropagation();
                  onOpen(video.path);
                }}
              >
                <FolderOpen className="w-4 h-4 mr-1" />
                Dossier
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(video);
                }}
              >
                <Play className="w-4 h-4 mr-1" />
                Lecture
              </Button>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// Video Player Modal
function VideoPlayerModal({
  video,
  onClose,
}: {
  video: Artifact;
  onClose: () => void;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isMuted, setIsMuted] = useState(false);

  const videoUrl = `file:///${video.path.replace(/\\/g, '/')}`;

  useEffect(() => {
    // Auto-play when modal opens
    if (videoRef.current) {
      videoRef.current.play();
      setIsPlaying(true);
    }
  }, []);

  const togglePlay = () => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  };

  const formatTimeDisplay = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="fixed inset-0 z-50 bg-black/90 flex items-center justify-center"
      onClick={onClose}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        exit={{ scale: 0.9, opacity: 0 }}
        className="relative max-w-md w-full mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute -top-12 right-0 p-2 rounded-full bg-white/10 hover:bg-white/20 transition-colors"
        >
          <X className="w-5 h-5 text-white" />
        </button>

        {/* Video container - 9:16 aspect ratio */}
        <div className="relative bg-black rounded-2xl overflow-hidden" style={{ aspectRatio: '9/16' }}>
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain"
            muted={isMuted}
            loop
            onTimeUpdate={handleTimeUpdate}
            onLoadedMetadata={handleLoadedMetadata}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            onClick={togglePlay}
          />

          {/* Play/Pause overlay */}
          <AnimatePresence>
            {!isPlaying && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="absolute inset-0 flex items-center justify-center bg-black/30"
                onClick={togglePlay}
              >
                <div className="w-20 h-20 rounded-full bg-white/20 backdrop-blur-lg flex items-center justify-center">
                  <Play className="w-10 h-10 text-white ml-2" />
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Controls */}
          <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent">
            {/* Progress bar */}
            <input
              type="range"
              min="0"
              max={duration || 100}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1 mb-3 accent-white cursor-pointer"
            />

            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <button
                  onClick={togglePlay}
                  className="p-2 rounded-full hover:bg-white/20 transition-colors"
                >
                  {isPlaying ? (
                    <Pause className="w-5 h-5 text-white" />
                  ) : (
                    <Play className="w-5 h-5 text-white" />
                  )}
                </button>

                <button
                  onClick={() => setIsMuted(!isMuted)}
                  className="p-2 rounded-full hover:bg-white/20 transition-colors"
                >
                  {isMuted ? (
                    <VolumeX className="w-5 h-5 text-white" />
                  ) : (
                    <Volume2 className="w-5 h-5 text-white" />
                  )}
                </button>

                <span className="text-xs text-white/70">
                  {formatTimeDisplay(currentTime)} / {formatTimeDisplay(duration)}
                </span>
              </div>

              <div className="text-xs text-white/50 truncate max-w-[150px]">
                {video.filename}
              </div>
            </div>
          </div>
        </div>

        {/* Info bar */}
        <div className="mt-4 flex items-center justify-center gap-4 text-sm text-white/60">
          <span>{formatFileSize(video.size)}</span>
          <span>•</span>
          <span>{formatDate(video.createdAt)}</span>
        </div>
      </motion.div>
    </motion.div>
  );
}




