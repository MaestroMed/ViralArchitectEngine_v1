import { useState, useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Edit2, Check, X, Clock, Play, AlertTriangle } from 'lucide-react';

interface Word {
  word: string;
  start: number;
  end: number;
  confidence?: number;
}

interface TranscriptEditorProps {
  words: Word[];
  currentTime: number;
  onWordUpdate: (index: number, word: string) => void;
  onTimingUpdate: (index: number, start: number, end: number) => void;
  onSeek: (time: number) => void;
}

export function TranscriptEditor({
  words,
  currentTime,
  onWordUpdate,
  onTimingUpdate,
  onSeek,
}: TranscriptEditorProps) {
  const [editingIndex, setEditingIndex] = useState<number | null>(null);
  const [editValue, setEditValue] = useState('');
  const [editingTiming, setEditingTiming] = useState<number | null>(null);
  const [timingValues, setTimingValues] = useState({ start: 0, end: 0 });
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to current word
  useEffect(() => {
    if (!containerRef.current) return;
    const currentWordIndex = words.findIndex(
      (w) => currentTime >= w.start && currentTime < w.end
    );
    if (currentWordIndex >= 0) {
      const wordEl = containerRef.current.querySelector(`[data-word-index="${currentWordIndex}"]`);
      if (wordEl) {
        wordEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [currentTime, words]);

  const handleStartEdit = (index: number) => {
    setEditingIndex(index);
    setEditValue(words[index].word);
  };

  const handleSaveEdit = () => {
    if (editingIndex !== null) {
      onWordUpdate(editingIndex, editValue);
      setEditingIndex(null);
    }
  };

  const handleCancelEdit = () => {
    setEditingIndex(null);
    setEditValue('');
  };

  const handleStartTimingEdit = (index: number) => {
    setEditingTiming(index);
    setTimingValues({ start: words[index].start, end: words[index].end });
  };

  const handleSaveTiming = () => {
    if (editingTiming !== null) {
      onTimingUpdate(editingTiming, timingValues.start, timingValues.end);
      setEditingTiming(null);
    }
  };

  const isCurrentWord = useCallback(
    (word: Word) => currentTime >= word.start && currentTime < word.end,
    [currentTime]
  );

  const isLowConfidence = (word: Word) => (word.confidence || 1) < 0.7;

  return (
    <div className="h-full flex flex-col bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)]">
      {/* Header */}
      <div className="flex items-center justify-between p-4 border-b border-[var(--border-color)]">
        <div>
          <h3 className="font-semibold text-[var(--text-primary)]">Éditeur de transcription</h3>
          <p className="text-xs text-[var(--text-muted)]">{words.length} mots • Cliquez pour éditer</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-[var(--text-muted)]">
          <span className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-blue-500" /> Mot actuel
          </span>
          <span className="flex items-center gap-1">
            <div className="w-2 h-2 rounded-full bg-amber-500" /> Confiance faible
          </span>
        </div>
      </div>

      {/* Words grid */}
      <div ref={containerRef} className="flex-1 overflow-auto p-4">
        <div className="flex flex-wrap gap-1">
          {words.map((word, index) => {
            const isCurrent = isCurrentWord(word);
            const isLow = isLowConfidence(word);
            const isEditing = editingIndex === index;
            const isEditingTime = editingTiming === index;

            return (
              <motion.div
                key={index}
                data-word-index={index}
                className={`relative group ${isCurrent ? 'z-10' : ''}`}
                layout
              >
                {isEditing ? (
                  <div className="flex items-center gap-1 bg-blue-500/20 border border-blue-500 rounded-lg p-1">
                    <input
                      type="text"
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSaveEdit();
                        if (e.key === 'Escape') handleCancelEdit();
                      }}
                      className="bg-transparent border-none outline-none text-sm w-24 text-[var(--text-primary)]"
                      autoFocus
                    />
                    <button onClick={handleSaveEdit} className="p-1 hover:bg-green-500/20 rounded">
                      <Check className="w-3 h-3 text-green-500" />
                    </button>
                    <button onClick={handleCancelEdit} className="p-1 hover:bg-red-500/20 rounded">
                      <X className="w-3 h-3 text-red-500" />
                    </button>
                  </div>
                ) : isEditingTime ? (
                  <div className="flex flex-col gap-1 bg-purple-500/20 border border-purple-500 rounded-lg p-2">
                    <span className="text-xs font-medium text-[var(--text-primary)]">{word.word}</span>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        step="0.01"
                        value={timingValues.start.toFixed(2)}
                        onChange={(e) => setTimingValues({ ...timingValues, start: parseFloat(e.target.value) })}
                        className="w-16 bg-transparent border border-white/20 rounded px-1 text-xs text-[var(--text-primary)]"
                      />
                      <span className="text-xs text-[var(--text-muted)]">→</span>
                      <input
                        type="number"
                        step="0.01"
                        value={timingValues.end.toFixed(2)}
                        onChange={(e) => setTimingValues({ ...timingValues, end: parseFloat(e.target.value) })}
                        className="w-16 bg-transparent border border-white/20 rounded px-1 text-xs text-[var(--text-primary)]"
                      />
                    </div>
                    <div className="flex gap-1">
                      <button onClick={handleSaveTiming} className="flex-1 p-1 bg-purple-500 rounded text-xs">
                        OK
                      </button>
                      <button onClick={() => setEditingTiming(null)} className="flex-1 p-1 bg-white/10 rounded text-xs">
                        ✕
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => onSeek(word.start)}
                    onDoubleClick={() => handleStartEdit(index)}
                    className={`
                      px-2 py-1 rounded-lg text-sm transition-all cursor-pointer
                      ${isCurrent 
                        ? 'bg-blue-500 text-white scale-110 shadow-lg' 
                        : isLow 
                          ? 'bg-amber-500/20 text-amber-400 border border-amber-500/30' 
                          : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]'
                      }
                    `}
                  >
                    {word.word}
                    
                    {/* Hover actions */}
                    <div className="absolute -top-8 left-1/2 -translate-x-1/2 hidden group-hover:flex items-center gap-1 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg p-1 shadow-lg z-20">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartEdit(index);
                        }}
                        className="p-1 hover:bg-blue-500/20 rounded"
                        title="Éditer le mot"
                      >
                        <Edit2 className="w-3 h-3 text-blue-400" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartTimingEdit(index);
                        }}
                        className="p-1 hover:bg-purple-500/20 rounded"
                        title="Ajuster le timing"
                      >
                        <Clock className="w-3 h-3 text-purple-400" />
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSeek(word.start);
                        }}
                        className="p-1 hover:bg-green-500/20 rounded"
                        title="Aller à ce mot"
                      >
                        <Play className="w-3 h-3 text-green-400" />
                      </button>
                    </div>
                    
                    {/* Low confidence indicator */}
                    {isLow && (
                      <AlertTriangle className="absolute -top-1 -right-1 w-3 h-3 text-amber-500" />
                    )}
                  </button>
                )}
              </motion.div>
            );
          })}
        </div>
      </div>

      {/* Footer with tips */}
      <div className="p-3 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <p className="text-xs text-[var(--text-muted)]">
          💡 <strong>Double-clic</strong> pour éditer un mot • <strong>Clic</strong> pour aller à ce moment
        </p>
      </div>
    </div>
  );
}

export default TranscriptEditor;





