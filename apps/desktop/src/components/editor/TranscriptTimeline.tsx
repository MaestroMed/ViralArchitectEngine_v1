import { useState, useRef, useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Edit2, Check, X } from 'lucide-react';

interface Word {
  word: string;
  start: number;
  end: number;
  confidence?: number;
}

interface Segment {
  id: number;
  start: number;
  end: number;
  text: string;
  words?: Word[];
}

interface TranscriptTimelineProps {
  segments: Segment[];
  currentTime: number;
  trimStart?: number;
  trimEnd?: number;
  onSeek: (time: number) => void;
  onWordEdit?: (segmentId: number, wordIndex: number, newWord: string) => void;
}

export default function TranscriptTimeline({
  segments,
  currentTime,
  trimStart = 0,
  trimEnd,
  onSeek,
  onWordEdit,
}: TranscriptTimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [editingWord, setEditingWord] = useState<{
    segmentId: number;
    wordIndex: number;
    text: string;
  } | null>(null);

  // Flatten all words with segment info
  const allWords = useMemo(() => {
    const words: (Word & { segmentId: number; wordIndex: number })[] = [];
    segments.forEach((segment) => {
      if (segment.words) {
        segment.words.forEach((word, idx) => {
          words.push({
            ...word,
            segmentId: segment.id,
            wordIndex: idx,
          });
        });
      } else {
        // If no word-level timestamps, create from segment
        const segmentWords = segment.text.split(' ').filter(Boolean);
        const duration = segment.end - segment.start;
        const wordDuration = duration / segmentWords.length;
        segmentWords.forEach((word, idx) => {
          words.push({
            word,
            start: segment.start + idx * wordDuration,
            end: segment.start + (idx + 1) * wordDuration,
            segmentId: segment.id,
            wordIndex: idx,
          });
        });
      }
    });
    return words;
  }, [segments]);

  // Filter words within trim range
  const visibleWords = useMemo(() => {
    return allWords.filter((word) => {
      const effectiveEnd = trimEnd ?? Infinity;
      return word.start >= trimStart && word.end <= effectiveEnd;
    });
  }, [allWords, trimStart, trimEnd]);

  // Find current word
  const currentWordIndex = useMemo(() => {
    return visibleWords.findIndex(
      (word) => currentTime >= word.start && currentTime < word.end
    );
  }, [visibleWords, currentTime]);

  // Auto-scroll to current word
  useEffect(() => {
    if (currentWordIndex >= 0 && containerRef.current) {
      const wordElements = containerRef.current.querySelectorAll('[data-word]');
      const currentWordEl = wordElements[currentWordIndex] as HTMLElement;
      if (currentWordEl) {
        currentWordEl.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'center',
        });
      }
    }
  }, [currentWordIndex]);

  const handleWordClick = (word: typeof visibleWords[0]) => {
    onSeek(word.start);
  };

  const handleWordDoubleClick = (word: typeof visibleWords[0]) => {
    if (onWordEdit) {
      setEditingWord({
        segmentId: word.segmentId,
        wordIndex: word.wordIndex,
        text: word.word,
      });
    }
  };

  const handleEditSubmit = () => {
    if (editingWord && onWordEdit) {
      onWordEdit(editingWord.segmentId, editingWord.wordIndex, editingWord.text);
    }
    setEditingWord(null);
  };

  const handleEditCancel = () => {
    setEditingWord(null);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[var(--border-color)]">
        <h4 className="text-sm font-medium text-[var(--text-primary)]">Transcription</h4>
        <span className="text-xs text-[var(--text-muted)]">
          {visibleWords.length} mots • Double-clic pour éditer
        </span>
      </div>

      {/* Words container */}
      <div
        ref={containerRef}
        className="flex-1 overflow-auto p-4 scrollbar-thin"
      >
        <div className="flex flex-wrap gap-1.5 leading-relaxed">
          {visibleWords.map((word, index) => {
            const isCurrentWord = index === currentWordIndex;
            const isEditing =
              editingWord?.segmentId === word.segmentId &&
              editingWord?.wordIndex === word.wordIndex;
            const isPast = currentTime > word.end;

            return (
              <motion.span
                key={`${word.segmentId}-${word.wordIndex}`}
                data-word
                initial={false}
                animate={{
                  scale: isCurrentWord ? 1.05 : 1,
                  backgroundColor: isCurrentWord
                    ? 'rgba(16, 185, 129, 0.2)'
                    : 'transparent',
                }}
                className={`
                  relative px-1.5 py-0.5 rounded cursor-pointer select-none transition-colors
                  ${isCurrentWord
                    ? 'text-[var(--accent-color)] font-medium ring-1 ring-[var(--accent-color)]'
                    : isPast
                    ? 'text-[var(--text-muted)]'
                    : 'text-[var(--text-primary)] hover:bg-[var(--bg-tertiary)]'
                  }
                  ${word.confidence && word.confidence < 0.8 ? 'border-b border-dashed border-amber-500' : ''}
                `}
                onClick={() => handleWordClick(word)}
                onDoubleClick={() => handleWordDoubleClick(word)}
              >
                {isEditing ? (
                  <span className="inline-flex items-center gap-1">
                    <input
                      type="text"
                      value={editingWord.text}
                      onChange={(e) =>
                        setEditingWord({ ...editingWord, text: e.target.value })
                      }
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleEditSubmit();
                        if (e.key === 'Escape') handleEditCancel();
                      }}
                      className="w-auto min-w-[40px] px-1 py-0.5 bg-[var(--bg-card)] border border-[var(--accent-color)] rounded text-sm focus:outline-none"
                      autoFocus
                      onClick={(e) => e.stopPropagation()}
                    />
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditSubmit();
                      }}
                      className="p-0.5 hover:bg-green-500/20 rounded"
                    >
                      <Check className="w-3 h-3 text-green-500" />
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleEditCancel();
                      }}
                      className="p-0.5 hover:bg-red-500/20 rounded"
                    >
                      <X className="w-3 h-3 text-red-500" />
                    </button>
                  </span>
                ) : (
                  word.word
                )}
              </motion.span>
            );
          })}
        </div>

        {visibleWords.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center py-8">
            <Edit2 className="w-8 h-8 text-[var(--text-muted)] opacity-30 mb-2" />
            <p className="text-sm text-[var(--text-muted)]">
              Aucune transcription disponible
            </p>
          </div>
        )}
      </div>

      {/* Timeline progress bar */}
      <div className="h-1 bg-[var(--bg-tertiary)]">
        <motion.div
          className="h-full bg-gradient-viral"
          initial={false}
          animate={{
            width: `${
              trimEnd
                ? ((currentTime - trimStart) / (trimEnd - trimStart)) * 100
                : 0
            }%`,
          }}
          transition={{ duration: 0.1 }}
        />
      </div>
    </div>
  );
}




