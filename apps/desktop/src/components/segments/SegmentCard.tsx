import { motion } from 'framer-motion';
import { Play, Clock, Zap, MessageSquare, Scissors, Star } from 'lucide-react';

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

interface SegmentCardProps {
  segment: Segment;
  isSelected: boolean;
  thumbnailUrl?: string;
  onSelect: () => void;
  onPlay: () => void;
  onEdit: () => void;
}

export function SegmentCard({
  segment,
  isSelected,
  thumbnailUrl,
  onSelect,
  onPlay,
  onEdit,
}: SegmentCardProps) {
  const score = segment.score?.total || 0;
  const duration = segment.duration;
  const isMonetizable = duration >= 60;

  const scoreColor = score >= 70 ? 'text-green-500' : score >= 50 ? 'text-amber-500' : 'text-gray-400';
  const scoreBg = score >= 70 ? 'bg-green-500/10' : score >= 50 ? 'bg-amber-500/10' : 'bg-gray-500/10';

  return (
    <motion.div
      className={`relative rounded-xl overflow-hidden cursor-pointer transition-all ${
        isSelected
          ? 'ring-2 ring-blue-500 bg-[var(--bg-card)]'
          : 'bg-[var(--bg-card)] hover:bg-[var(--bg-secondary)]'
      }`}
      style={{ border: '1px solid var(--border-color)' }}
      onClick={onSelect}
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      layout
    >
      {/* Thumbnail area */}
      <div className="relative aspect-video bg-gray-900">
        {thumbnailUrl ? (
          <img src={thumbnailUrl} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-600">
            <Play className="w-8 h-8" />
          </div>
        )}

        {/* Duration badge */}
        <div
          className={`absolute bottom-2 right-2 px-2 py-0.5 rounded text-xs font-mono font-medium ${
            isMonetizable ? 'bg-green-500/90 text-white' : 'bg-amber-500/90 text-white'
          }`}
        >
          {formatDuration(duration)}
        </div>

        {/* Play button overlay */}
        <button
          className="absolute inset-0 flex items-center justify-center bg-black/0 hover:bg-black/30 transition-colors group"
          onClick={(e) => {
            e.stopPropagation();
            onPlay();
          }}
        >
          <div className="w-12 h-12 bg-white/90 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
            <Play className="w-5 h-5 text-gray-900 ml-1" />
          </div>
        </button>

        {/* Score badge */}
        <div
          className={`absolute top-2 right-2 px-2 py-1 rounded-lg ${scoreBg} flex items-center gap-1`}
        >
          <Zap className={`w-3 h-3 ${scoreColor}`} />
          <span className={`text-sm font-bold ${scoreColor}`}>{score}</span>
        </div>

        {/* Not monetizable warning */}
        {!isMonetizable && (
          <div className="absolute top-2 left-2 px-2 py-1 bg-amber-500/90 rounded text-xs text-white flex items-center gap-1">
            <Clock className="w-3 h-3" />
            <span>&lt; 1 min</span>
          </div>
        )}
      </div>

      {/* Content */}
      <div className="p-3">
        {/* Topic label */}
        <h4 className="font-medium text-[var(--text-primary)] text-sm line-clamp-1 mb-1">
          {segment.topic_label || 'Segment'}
        </h4>

        {/* Hook text */}
        {segment.hook_text && (
          <p className="text-xs text-[var(--text-muted)] line-clamp-2 mb-2 italic">
            "{segment.hook_text}"
          </p>
        )}

        {/* Tags */}
        {segment.score?.tags && segment.score.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-2">
            {segment.score.tags.slice(0, 3).map((tag) => (
              <span
                key={tag}
                className="px-1.5 py-0.5 bg-[var(--bg-tertiary)] text-[var(--text-muted)] text-xs rounded capitalize"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Score breakdown */}
        <div className="grid grid-cols-3 gap-1 mb-2">
          <ScoreMini label="Hook" value={segment.score?.hook_strength || 0} max={25} />
          <ScoreMini label="Payoff" value={segment.score?.payoff || 0} max={20} />
          <ScoreMini label="Énergie" value={(segment.score?.tension_surprise || 0) + (segment.score?.humour_reaction || 0)} max={30} />
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2 pt-2 border-t border-[var(--border-color)]">
          <button
            className="flex-1 flex items-center justify-center gap-1 py-1.5 rounded-lg bg-[var(--bg-tertiary)] hover:bg-[var(--accent)] hover:text-white transition-colors text-xs"
            onClick={(e) => {
              e.stopPropagation();
              onEdit();
            }}
          >
            <Scissors className="w-3 h-3" />
            Éditer
          </button>
          <button
            className="flex items-center justify-center p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            onClick={(e) => e.stopPropagation()}
          >
            <Star className="w-4 h-4 text-[var(--text-muted)]" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

function ScoreMini({ label, value, max }: { label: string; value: number; max: number }) {
  const pct = (value / max) * 100;
  return (
    <div className="text-center">
      <div className="text-xs text-[var(--text-muted)] mb-0.5">{label}</div>
      <div className="h-1 bg-[var(--bg-tertiary)] rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-amber-500 to-green-500 transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}








