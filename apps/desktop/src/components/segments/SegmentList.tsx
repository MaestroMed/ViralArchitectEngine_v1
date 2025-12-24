import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Filter, SortAsc, SortDesc, Clock, Zap, Grid, List } from 'lucide-react';
import { SegmentCard } from './SegmentCard';

interface Segment {
  id: string;
  start_time: number;
  end_time: number;
  duration: number;
  transcript?: string;
  topic_label?: string;
  hook_text?: string;
  score?: {
    total: number;
    hook_strength: number;
    payoff: number;
    reasons: string[];
    tags: string[];
  };
}

interface SegmentListProps {
  segments: Segment[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  onPlay: (segment: Segment) => void;
  onEdit: (segment: Segment) => void;
}

type SortOption = 'score' | 'duration' | 'time';
type FilterOption = 'all' | 'monetizable' | 'high-score';
type ViewMode = 'grid' | 'list';

export function SegmentList({
  segments,
  selectedId,
  onSelect,
  onPlay,
  onEdit,
}: SegmentListProps) {
  const [sortBy, setSortBy] = useState<SortOption>('score');
  const [sortDesc, setSortDesc] = useState(true);
  const [filter, setFilter] = useState<FilterOption>('all');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');

  // Filter segments
  let filtered = [...segments];
  if (filter === 'monetizable') {
    filtered = filtered.filter((s) => s.duration >= 60);
  } else if (filter === 'high-score') {
    filtered = filtered.filter((s) => (s.score?.total || 0) >= 60);
  }

  // Sort segments
  filtered.sort((a, b) => {
    let diff = 0;
    if (sortBy === 'score') {
      diff = (a.score?.total || 0) - (b.score?.total || 0);
    } else if (sortBy === 'duration') {
      diff = a.duration - b.duration;
    } else {
      diff = a.start_time - b.start_time;
    }
    return sortDesc ? -diff : diff;
  });

  const stats = {
    total: segments.length,
    monetizable: segments.filter((s) => s.duration >= 60).length,
    highScore: segments.filter((s) => (s.score?.total || 0) >= 60).length,
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border-color)]">
        <div>
          <h3 className="font-semibold text-[var(--text-primary)]">Segments détectés</h3>
          <p className="text-xs text-[var(--text-muted)]">
            {stats.total} segments • {stats.monetizable} monétisables • {stats.highScore} haute viralité
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex items-center bg-[var(--bg-tertiary)] rounded-lg p-1">
            <button
              className={`p-1.5 rounded ${viewMode === 'grid' ? 'bg-[var(--bg-card)]' : ''}`}
              onClick={() => setViewMode('grid')}
            >
              <Grid className="w-4 h-4 text-[var(--text-secondary)]" />
            </button>
            <button
              className={`p-1.5 rounded ${viewMode === 'list' ? 'bg-[var(--bg-card)]' : ''}`}
              onClick={() => setViewMode('list')}
            >
              <List className="w-4 h-4 text-[var(--text-secondary)]" />
            </button>
          </div>
        </div>
      </div>

      {/* Filters bar */}
      <div className="flex items-center gap-2 p-3 border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
        {/* Filter pills */}
        <div className="flex items-center gap-1">
          <FilterPill
            active={filter === 'all'}
            onClick={() => setFilter('all')}
          >
            Tous
          </FilterPill>
          <FilterPill
            active={filter === 'monetizable'}
            onClick={() => setFilter('monetizable')}
            icon={<Clock className="w-3 h-3" />}
          >
            ≥ 1 min
          </FilterPill>
          <FilterPill
            active={filter === 'high-score'}
            onClick={() => setFilter('high-score')}
            icon={<Zap className="w-3 h-3" />}
          >
            Score 60+
          </FilterPill>
        </div>

        <div className="flex-1" />

        {/* Sort */}
        <div className="flex items-center gap-1">
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            className="text-xs bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg px-2 py-1.5 text-[var(--text-secondary)]"
          >
            <option value="score">Score viral</option>
            <option value="duration">Durée</option>
            <option value="time">Chronologique</option>
          </select>
          <button
            className="p-1.5 rounded-lg hover:bg-[var(--bg-card)] transition-colors"
            onClick={() => setSortDesc(!sortDesc)}
          >
            {sortDesc ? (
              <SortDesc className="w-4 h-4 text-[var(--text-secondary)]" />
            ) : (
              <SortAsc className="w-4 h-4 text-[var(--text-secondary)]" />
            )}
          </button>
        </div>
      </div>

      {/* Segment grid/list */}
      <div className="flex-1 overflow-auto p-4">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Filter className="w-12 h-12 text-[var(--text-muted)] opacity-30 mb-4" />
            <p className="text-[var(--text-muted)]">Aucun segment ne correspond aux filtres</p>
          </div>
        ) : viewMode === 'grid' ? (
          <motion.div
            className="grid grid-cols-2 xl:grid-cols-3 gap-4"
            layout
          >
            <AnimatePresence>
              {filtered.map((segment) => (
                <SegmentCard
                  key={segment.id}
                  segment={segment}
                  isSelected={selectedId === segment.id}
                  onSelect={() => onSelect(segment.id)}
                  onPlay={() => onPlay(segment)}
                  onEdit={() => onEdit(segment)}
                />
              ))}
            </AnimatePresence>
          </motion.div>
        ) : (
          <div className="space-y-2">
            <AnimatePresence>
              {filtered.map((segment) => (
                <SegmentListItem
                  key={segment.id}
                  segment={segment}
                  isSelected={selectedId === segment.id}
                  onSelect={() => onSelect(segment.id)}
                  onPlay={() => onPlay(segment)}
                  onEdit={() => onEdit(segment)}
                />
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}

function FilterPill({
  active,
  onClick,
  icon,
  children,
}: {
  active: boolean;
  onClick: () => void;
  icon?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <button
      className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
        active
          ? 'bg-[var(--accent)] text-white'
          : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
      }`}
      onClick={onClick}
    >
      {icon}
      {children}
    </button>
  );
}

function SegmentListItem({
  segment,
  isSelected,
  onSelect,
  onPlay,
  onEdit,
}: {
  segment: Segment;
  isSelected: boolean;
  onSelect: () => void;
  onPlay: () => void;
  onEdit: () => void;
}) {
  const score = segment.score?.total || 0;
  const isMonetizable = segment.duration >= 60;

  return (
    <motion.div
      className={`flex items-center gap-4 p-3 rounded-lg cursor-pointer transition-colors ${
        isSelected
          ? 'bg-blue-500/10 border border-blue-500'
          : 'bg-[var(--bg-card)] border border-[var(--border-color)] hover:bg-[var(--bg-secondary)]'
      }`}
      onClick={onSelect}
      layout
    >
      {/* Score */}
      <div
        className={`w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm ${
          score >= 70
            ? 'bg-green-500/10 text-green-500'
            : score >= 50
            ? 'bg-amber-500/10 text-amber-500'
            : 'bg-gray-500/10 text-gray-400'
        }`}
      >
        {score}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[var(--text-primary)] truncate">
            {segment.topic_label || 'Segment'}
          </span>
          {!isMonetizable && (
            <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-500 text-xs rounded">
              &lt; 1 min
            </span>
          )}
        </div>
        <div className="text-xs text-[var(--text-muted)]">
          {formatTime(segment.start_time)} → {formatTime(segment.end_time)} ({formatDuration(segment.duration)})
        </div>
      </div>

      {/* Tags */}
      <div className="hidden md:flex items-center gap-1">
        {segment.score?.tags?.slice(0, 2).map((tag) => (
          <span
            key={tag}
            className="px-1.5 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-muted)] text-xs rounded capitalize"
          >
            {tag}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1">
        <button
          className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            onPlay();
          }}
        >
          <Play className="w-4 h-4 text-[var(--text-secondary)]" />
        </button>
        <button
          className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
          onClick={(e) => {
            e.stopPropagation();
            onEdit();
          }}
        >
          <Scissors className="w-4 h-4 text-[var(--text-secondary)]" />
        </button>
      </div>
    </motion.div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

interface Segment {
  id: string;
  start_time: number;
  end_time: number;
  duration: number;
  transcript?: string;
  topic_label?: string;
  hook_text?: string;
  score?: {
    total: number;
    hook_strength: number;
    payoff: number;
    tension_surprise?: number;
    humour_reaction?: number;
    reasons: string[];
    tags: string[];
  };
}








