import { useRef, useEffect, useState, useCallback } from 'react';
import { useLayoutEditorStore, useSubtitleStyleStore } from '@/store';
import { motion, useDragControls } from 'framer-motion';

interface Canvas9x16Props {
  videoSrc: string;
  currentTime: number;
  isPlaying: boolean;
  currentSubtitle?: string;
  highlightedWord?: string;
  faceDetections?: any[];
  onTimeUpdate?: (time: number) => void;
  onPlayPause?: () => void;
}

export function Canvas9x16({
  videoSrc,
  currentTime,
  isPlaying,
  currentSubtitle,
  highlightedWord,
  faceDetections = [],
  onTimeUpdate,
  onPlayPause,
}: Canvas9x16Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const { zones, selectedZoneId, setSelectedZone, updateZone } = useLayoutEditorStore();
  const { style } = useSubtitleStyleStore();
  const [canvasRect, setCanvasRect] = useState<DOMRect | null>(null);

  // Sync main video playback
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  // Sync main video time
  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.5) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  const handleTimeUpdate = () => {
    if (videoRef.current && onTimeUpdate) {
      onTimeUpdate(videoRef.current.currentTime);
    }
  };

  // Update canvas dimensions on resize
  useEffect(() => {
    const updateRect = () => {
      if (canvasRef.current) {
        setCanvasRect(canvasRef.current.getBoundingClientRect());
      }
    };
    
    updateRect();
    window.addEventListener('resize', updateRect);
    return () => window.removeEventListener('resize', updateRect);
  }, []);

  // Sync other video elements (zones)
  const syncZoneVideos = useCallback(() => {
    if (!videoRef.current) return;
    const time = videoRef.current.currentTime;
    
    document.querySelectorAll('video.zone-video').forEach((el) => {
      const v = el as HTMLVideoElement;
      if (Math.abs(v.currentTime - time) > 0.1) {
        v.currentTime = time;
      }
      if (isPlaying && v.paused) v.play().catch(() => {});
      if (!isPlaying && !v.paused) v.pause();
    });
  }, [isPlaying]);

  useEffect(() => {
    let frameId: number;
    const loop = () => {
      syncZoneVideos();
      frameId = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(frameId);
  }, [syncZoneVideos]);


  const renderSubtitle = () => {
    if (!currentSubtitle) return null;

    const positionClass = {
      bottom: 'bottom-16',
      center: 'top-1/2 -translate-y-1/2',
      top: 'top-16',
    }[style.position];

    const words = currentSubtitle.split(' ');

    return (
      <div className={`absolute left-8 right-8 ${positionClass} text-center z-20 pointer-events-none`}>
        <motion.p
          initial={{ opacity: 0.8, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="inline-block px-4 py-2 rounded-lg"
          style={{
            fontFamily: style.fontFamily,
            fontSize: `${style.fontSize / 2.5}px`, // Scale down for preview
            fontWeight: style.fontWeight,
            color: style.color,
            backgroundColor: style.backgroundColor,
            textShadow: style.outlineWidth > 0
              ? `
                -${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor},
                ${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor},
                -${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor},
                ${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor}
              `
              : 'none',
            lineHeight: 1.4,
          }}
        >
          {words.map((word, i) => {
            const isHighlighted = word.toLowerCase().replace(/[.,!?]/g, '') === highlightedWord?.toLowerCase().replace(/[.,!?]/g, '');
            return (
              <span
                key={i}
                className="transition-all duration-100 inline-block mx-1"
                style={{
                  color: isHighlighted ? style.highlightColor : style.color,
                  transform: isHighlighted && style.animation === 'pop' ? 'scale(1.2)' : 'scale(1)',
                }}
              >
                {word}
              </span>
            );
          })}
        </motion.p>
      </div>
    );
  };

  return (
    <div
      ref={canvasRef}
      className="relative bg-black rounded-xl overflow-hidden shadow-2xl select-none"
      style={{ aspectRatio: '9/16', maxHeight: '75vh' }}
      onClick={() => {
        setSelectedZone(null);
        onPlayPause?.();
      }}
    >
      {/* Hidden main video for timing master */}
      <video
        ref={videoRef}
        src={videoSrc}
        className="hidden"
        onTimeUpdate={handleTimeUpdate}
        muted={false} // Main audio source
      />

      {/* Grid / Safe Guides */}
      <div className="absolute inset-0 pointer-events-none z-30 opacity-20">
        <div className="absolute inset-8 border border-dashed border-white/50 rounded" />
      </div>

      {/* Interactive Zones */}
      {zones.map((zone) => (
        <DraggableZone
          key={zone.id}
          zone={zone}
          isSelected={selectedZoneId === zone.id}
          videoSrc={videoSrc}
          canvasRect={canvasRect}
          faceRect={zone.id === 'facecam' ? getInterpolatedFaceRect(faceDetections, currentTime) : null}
          onSelect={() => setSelectedZone(zone.id)}
          onUpdate={(updates) => updateZone(zone.id, updates)}
        />
      ))}

      {/* Subtitles */}
      {renderSubtitle()}

      {/* Controls Overlay */}
      {!isPlaying && (
        <div className="absolute inset-0 flex items-center justify-center bg-black/10 pointer-events-none z-40">
          <div className="w-16 h-16 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center shadow-lg">
             <div className="w-0 h-0 border-t-[12px] border-b-[12px] border-l-[20px] border-transparent border-l-white ml-1" />
          </div>
        </div>
      )}

      <div className="absolute bottom-3 right-3 px-2 py-1 bg-black/60 backdrop-blur-md rounded text-xs text-white/90 font-mono z-50 pointer-events-none">
        {formatTime(currentTime)}
      </div>
    </div>
  );
}

// Separate component for drag logic
function DraggableZone({ 
  zone, 
  isSelected, 
  videoSrc, 
  canvasRect,
  faceRect,
  onSelect,
  onUpdate 
}: { 
  zone: any, 
  isSelected: boolean, 
  videoSrc: string,
  canvasRect: DOMRect | null,
  faceRect?: { x: number, y: number, width: number, height: number } | null,
  onSelect: () => void,
  onUpdate: (u: any) => void
}) {
  const controls = useDragControls();

  const handleDragEnd = (_: any, info: any) => {
    if (!canvasRect) return;
    
    // Convert pixel delta to percentage
    const deltaX = (info.offset.x / canvasRect.width) * 100;
    const deltaY = (info.offset.y / canvasRect.height) * 100;
    
    onUpdate({
      x: Math.max(0, Math.min(100 - zone.width, zone.x + deltaX)),
      y: Math.max(0, Math.min(100 - zone.height, zone.y + deltaY))
    });
  };

  return (
    <motion.div
      drag={isSelected}
      dragControls={controls}
      dragMomentum={false}
      dragElastic={0}
      onDragEnd={handleDragEnd}
      onClick={(e) => {
        e.stopPropagation();
        onSelect();
      }}
      className={`absolute overflow-hidden group ${
        isSelected ? 'z-20 ring-2 ring-[var(--accent-color)] shadow-xl' : 'z-10'
      }`}
      style={{
        left: `${zone.x}%`,
        top: `${zone.y}%`,
        width: `${zone.width}%`,
        height: `${zone.height}%`,
        touchAction: 'none',
      }}
      whileHover={{ scale: 1.005 }}
    >
      {/* Video Content */}
      <div className="w-full h-full bg-gray-900 relative">
        <video
          src={videoSrc}
          className="zone-video w-full h-full object-cover pointer-events-none"
          muted
          style={{
            objectPosition: faceRect 
              ? `${(faceRect.x + faceRect.width/2) * 100}% ${(faceRect.y + faceRect.height/3) * 100}%` 
              : 'center 20%'
          }}
        />
        
        {/* Overlay when selected */}
        <div className={`absolute inset-0 bg-[var(--accent-color)]/10 transition-opacity ${isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`} />
      </div>

      {/* Label */}
      <div className="absolute top-2 left-2 px-2 py-1 bg-black/70 backdrop-blur-sm rounded text-[10px] text-white font-medium uppercase tracking-wider pointer-events-none">
        {zone.type}
      </div>

      {/* Resize Handles (Visual only for now) */}
      {isSelected && (
        <>
          <div className="absolute top-0 left-0 w-3 h-3 bg-[var(--accent-color)] cursor-nw-resize" />
          <div className="absolute top-0 right-0 w-3 h-3 bg-[var(--accent-color)] cursor-ne-resize" />
          <div className="absolute bottom-0 left-0 w-3 h-3 bg-[var(--accent-color)] cursor-sw-resize" />
          <div className="absolute bottom-0 right-0 w-3 h-3 bg-[var(--accent-color)] cursor-se-resize" />
        </>
      )}
    </motion.div>
  );
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  const ms = Math.floor((seconds % 1) * 100);
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}.${ms.toString().padStart(2, '0')}`;
}

function getInterpolatedFaceRect(detections: any[], time: number) {
  if (!detections || detections.length === 0) return null;
  
  const nextIdx = detections.findIndex(d => d.time > time);
  if (nextIdx === -1) return detections[detections.length - 1].normalized;
  if (nextIdx === 0) return detections[0].normalized;
  
  const prev = detections[nextIdx - 1];
  const next = detections[nextIdx];
  const factor = (time - prev.time) / (next.time - prev.time);
  
  return {
    x: prev.normalized.x + (next.normalized.x - prev.normalized.x) * factor,
    y: prev.normalized.y + (next.normalized.y - prev.normalized.y) * factor,
    width: prev.normalized.width + (next.normalized.width - prev.normalized.width) * factor,
    height: prev.normalized.height + (next.normalized.height - prev.normalized.height) * factor,
  };
}
