import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Filter, 
  ChevronDown, 
  ChevronUp, 
  RotateCcw,
  Zap,
  Clock,
  TrendingUp,
  Search,
  X,
  Tag,
} from 'lucide-react';

interface SegmentStats {
  total: number;
  avgScore: number;
  maxScore: number;
  minScore: number;
  avgDuration: number;
  maxDuration: number;
  minDuration: number;
  scoreDistribution: number[];
  durationDistribution: number[];
  monetizable: number;
  highScore: number;
}

interface FilterState {
  minScore: number;
  minDuration: number;
  maxDuration: number;
  limit: number | null;
  search?: string;
  tags?: string[];
}

interface SegmentFilterBarProps {
  stats: SegmentStats | null;
  filters: FilterState;
  onFiltersChange: (filters: FilterState) => void;
  filteredCount: number;
  loading?: boolean;
  availableTags?: string[];
  onSearchChange?: (search: string) => void;
  onTagsChange?: (tags: string[]) => void;
}

const LIMIT_PRESETS = [
  { label: 'Top 10', value: 10 },
  { label: 'Top 25', value: 25 },
  { label: 'Top 50', value: 50 },
  { label: 'Tous', value: null },
];

// Debounce hook
function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}

export function SegmentFilterBar({
  stats,
  filters,
  onFiltersChange,
  filteredCount,
  loading = false,
  availableTags = [],
  onSearchChange,
  onTagsChange,
}: SegmentFilterBarProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  const [searchInput, setSearchInput] = useState(filters.search || '');
  const [selectedTags, setSelectedTags] = useState<string[]>(filters.tags || []);
  
  // Debounce search input
  const debouncedSearch = useDebounce(searchInput, 300);
  
  // Notify parent when debounced search changes
  useEffect(() => {
    if (onSearchChange) {
      onSearchChange(debouncedSearch);
    }
  }, [debouncedSearch, onSearchChange]);
  
  // Notify parent when tags change
  useEffect(() => {
    if (onTagsChange) {
      onTagsChange(selectedTags);
    }
  }, [selectedTags, onTagsChange]);

  const handleReset = () => {
    setSearchInput('');
    setSelectedTags([]);
    onFiltersChange({
      minScore: 0,
      minDuration: 0,
      maxDuration: 600,
      limit: null,
      search: '',
      tags: [],
    });
  };

  const toggleTag = (tag: string) => {
    setSelectedTags(prev => 
      prev.includes(tag) 
        ? prev.filter(t => t !== tag)
        : [...prev, tag]
    );
  };

  const hasActiveFilters = 
    filters.minScore > 0 || 
    filters.minDuration > 0 || 
    filters.maxDuration < 600 ||
    filters.limit !== null ||
    searchInput.length > 0 ||
    selectedTags.length > 0;

  return (
    <div className="border-b border-[var(--border-color)] bg-[var(--bg-secondary)]">
      {/* Compact Header */}
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-3">
          {/* Stats summary */}
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium text-[var(--text-primary)]">
              {loading ? '...' : filteredCount}
            </span>
            <span className="text-xs text-[var(--text-muted)]">
              / {stats?.total ?? 0}
            </span>
          </div>

          {/* Quick stats badges - hidden on small screens */}
          {stats && (
            <div className="hidden lg:flex items-center gap-2">
              <span className="flex items-center gap-1 px-2 py-0.5 bg-green-500/10 text-green-500 text-xs rounded-full">
                <TrendingUp aria-hidden="true" className="w-3 h-3" />
                {stats.avgScore.toFixed(0)}
              </span>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Reset button */}
          {hasActiveFilters && (
            <button
              onClick={handleReset}
              aria-label="Réinitialiser les filtres"
              className="p-1.5 rounded-lg hover:bg-[var(--bg-tertiary)] text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
              title="Réinitialiser les filtres"
            >
              <RotateCcw aria-hidden="true" className="w-4 h-4" />
            </button>
          )}

          {/* Expand toggle */}
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label="Filtres"
            aria-expanded={isExpanded}
            className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              hasActiveFilters
                ? 'bg-blue-500/10 text-blue-500'
                : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-card)]'
            }`}
          >
            <Filter aria-hidden="true" className="w-3.5 h-3.5" />
            {isExpanded ? (
              <ChevronUp aria-hidden="true" className="w-3.5 h-3.5" />
            ) : (
              <ChevronDown aria-hidden="true" className="w-3.5 h-3.5" />
            )}
          </button>
        </div>
      </div>

      {/* Expanded Filter Panel */}
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 space-y-3">
              {/* Search Input */}
              <div className="relative">
                <Search aria-hidden="true" className="absolute left-2.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                <input
                  type="text"
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  placeholder="Rechercher dans la transcription..."
                  aria-label="Rechercher dans la transcription"
                  className="w-full pl-8 pr-8 py-2 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                />
                {searchInput && (
                  <button
                    onClick={() => setSearchInput('')}
                    aria-label="Effacer la recherche"
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 p-0.5 rounded hover:bg-[var(--bg-tertiary)]"
                  >
                    <X aria-hidden="true" className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                  </button>
                )}
              </div>

              {/* Score Distribution Visualization */}
              {stats && (
                <div className="flex items-end gap-0.5 h-8">
                  {stats.scoreDistribution.map((count, i) => {
                    const maxCount = Math.max(...stats.scoreDistribution, 1);
                    const height = (count / maxCount) * 100;
                    const labels = ['0-20', '20-40', '40-60', '60-80', '80-100'];
                    const colors = [
                      'bg-gray-400',
                      'bg-orange-400',
                      'bg-amber-400',
                      'bg-lime-400',
                      'bg-green-500',
                    ];
                    return (
                      <div
                        key={i}
                        className="flex-1 flex flex-col items-center group relative"
                      >
                        <div
                          className={`w-full rounded-t ${colors[i]} transition-all`}
                          style={{ height: `${Math.max(height, 4)}%` }}
                        />
                        <span className="text-[9px] text-[var(--text-muted)] mt-0.5">
                          {labels[i]}
                        </span>
                        <div className="absolute bottom-full mb-1 hidden group-hover:block px-1.5 py-0.5 bg-black/80 text-white text-[10px] rounded whitespace-nowrap z-10">
                          {count} segments
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Score Slider */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-[var(--text-secondary)]">
                    Score minimum
                  </label>
                  <span className="text-xs font-mono text-[var(--text-primary)]">
                    {filters.minScore}+
                  </span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={100}
                  step={5}
                  value={filters.minScore}
                  onChange={(e) =>
                    onFiltersChange({ ...filters, minScore: parseInt(e.target.value) })
                  }
                  aria-label="Score minimum"
                  className="w-full h-1.5 bg-[var(--bg-tertiary)] rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
              </div>

              {/* Duration Range */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1">
                    <Clock aria-hidden="true" className="w-3 h-3" />
                    Durée
                  </label>
                  <span className="text-xs font-mono text-[var(--text-primary)]">
                    {formatDuration(filters.minDuration)} - {formatDuration(filters.maxDuration)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={300}
                    step={15}
                    value={filters.minDuration}
                    onChange={(e) =>
                      onFiltersChange({
                        ...filters,
                        minDuration: Math.min(parseInt(e.target.value), filters.maxDuration - 15),
                      })
                    }
                    aria-label="Durée minimum"
                    className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                  <span className="text-[10px] text-[var(--text-muted)]">-</span>
                  <input
                    type="range"
                    min={30}
                    max={600}
                    step={30}
                    value={filters.maxDuration}
                    onChange={(e) =>
                      onFiltersChange({
                        ...filters,
                        maxDuration: Math.max(parseInt(e.target.value), filters.minDuration + 15),
                      })
                    }
                    aria-label="Durée maximum"
                    className="flex-1 h-1.5 bg-[var(--bg-tertiary)] rounded-lg appearance-none cursor-pointer accent-blue-500"
                  />
                </div>
              </div>

              {/* Tag Filters */}
              {availableTags.length > 0 && (
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-[var(--text-secondary)] flex items-center gap-1">
                    <Tag aria-hidden="true" className="w-3 h-3" />
                    Tags
                  </label>
                  <div className="flex flex-wrap gap-1">
                    {availableTags.slice(0, 12).map((tag) => (
                      <button
                        key={tag}
                        onClick={() => toggleTag(tag)}
                        aria-pressed={selectedTags.includes(tag)}
                        aria-label={`Filtrer par le tag ${tag}`}
                        className={`px-2 py-0.5 rounded-full text-xs font-medium transition-colors capitalize ${
                          selectedTags.includes(tag)
                            ? 'bg-blue-500 text-white'
                            : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
                        }`}
                      >
                        {tag}
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {/* Limit Presets */}
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-[var(--text-secondary)]">
                  Afficher
                </label>
                <div className="flex flex-wrap gap-1.5">
                  {LIMIT_PRESETS.map((preset) => (
                    <button
                      key={preset.label}
                      onClick={() => onFiltersChange({ ...filters, limit: preset.value })}
                      aria-pressed={filters.limit === preset.value}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                        filters.limit === preset.value
                          ? 'bg-blue-500 text-white'
                          : 'bg-[var(--bg-card)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
                      }`}
                    >
                      {preset.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Quick Filters */}
              <div className="flex flex-wrap gap-1.5 pt-2 border-t border-[var(--border-color)]">
                <button
                  onClick={() => onFiltersChange({ ...filters, minScore: 60, minDuration: 60 })}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-green-500/10 text-green-500 hover:bg-green-500/20 transition-colors"
                >
                  <Zap aria-hidden="true" className="w-3 h-3" />
                  Viraux (60+)
                </button>
                <button
                  onClick={() => onFiltersChange({ ...filters, minScore: 70, limit: 10 })}
                  className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-500 hover:bg-amber-500/20 transition-colors"
                >
                  <TrendingUp aria-hidden="true" className="w-3 h-3" />
                  Top 10
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

function formatDuration(seconds: number): string {
  if (seconds < 60) {
    return `${seconds}s`;
  }
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return secs > 0 ? `${mins}m${secs}s` : `${mins}m`;
}

export type { FilterState, SegmentStats };
