import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Play,
  Pause,
  Clock,
  Zap,
  ChevronRight,
  Download,
  Filter,
  Grid3X3,
  LayoutList,
  Volume2,
  VolumeX,
  SkipBack,
  SkipForward,
  Layers,
  Check,
  AlertTriangle,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { formatDuration, truncate } from '@/lib/utils';

interface ForgePanelProps {
  project: {
    id: string;
    duration?: number;
    proxy_path?: string;
    source_path?: string;
  };
}

interface Segment {
  id: string;
  startTime: number;
  endTime: number;
  duration: number;
  topicLabel?: string;
  hookText?: string;
  transcript?: string;
  score: {
    total: number;
    hookStrength: number;
    payoff: number;
    humourReaction: number;
    tensionSurprise: number;
    clarityAutonomy: number;
    rhythm: number;
    reasons: string[];
    tags: string[];
  };
}

type FilterMode = 'all' | 'monetizable' | 'high-score';
type SortMode = 'score' | 'duration' | 'time';

export default function ForgePanel({ project }: ForgePanelProps) {
  const navigate = useNavigate();
  const videoRef = useRef<HTMLVideoElement>(null);
  
  const [segments, setSegments] = useState<Segment[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedSegment, setSelectedSegment] = useState<Segment | null>(null);
  
  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [isMuted, setIsMuted] = useState(false);
  
  // Filter/Sort state
  const [filter, setFilter] = useState<FilterMode>('all');
  const [sortBy, setSortBy] = useState<SortMode>('score');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  useEffect(() => {
    loadSegments();
  }, [project.id]);

  const loadSegments = async () => {
    try {
      const res = await api.listSegments(project.id, { pageSize: 100 });
      setSegments(res.data?.items || []);
    } catch (error) {
      console.error('Failed to load segments:', error);
    } finally {
      setLoading(false);
    }
  };

  // Filter and sort segments (with null-safe score access)
  const getScore = (seg: Segment) => seg.score?.total ?? 0;
  
  const filteredSegments = segments
    .filter((seg) => {
      if (filter === 'monetizable') return seg.duration >= 60;
      if (filter === 'high-score') return getScore(seg) >= 60;
      return true;
    })
    .sort((a, b) => {
      if (sortBy === 'score') return getScore(b) - getScore(a);
      if (sortBy === 'duration') return b.duration - a.duration;
      return a.startTime - b.startTime;
    });

  // Stats
  const stats = {
    total: segments.length,
    monetizable: segments.filter((s) => s.duration >= 60).length,
    highScore: segments.filter((s) => getScore(s) >= 60).length,
  };

  // Video controls
  const handlePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause();
      } else {
        videoRef.current.play();
      }
      setIsPlaying(!isPlaying);
    }
  }, [isPlaying]);

  const handleSeek = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
      setCurrentTime(time);
    }
  }, []);

  const handleSegmentSelect = useCallback((segment: Segment) => {
    setSelectedSegment(segment);
    if (videoRef.current) {
      videoRef.current.currentTime = segment.startTime;
      setCurrentTime(segment.startTime);
    }
  }, []);

  const handleSegmentPlay = useCallback((segment: Segment) => {
    setSelectedSegment(segment);
    if (videoRef.current) {
      videoRef.current.currentTime = segment.startTime;
      videoRef.current.play();
      setIsPlaying(true);
    }
  }, []);

  // Update time display
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    
    const onTimeUpdate = () => setCurrentTime(video.currentTime);
    const onEnded = () => setIsPlaying(false);
    
    video.addEventListener('timeupdate', onTimeUpdate);
    video.addEventListener('ended', onEnded);
    
    return () => {
      video.removeEventListener('timeupdate', onTimeUpdate);
      video.removeEventListener('ended', onEnded);
    };
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      
      switch (e.key) {
        case ' ':
          e.preventDefault();
          handlePlayPause();
          break;
        case 'ArrowLeft':
          handleSeek(Math.max(0, currentTime - (e.shiftKey ? 5 : 1)));
          break;
        case 'ArrowRight':
          handleSeek(currentTime + (e.shiftKey ? 5 : 1));
          break;
        case 'm':
          setIsMuted((m) => !m);
          break;
      }
    };
    
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [currentTime, handlePlayPause, handleSeek]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const videoSrc = project.proxyPath || project.sourcePath;

  return (
    <div className="h-full flex bg-[var(--bg-primary)]">
      {/* LEFT: Segment List */}
      <div className="w-80 flex flex-col border-r border-[var(--border-color)] bg-[var(--bg-card)]">
        {/* Header */}
        <div className="p-4 border-b border-[var(--border-color)]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-bold text-lg text-[var(--text-primary)]">Segments</h3>
            <span className="text-xs text-[var(--text-muted)]">{filteredSegments.length} / {stats.total}</span>
          </div>
          
          {/* Filter pills */}
          <div className="flex items-center gap-1 mb-3">
            <FilterPill active={filter === 'all'} onClick={() => setFilter('all')}>
              Tous
            </FilterPill>
            <FilterPill active={filter === 'monetizable'} onClick={() => setFilter('monetizable')}>
              <Clock className="w-3 h-3 mr-1" />
              ≥1min
            </FilterPill>
            <FilterPill active={filter === 'high-score'} onClick={() => setFilter('high-score')}>
              <Zap className="w-3 h-3 mr-1" />
              60+
            </FilterPill>
          </div>
          
          {/* Sort & View toggle */}
          <div className="flex items-center justify-between">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortMode)}
              className="text-xs bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-2 py-1 text-[var(--text-secondary)]"
            >
              <option value="score">Par score</option>
              <option value="duration">Par durée</option>
              <option value="time">Chronologique</option>
            </select>
            
            <div className="flex items-center gap-1 bg-[var(--bg-secondary)] rounded-lg p-0.5">
              <button
                className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-[var(--bg-card)] shadow-sm' : ''}`}
                onClick={() => setViewMode('grid')}
              >
                <Grid3X3 className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
              </button>
              <button
                className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-[var(--bg-card)] shadow-sm' : ''}`}
                onClick={() => setViewMode('list')}
              >
                <LayoutList className="w-3.5 h-3.5 text-[var(--text-secondary)]" />
              </button>
            </div>
          </div>
        </div>

        {/* Segment List */}
        <div className="flex-1 overflow-y-auto p-2 scrollbar-thin">
          {filteredSegments.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-center p-4">
              <Filter className="w-10 h-10 text-[var(--text-muted)] opacity-30 mb-3" />
              <p className="text-sm text-[var(--text-muted)]">Aucun segment trouvé</p>
            </div>
          ) : viewMode === 'grid' ? (
            // Grid mode
            <div className="grid grid-cols-2 gap-2">
              {filteredSegments.map((segment) => (
                <SegmentCardCompact
                  key={segment.id}
                  segment={segment}
                  isSelected={selectedSegment?.id === segment.id}
                  onSelect={() => handleSegmentSelect(segment)}
                  onPlay={() => handleSegmentPlay(segment)}
                />
              ))}
            </div>
          ) : (
            // List mode
            <div className="space-y-1">
              {filteredSegments.map((segment) => (
                <SegmentRowCompact
                  key={segment.id}
                  segment={segment}
                  isSelected={selectedSegment?.id === segment.id}
                  onSelect={() => handleSegmentSelect(segment)}
                  onPlay={() => handleSegmentPlay(segment)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CENTER: Video Preview */}
      <div className="flex-1 flex flex-col">
        {/* Video area */}
        <div className="flex-1 bg-black flex items-center justify-center relative">
          {videoSrc ? (
            <>
              <video
                ref={videoRef}
                src={`http://localhost:8420/media/${project.id}/proxy`}
                className="max-h-full max-w-full"
                muted={isMuted}
                onClick={handlePlayPause}
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
              onClick={() => handleSeek(Math.max(0, currentTime - 10))}
            >
              <SkipBack className="w-5 h-5 text-[var(--text-secondary)]" />
            </button>
            <button
              className="p-3 rounded-full bg-blue-500 hover:bg-blue-600 text-white transition-colors"
              onClick={handlePlayPause}
            >
              {isPlaying ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5 ml-0.5" />}
            </button>
            <button
              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
              onClick={() => handleSeek(currentTime + 10)}
            >
              <SkipForward className="w-5 h-5 text-[var(--text-secondary)]" />
            </button>
          </div>
          
          {/* Timeline scrubber */}
          <div className="flex-1 relative h-2 bg-[var(--bg-tertiary)] rounded-full cursor-pointer group"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              handleSeek(pct * (project.duration || 0));
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
                className="absolute inset-y-0 bg-green-500/30 rounded-full"
                style={{
                  left: `${(selectedSegment.startTime / (project.duration || 1)) * 100}%`,
                  width: `${((selectedSegment.endTime - selectedSegment.startTime) / (project.duration || 1)) * 100}%`,
                }}
              />
            )}
            
            {/* Playhead */}
            <div
              className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full shadow-lg border-2 border-blue-500 opacity-0 group-hover:opacity-100 transition-opacity"
              style={{ left: `${(currentTime / (project.duration || 1)) * 100}%`, marginLeft: '-6px' }}
            />
          </div>
          
          {/* Volume */}
          <button
            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            onClick={() => setIsMuted(!isMuted)}
          >
            {isMuted ? (
              <VolumeX className="w-5 h-5 text-[var(--text-secondary)]" />
            ) : (
              <Volume2 className="w-5 h-5 text-[var(--text-secondary)]" />
            )}
          </button>
        </div>
      </div>

      {/* RIGHT: Segment Details + Actions */}
      <div className="w-80 flex flex-col border-l border-[var(--border-color)] bg-[var(--bg-card)]">
        {selectedSegment ? (
          <>
            {/* Segment info */}
            <div className="p-4 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-3 mb-4">
                <ScoreBadge score={selectedSegment.score?.total} size="lg" />
                <div className="flex-1">
                  <h3 className="font-semibold text-[var(--text-primary)]">
                    {selectedSegment.topicLabel || 'Segment sans titre'}
                  </h3>
                  <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
                    <Clock className="w-3 h-3" />
                    <span>{formatDuration(selectedSegment.duration)}</span>
                    {selectedSegment.duration >= 60 ? (
                      <span className="flex items-center text-green-500">
                        <Check className="w-3 h-3 mr-0.5" /> Monétisable
                      </span>
                    ) : (
                      <span className="flex items-center text-amber-500">
                        <AlertTriangle className="w-3 h-3 mr-0.5" /> &lt; 1 min
                      </span>
                    )}
                  </div>
                </div>
              </div>
              
              {/* Hook */}
              {selectedSegment.hookText && (
                <div className="bg-[var(--bg-secondary)] rounded-lg p-3 mb-3">
                  <p className="text-xs text-[var(--text-muted)] mb-1">Hook détecté</p>
                  <p className="text-sm text-[var(--text-primary)] italic">"{selectedSegment.hookText}"</p>
                </div>
              )}
              
              {/* Tags */}
              {(selectedSegment.score?.tags?.length ?? 0) > 0 && (
                <div className="flex flex-wrap gap-1">
                  {selectedSegment.score?.tags?.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-muted)] text-xs rounded-full capitalize"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Score breakdown */}
            <div className="p-4 border-b border-[var(--border-color)]">
              <h4 className="text-sm font-medium text-[var(--text-primary)] mb-3">Score détaillé</h4>
              <div className="space-y-2">
                <ScoreRow label="Hook" value={selectedSegment.score?.hookStrength ?? 0} max={25} />
                <ScoreRow label="Payoff" value={selectedSegment.score?.payoff ?? 0} max={20} />
                <ScoreRow label="Humour/Réaction" value={selectedSegment.score?.humourReaction ?? 0} max={15} />
                <ScoreRow label="Tension/Surprise" value={selectedSegment.score?.tensionSurprise ?? 0} max={15} />
                <ScoreRow label="Clarté" value={selectedSegment.score?.clarityAutonomy ?? 0} max={15} />
                <ScoreRow label="Rythme" value={selectedSegment.score?.rhythm ?? 0} max={10} />
              </div>
            </div>

            {/* Transcript preview */}
            {selectedSegment.transcript && (
              <div className="flex-1 overflow-auto p-4">
                <h4 className="text-sm font-medium text-[var(--text-primary)] mb-2">Transcription</h4>
                <p className="text-sm text-[var(--text-secondary)] leading-relaxed">
                  {selectedSegment.transcript.slice(0, 500)}
                  {selectedSegment.transcript.length > 500 && '...'}
                </p>
              </div>
            )}

            {/* Actions */}
            <div className="p-4 border-t border-[var(--border-color)] space-y-2">
              <Button
                size="sm"
                onClick={() => navigate(`/editor/${project.id}?segment=${selectedSegment.id}`)}
                className="w-full flex items-center justify-center gap-2 bg-blue-500 hover:bg-blue-600"
              >
                <Layers className="w-4 h-4" />
                Ouvrir l'éditeur 9:16
              </Button>
              <div className="grid grid-cols-2 gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => handleSegmentPlay(selectedSegment)}
                  className="flex items-center justify-center gap-1.5"
                >
                  <Play className="w-4 h-4" />
                  Preview
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => {/* TODO: export */}}
                  className="flex items-center justify-center gap-1.5"
                >
                  <Download className="w-4 h-4" />
                  Export rapide
                </Button>
              </div>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center p-4">
            <div className="text-center">
              <ChevronRight className="w-12 h-12 mx-auto mb-3 text-[var(--text-muted)] opacity-30" />
              <p className="text-sm text-[var(--text-muted)]">
                Sélectionnez un segment pour voir les détails
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Components

function FilterPill({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      className={`flex items-center px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
        active
          ? 'bg-blue-500 text-white'
          : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
      }`}
      onClick={onClick}
    >
      {children}
    </button>
  );
}

function SegmentCardCompact({
  segment,
  isSelected,
  onSelect,
  onPlay,
}: {
  segment: Segment;
  isSelected: boolean;
  onSelect: () => void;
  onPlay: () => void;
}) {
  const isMonetizable = segment.duration >= 60;
  
  return (
    <motion.div
      className={`relative rounded-lg overflow-hidden cursor-pointer transition-all ${
        isSelected ? 'ring-2 ring-blue-500' : 'hover:ring-1 hover:ring-[var(--border-color)]'
      }`}
      onClick={onSelect}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
    >
      {/* Thumbnail */}
      <div className="aspect-video bg-gradient-to-br from-gray-800 to-gray-900 flex items-center justify-center relative">
        <img
          src={`http://localhost:8420/v1/projects/${segment.id.split('-')[0]}/thumbnail?time=${segment.startTime + 1}&width=160&height=90`}
          alt=""
          className="absolute inset-0 w-full h-full object-cover"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = 'none';
          }}
        />
        <button
          className="absolute inset-0 flex items-center justify-center bg-black/0 hover:bg-black/40 transition-colors group"
          onClick={(e) => {
            e.stopPropagation();
            onPlay();
          }}
        >
          <div className="w-8 h-8 bg-white/90 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <Play className="w-4 h-4 text-gray-900 ml-0.5" />
          </div>
        </button>
        
        {/* Duration badge */}
        <div className={`absolute bottom-1 right-1 px-1.5 py-0.5 rounded text-xs font-mono font-medium ${
          isMonetizable ? 'bg-green-500/90' : 'bg-amber-500/90'
        } text-white`}>
          {formatDurationShort(segment.duration)}
        </div>
        
        {/* Score badge */}
        <div className="absolute top-1 right-1">
          <ScoreBadge score={segment.score?.total} size="sm" />
        </div>
      </div>
      
      {/* Info */}
      <div className="p-2 bg-[var(--bg-secondary)]">
        <h4 className="text-xs font-medium text-[var(--text-primary)] truncate">
          {segment.topicLabel || 'Segment'}
        </h4>
        <p className="text-2xs text-[var(--text-muted)]">
          {formatTime(segment.startTime)}
        </p>
      </div>
    </motion.div>
  );
}

function SegmentRowCompact({
  segment,
  isSelected,
  onSelect,
  onPlay,
}: {
  segment: Segment;
  isSelected: boolean;
  onSelect: () => void;
  onPlay: () => void;
}) {
  return (
    <motion.div
      className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${
        isSelected ? 'bg-blue-500/10 border border-blue-500' : 'hover:bg-[var(--bg-secondary)]'
      }`}
      onClick={onSelect}
      layout
    >
      <ScoreBadge score={segment.score.total} size="sm" />
      
      <div className="flex-1 min-w-0">
        <h4 className="text-sm font-medium text-[var(--text-primary)] truncate">
          {segment.topicLabel || 'Segment'}
        </h4>
        <p className="text-xs text-[var(--text-muted)]">
          {formatTime(segment.startTime)} • {formatDurationShort(segment.duration)}
        </p>
      </div>
      
      <button
        className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
        onClick={(e) => {
          e.stopPropagation();
          onPlay();
        }}
      >
        <Play className="w-4 h-4 text-[var(--text-secondary)]" />
      </button>
    </motion.div>
  );
}

function ScoreBadge({ score, size = 'md' }: { score: number | undefined | null; size?: 'sm' | 'md' | 'lg' }) {
  const s = score ?? 0;
  const colors = s >= 70 ? 'bg-green-500' : s >= 50 ? 'bg-amber-500' : 'bg-gray-500';
  const sizes = {
    sm: 'w-6 h-6 text-xs',
    md: 'w-8 h-8 text-sm',
    lg: 'w-12 h-12 text-lg',
  };
  
  return (
    <div className={`${sizes[size]} ${colors} rounded-lg flex items-center justify-center text-white font-bold`}>
      {Math.round(s)}
    </div>
  );
}

function ScoreRow({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-[var(--text-muted)] w-28">{label}</span>
      <div className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber-500 to-green-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs text-[var(--text-secondary)] w-10 text-right">{value}/{max}</span>
    </div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDurationShort(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}
