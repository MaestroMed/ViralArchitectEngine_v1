import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Volume2, VolumeX, Music, ChevronUp } from 'lucide-react';
import { useAmbientAudioStore, AmbientTrack } from '@/store';

const TRACK_LABELS: Record<AmbientTrack, string> = {
  westworld: 'Westworld',
  minimal: 'Minimal',
  deep: 'Deep',
  none: 'Off',
};

export default function AudioControls() {
  const { enabled, volume, track, toggleEnabled, setVolume, setTrack } = useAmbientAudioStore();
  const [showPopup, setShowPopup] = useState(false);
  const popupRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  
  // Close popup on click outside
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (
        popupRef.current && 
        buttonRef.current &&
        !popupRef.current.contains(e.target as Node) &&
        !buttonRef.current.contains(e.target as Node)
      ) {
        setShowPopup(false);
      }
    };
    
    if (showPopup) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showPopup]);
  
  return (
    <div className="relative">
      {/* Toggle button */}
      <button
        ref={buttonRef}
        onClick={toggleEnabled}
        onContextMenu={(e) => {
          e.preventDefault();
          setShowPopup(!showPopup);
        }}
        className={`
          flex items-center gap-1.5 px-2 py-0.5 rounded transition-colors
          ${enabled 
            ? 'text-[var(--accent-color)] hover:bg-[var(--accent-color)]/10' 
            : 'text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]'
          }
        `}
        title={enabled ? 'Clic: Mute | Clic droit: Options' : 'Clic: Activer | Clic droit: Options'}
        aria-label={enabled ? 'Couper l’audio ambiant' : 'Activer l’audio ambiant'}
        aria-pressed={enabled}
      >
        {enabled ? (
          <Volume2 aria-hidden="true" className="w-3 h-3" />
        ) : (
          <VolumeX aria-hidden="true" className="w-3 h-3" />
        )}
        {enabled && track !== 'none' && (
          <span className="text-2xs">{volume}%</span>
        )}
        <ChevronUp
          aria-hidden="true"
          className={`w-2.5 h-2.5 transition-transform ${showPopup ? 'rotate-180' : ''}`}
        />
      </button>
      
      {/* Popup menu */}
      <AnimatePresence>
        {showPopup && (
          <motion.div
            ref={popupRef}
            initial={{ opacity: 0, y: 5, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 5, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute bottom-full right-0 mb-2 w-48 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg shadow-xl overflow-hidden"
          >
            {/* Header */}
            <div className="px-3 py-2 border-b border-[var(--border-color)] bg-[var(--bg-tertiary)]">
              <div className="flex items-center gap-2">
                <Music aria-hidden="true" className="w-3.5 h-3.5 text-[var(--accent-color)]" />
                <span className="text-xs font-medium text-[var(--text-primary)]">
                  Audio Ambiant
                </span>
              </div>
            </div>
            
            {/* Volume slider */}
            <div className="px-3 py-3">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-[var(--text-secondary)]">Volume</span>
                <span className="text-xs font-medium text-[var(--text-primary)]">{volume}%</span>
              </div>
              <input
                type="range"
                min="0"
                max="100"
                value={volume}
                onChange={(e) => setVolume(Number(e.target.value))}
                aria-label="Volume de l’audio ambiant"
                className="w-full h-1.5 rounded-full bg-[var(--bg-tertiary)] appearance-none cursor-pointer
                  [&::-webkit-slider-thumb]:appearance-none
                  [&::-webkit-slider-thumb]:w-3
                  [&::-webkit-slider-thumb]:h-3
                  [&::-webkit-slider-thumb]:rounded-full
                  [&::-webkit-slider-thumb]:bg-[var(--accent-color)]
                  [&::-webkit-slider-thumb]:cursor-pointer
                  [&::-webkit-slider-thumb]:transition-transform
                  [&::-webkit-slider-thumb]:hover:scale-110
                "
              />
            </div>
            
            {/* Track selection */}
            <div className="px-3 pb-3">
              <span className="text-xs text-[var(--text-secondary)] mb-2 block">Piste</span>
              <div className="grid grid-cols-2 gap-1">
                {(Object.keys(TRACK_LABELS) as AmbientTrack[]).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTrack(t)}
                    aria-pressed={track === t}
                    aria-label={`Piste ${TRACK_LABELS[t]}`}
                    className={`
                      px-2 py-1.5 text-xs rounded transition-colors
                      ${track === t
                        ? 'bg-[var(--accent-color)] text-[var(--btn-primary-text)]'
                        : 'bg-[var(--bg-tertiary)] text-[var(--text-secondary)] hover:bg-[var(--bg-secondary)]'
                      }
                    `}
                  >
                    {TRACK_LABELS[t]}
                  </button>
                ))}
              </div>
            </div>
            
            {/* Enable toggle */}
            <div className="px-3 py-2 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
              <label className="flex items-center justify-between cursor-pointer">
                <span className="text-xs text-[var(--text-secondary)]">Activer</span>
                <button
                  onClick={toggleEnabled}
                  role="switch"
                  aria-checked={enabled}
                  aria-label="Activer l’audio ambiant"
                  className={`
                    relative w-8 h-4 rounded-full transition-colors
                    ${enabled ? 'bg-[var(--accent-color)]' : 'bg-[var(--bg-tertiary)]'}
                  `}
                >
                  <motion.div
                    aria-hidden="true"
                    className="absolute top-0.5 w-3 h-3 bg-white rounded-full shadow"
                    animate={{ left: enabled ? '1rem' : '0.125rem' }}
                    transition={{ type: 'spring', stiffness: 500, damping: 30 }}
                  />
                </button>
              </label>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
