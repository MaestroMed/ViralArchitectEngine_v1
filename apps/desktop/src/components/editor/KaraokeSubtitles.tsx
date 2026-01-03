import { useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSubtitleStyleStore } from '@/store';

export interface WordTiming {
  word: string;
  start: number;
  end: number;
  confidence?: number;
}

interface KaraokeSubtitlesProps {
  words: WordTiming[];
  currentTime: number;
  clipStartTime: number; // Offset from video start
}

export function KaraokeSubtitles({ words, currentTime, clipStartTime }: KaraokeSubtitlesProps) {
  const { style } = useSubtitleStyleStore();
  
  // Get relative time within clip
  const relativeTime = currentTime - clipStartTime;
  
  // Find visible words (current line - show ~4-6 words at a time)
  const visibleWords = useMemo(() => {
    if (!words.length) return [];
    
    // Find current word index
    const currentIndex = words.findIndex(
      (w) => relativeTime >= w.start && relativeTime < w.end
    );
    
    if (currentIndex === -1) {
      // Before first word or after last word
      const firstWord = words[0];
      if (relativeTime < firstWord.start) return words.slice(0, Math.min(5, words.length));
      return [];
    }
    
    // Show words around current: 2 before, current, 3 after
    const start = Math.max(0, currentIndex - 2);
    const end = Math.min(words.length, currentIndex + 4);
    
    return words.slice(start, end).map((w, i) => ({
      ...w,
      isCurrent: start + i === currentIndex,
      isPast: start + i < currentIndex,
      index: start + i,
    }));
  }, [words, relativeTime]);

  // Position classes
  const positionClass = {
    bottom: 'bottom-12',
    center: 'top-1/2 -translate-y-1/2',
    top: 'top-12',
  }[style.position];

  // Animation variants
  const getAnimationVariants = (animation: string) => {
    switch (animation) {
      case 'pop':
        return {
          initial: { scale: 0.8, opacity: 0 },
          animate: { scale: 1, opacity: 1 },
          current: { scale: 1.25, opacity: 1 },
          exit: { scale: 0.8, opacity: 0 },
        };
      case 'bounce':
        return {
          initial: { y: 20, opacity: 0 },
          animate: { y: 0, opacity: 1 },
          current: { y: -5, opacity: 1 },
          exit: { y: -20, opacity: 0 },
        };
      case 'glow':
        return {
          initial: { opacity: 0.3 },
          animate: { opacity: 0.7 },
          current: { opacity: 1 },
          exit: { opacity: 0 },
        };
      case 'wave':
        return {
          initial: { opacity: 0, y: 10 },
          animate: { opacity: 0.8, y: 0 },
          current: { opacity: 1, y: 0 },
          exit: { opacity: 0, y: -10 },
        };
      default:
        return {
          initial: { opacity: 0 },
          animate: { opacity: 1 },
          current: { opacity: 1 },
          exit: { opacity: 0 },
        };
    }
  };

  const variants = getAnimationVariants(style.animation);

  // Don't render if no words
  if (!visibleWords.length) return null;

  return (
    <div className={`absolute left-4 right-4 ${positionClass} text-center z-20 pointer-events-none`}>
      <motion.div
        className="inline-flex flex-wrap justify-center items-baseline gap-x-2 gap-y-1 px-4 py-3 rounded-xl"
        style={{
          backgroundColor: style.backgroundColor,
          maxWidth: '95%',
        }}
        layout
      >
        <AnimatePresence mode="popLayout">
          {visibleWords.map((wordData) => {
            const { word, isCurrent, isPast, index } = wordData as any;
            
            // Determine state for animation
            const animState = isCurrent ? 'current' : isPast ? 'animate' : 'initial';
            
            // Text shadow for outline effect
            const textShadow = style.outlineWidth > 0
              ? `
                -${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor},
                ${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor},
                -${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor},
                ${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor}
              `
              : 'none';
            
            // Glow effect for current word
            const glowShadow = isCurrent && style.animation === 'glow'
              ? `0 0 20px ${style.highlightColor}, 0 0 40px ${style.highlightColor}60`
              : '';

            return (
              <motion.span
                key={`${index}-${word}`}
                className="inline-block"
                initial={variants.initial}
                animate={isCurrent ? variants.current : variants.animate}
                exit={variants.exit}
                transition={{
                  type: 'spring',
                  stiffness: 500,
                  damping: 30,
                  duration: 0.15,
                }}
                style={{
                  fontFamily: style.fontFamily,
                  fontSize: `${style.fontSize / 2.8}px`, // Scale for preview
                  fontWeight: style.fontWeight,
                  color: isCurrent ? style.highlightColor : (isPast ? style.color : `${style.color}80`),
                  textShadow: `${textShadow}${glowShadow ? ', ' + glowShadow : ''}`,
                  lineHeight: 1.3,
                  letterSpacing: '0.02em',
                }}
              >
                {word}
              </motion.span>
            );
          })}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}

// Helper to parse transcript into word timings (if not provided by backend)
export function parseTranscriptToWords(transcript: string, duration: number): WordTiming[] {
  const words = transcript.split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  
  const avgWordDuration = duration / words.length;
  
  return words.map((word, i) => ({
    word,
    start: i * avgWordDuration,
    end: (i + 1) * avgWordDuration,
    confidence: 1,
  }));
}

export default KaraokeSubtitles;

