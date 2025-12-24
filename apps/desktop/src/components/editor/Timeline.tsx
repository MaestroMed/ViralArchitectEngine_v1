import { useRef, useState, useEffect, useCallback, useMemo } from 'react';
import { useClipEditorStore } from '@/store';
import { motion } from 'framer-motion';

interface TimelineProps {
  duration: number;
  waveformData?: number[];
  markers?: Array<{
    time: number;
    type: 'hook' | 'scene' | 'punchline';
    label?: string;
  }>;
  onSeek: (time: number) => void;
}

export function Timeline({
  duration,
  waveformData: initialWaveform = [],
  markers = [],
  onSeek,
}: TimelineProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const {
    playbackTime,
    trimStart,
    trimEnd,
    zoom,
    setTrimRange,
    setPlaybackTime,
  } = useClipEditorStore();

  const [isDraggingPlayhead, setIsDraggingPlayhead] = useState(false);
  const [isDraggingTrimStart, setIsDraggingTrimStart] = useState(false);
  const [isDraggingTrimEnd, setIsDraggingTrimEnd] = useState(false);

  // Generate fake waveform if none provided (visual feedback)
  const waveform = useMemo(() => {
    if (initialWaveform.length > 0) return initialWaveform;
    
    // Generate mock audio peaks (speech pattern simulation)
    return Array.from({ length: 200 }, () => {
      const base = Math.random() * 0.3 + 0.1;
      // Add "bursts" of energy
      return Math.random() > 0.8 ? base + 0.4 : base;
    });
  }, [initialWaveform, duration]);

  const positionToTime = useCallback(
    (x: number) => {
      if (!containerRef.current || duration === 0) return 0;
      const width = containerRef.current.clientWidth;
      const time = (x / width) * duration;
      return Math.max(0, Math.min(duration, time));
    },
    [duration]
  );

  const handleMouseDown = (e: React.MouseEvent, type: 'playhead' | 'trimStart' | 'trimEnd') => {
    e.preventDefault();
    e.stopPropagation();
    if (type === 'playhead') setIsDraggingPlayhead(true);
    else if (type === 'trimStart') setIsDraggingTrimStart(true);
    else if (type === 'trimEnd') setIsDraggingTrimEnd(true);
  };

  const handleMouseMove = useCallback(
    (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const time = positionToTime(x);

      if (isDraggingPlayhead) {
        const newTime = Math.max(trimStart, Math.min(trimEnd, time));
        setPlaybackTime(newTime);
        onSeek(newTime);
      } else if (isDraggingTrimStart) {
        // Minimum 5 seconds segment
        const newStart = Math.min(time, trimEnd - 5);
        setTrimRange(Math.max(0, newStart), trimEnd);
      } else if (isDraggingTrimEnd) {
        // Minimum 5 seconds segment
        const newEnd = Math.max(time, trimStart + 5);
        setTrimRange(trimStart, Math.min(duration, newEnd));
      }
    },
    [isDraggingPlayhead, isDraggingTrimStart, isDraggingTrimEnd, positionToTime, trimStart, trimEnd, duration, setTrimRange, setPlaybackTime, onSeek]
  );

  const handleMouseUp = useCallback(() => {
    setIsDraggingPlayhead(false);
    setIsDraggingTrimStart(false);
    setIsDraggingTrimEnd(false);
  }, []);

  useEffect(() => {
    if (isDraggingPlayhead || isDraggingTrimStart || isDraggingTrimEnd) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [isDraggingPlayhead, isDraggingTrimStart, isDraggingTrimEnd, handleMouseMove, handleMouseUp]);

  const handleTimelineClick = (e: React.MouseEvent) => {
    // Only seek if clicking directly on timeline (not dragging handles)
    if (isDraggingTrimStart || isDraggingTrimEnd) return;
    
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const time = positionToTime(x);
    setPlaybackTime(time);
    onSeek(time);
  };

  const markerColors = {
    hook: '#10B981',
    scene: '#F59E0B',
    punchline: '#8B5CF6',
  };

  const progressPercent = (playbackTime / duration) * 100;
  const startPercent = (trimStart / duration) * 100;
  const endPercent = (trimEnd / duration) * 100;

  return (
    <div className="w-full bg-[var(--bg-secondary)] rounded-lg p-4 select-none">
      {/* Time ruler */}
      <div className="flex items-center justify-between text-xs text-[var(--text-muted)] mb-2 font-mono">
        <span>{formatTime(0)}</span>
        <span>{formatTime(duration / 4)}</span>
        <span>{formatTime(duration / 2)}</span>
        <span>{formatTime((duration * 3) / 4)}</span>
        <span>{formatTime(duration)}</span>
      </div>

      {/* Timeline container */}
      <div
        ref={containerRef}
        className="relative h-24 bg-[var(--bg-tertiary)] rounded-lg cursor-crosshair overflow-hidden group"
        onClick={handleTimelineClick}
      >
        {/* Waveform */}
        <div className="absolute inset-0 flex items-center justify-between px-1 pointer-events-none">
          {waveform.map((value, i) => (
            <div
              key={i}
              className="flex-1 mx-px bg-white/20 rounded-full transition-all"
              style={{
                height: `${value * 100}%`,
                opacity: 
                  (i / waveform.length * 100) >= startPercent && 
                  (i / waveform.length * 100) <= endPercent 
                    ? 0.8 
                    : 0.2
              }}
            />
          ))}
        </div>

        {/* Inactive Zones (Dimmed) */}
        <div
          className="absolute top-0 bottom-0 bg-black/60 pointer-events-none backdrop-blur-[1px]"
          style={{ width: `${startPercent}%`, left: 0 }}
        />
        <div
          className="absolute top-0 bottom-0 bg-black/60 pointer-events-none backdrop-blur-[1px]"
          style={{ width: `${100 - endPercent}%`, right: 0 }}
        />

        {/* Markers */}
        {markers.map((marker, i) => (
          <div
            key={i}
            className="absolute top-0 bottom-0 w-px z-10 pointer-events-none opacity-60"
            style={{
              left: `${(marker.time / duration) * 100}%`,
              backgroundColor: markerColors[marker.type],
            }}
          >
            <div
              className="absolute -top-1 left-1/2 -translate-x-1/2 w-2 h-2 rounded-full"
              style={{ backgroundColor: markerColors[marker.type] }}
            />
          </div>
        ))}

        {/* Trim Handles */}
        <div 
          className="absolute top-0 bottom-0 w-1 bg-blue-500 cursor-ew-resize z-20 group-hover:w-2 transition-all"
          style={{ left: `${startPercent}%` }}
          onMouseDown={(e) => handleMouseDown(e, 'trimStart')}
        >
          <div className="absolute top-0 -translate-x-full bg-blue-500 text-[10px] text-white px-1 rounded-l opacity-0 group-hover:opacity-100 font-mono">
            {formatTime(trimStart)}
          </div>
        </div>
        
        <div 
          className="absolute top-0 bottom-0 w-1 bg-blue-500 cursor-ew-resize z-20 group-hover:w-2 transition-all"
          style={{ left: `${endPercent}%` }}
          onMouseDown={(e) => handleMouseDown(e, 'trimEnd')}
        >
          <div className="absolute top-0 translate-x-2 bg-blue-500 text-[10px] text-white px-1 rounded-r opacity-0 group-hover:opacity-100 font-mono">
            {formatTime(trimEnd)}
          </div>
        </div>

        {/* Active Region Border */}
        <div 
          className="absolute top-0 bottom-0 border-t-2 border-b-2 border-blue-500/30 pointer-events-none"
          style={{ left: `${startPercent}%`, width: `${endPercent - startPercent}%` }}
        />

        {/* Playhead */}
        <motion.div
          className="absolute top-0 bottom-0 w-0.5 bg-red-500 z-30 cursor-ew-resize shadow-[0_0_10px_rgba(239,68,68,0.5)]"
          style={{ left: `${progressPercent}%` }}
          onMouseDown={(e) => handleMouseDown(e, 'playhead')}
          animate={{ left: `${progressPercent}%` }}
          transition={{ type: 'tween', duration: 0.05, ease: 'linear' }}
        >
          <div className="absolute -top-1.5 left-1/2 -translate-x-1/2 w-3 h-3 bg-red-500 rotate-45 transform origin-center" />
        </motion.div>
      </div>

      {/* Stats footer */}
      <div className="flex items-center justify-between mt-3 text-xs">
        <div className="flex items-center gap-6">
          <div>
            <span className="text-[var(--text-muted)] uppercase tracking-wider">Durée</span>
            <span className={`ml-2 font-mono font-medium ${trimEnd - trimStart < 60 ? 'text-amber-500' : 'text-[var(--text-primary)]'}`}>
              {formatTime(trimEnd - trimStart)}
            </span>
          </div>
          {trimEnd - trimStart < 60 && (
            <div className="flex items-center text-amber-500 gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
              <span>Trop court pour TikTok (min 60s)</span>
            </div>
          )}
        </div>
        <div className="font-mono text-[var(--text-muted)]">
          {formatTime(playbackTime)}
        </div>
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 10);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms}`;
}
