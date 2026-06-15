import { useEffect } from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { mediaUrl } from '@/lib/config';
import { TimelineHeatmap } from '@/components/segments/TimelineHeatmap';

interface Segment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  topicLabel?: string;
}

interface SegmentPreviewProps {
  project: {
    id: string;
    duration?: number;
    proxy_path?: string;
    source_path?: string;
  };
  segments: Segment[];
  selectedSegment: Segment | null;
  isPlaying: boolean;
  currentTime: number;
  isMuted: boolean;
  onPlayPause: () => void;
  onSeek: (time: number) => void;
  onMuteToggle: () => void;
  onTimeUpdate: (time: number) => void;
  onEnded: () => void;
  videoRef: React.RefObject<HTMLVideoElement>;
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export function SegmentPreview({
  project,
  segments,
  selectedSegment,
  isPlaying,
  currentTime,
  isMuted,
  onPlayPause,
  onSeek,
  onMuteToggle,
  onTimeUpdate,
  onEnded,
  videoRef,
}: SegmentPreviewProps) {
  const videoSrc = project.proxy_path || project.source_path;

  // Update time display
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => onTimeUpdate(video.currentTime);
    const handleEnded = () => onEnded();

    video.addEventListener('timeupdate', handleTimeUpdate);
    video.addEventListener('ended', handleEnded);

    return () => {
      video.removeEventListener('timeupdate', handleTimeUpdate);
      video.removeEventListener('ended', handleEnded);
    };
  }, [onTimeUpdate, onEnded]);

  return (
    <div className="flex-1 flex flex-col">
      {/* Video area */}
      <div className="flex-1 bg-black flex items-center justify-center relative">
        {videoSrc ? (
          <>
            <video
              ref={videoRef}
              src={mediaUrl(project.id, 'proxy')}
              className="max-h-full max-w-full"
              muted={isMuted}
              onClick={onPlayPause}
            />

            {/* Overlay info */}
            {selectedSegment && (
              <div className="absolute top-4 left-4 bg-black/70 backdrop-blur-sm rounded-lg px-3 py-2 text-white text-sm">
                <div className="font-medium">{selectedSegment.topicLabel || 'Segment'}</div>
                <div className="text-xs opacity-70">
                  {formatTime(selectedSegment.startTime)} → {formatTime(selectedSegment.endTime)}
                </div>
              </div>
            )}

            {/* Time indicator */}
            <div className="absolute bottom-4 right-4 bg-black/70 backdrop-blur-sm rounded-lg px-3 py-1.5 text-white text-sm font-mono">
              {formatTime(currentTime)} / {formatTime(project.duration || 0)}
            </div>
          </>
        ) : (
          <div className="text-[var(--text-muted)]">Aucune vidéo disponible</div>
        )}
      </div>

      {/* Controls bar */}
      <div className="h-16 bg-[var(--bg-card)] border-t border-[var(--border-color)] flex items-center px-4 gap-4">
        {/* Play controls */}
        <div className="flex items-center gap-2">
          <button
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            onClick={() => onSeek(Math.max(0, currentTime - 10))}
            aria-label="Reculer de 10 secondes"
          >
            <SkipBack aria-hidden="true" className="w-5 h-5 text-[var(--text-secondary)]" />
          </button>
          <button
            className="p-3 rounded-full bg-blue-500 hover:bg-blue-600 text-white transition-colors"
            onClick={onPlayPause}
            aria-label={isPlaying ? 'Mettre en pause' : 'Lire'}
            aria-pressed={isPlaying}
          >
            {isPlaying ? <Pause aria-hidden="true" className="w-5 h-5" /> : <Play aria-hidden="true" className="w-5 h-5 ml-0.5" />}
          </button>
          <button
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            onClick={() => onSeek(currentTime + 10)}
            aria-label="Avancer de 10 secondes"
          >
            <SkipForward aria-hidden="true" className="w-5 h-5 text-[var(--text-secondary)]" />
          </button>
        </div>

        {/* Timeline with Heatmap */}
        <div className="flex-1 flex flex-col gap-1">
          {/* Segment Heatmap */}
          <TimelineHeatmap
            segments={segments}
            totalDuration={project.duration || 0}
            currentTime={currentTime}
            onSeek={onSeek}
            height={24}
            className="rounded"
          />

          {/* Progress scrubber */}
          <div className="relative h-1 bg-[var(--bg-tertiary)] rounded-full cursor-pointer group"
            role="slider"
            tabIndex={0}
            aria-label="Barre de progression"
            aria-valuemin={0}
            aria-valuemax={Math.round(project.duration || 0)}
            aria-valuenow={Math.round(currentTime)}
            onKeyDown={(e) => {
              const total = project.duration || 0;
              if (e.key === 'ArrowRight') {
                e.preventDefault();
                onSeek(Math.min(total, currentTime + 5));
              } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                onSeek(Math.max(0, currentTime - 5));
              }
            }}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              onSeek(pct * (project.duration || 0));
            }}
          >
            {/* Progress */}
            <div
              className="absolute inset-y-0 left-0 bg-blue-500 rounded-full"
              style={{ width: `${(currentTime / (project.duration || 1)) * 100}%` }}
            />

            {/* Selected segment highlight */}
            {selectedSegment && (
              <div
                className="absolute inset-y-0 bg-green-500/50 rounded-full"
                style={{
                  left: `${(selectedSegment.startTime / (project.duration || 1)) * 100}%`,
                  width: `${((selectedSegment.endTime - selectedSegment.startTime) / (project.duration || 1)) * 100}%`,
                }}
              />
            )}
          </div>
        </div>

        {/* Volume */}
        <button
          className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          onClick={onMuteToggle}
          aria-label={isMuted ? 'Activer le son' : 'Couper le son'}
          aria-pressed={isMuted}
        >
          {isMuted ? (
            <VolumeX aria-hidden="true" className="w-5 h-5 text-[var(--text-secondary)]" />
          ) : (
            <Volume2 aria-hidden="true" className="w-5 h-5 text-[var(--text-secondary)]" />
          )}
        </button>
      </div>
    </div>
  );
}
