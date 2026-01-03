import { useRef, useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { useLayoutEditorStore } from '@/store';
import { Move, Maximize2 } from 'lucide-react';

interface SourcePreviewProps {
  videoSrc: string;
  currentTime: number;
  isPlaying: boolean;
  videoSize?: { width: number; height: number };
}

interface CropBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export function SourcePreview({
  videoSrc,
  currentTime,
  isPlaying,
  videoSize = { width: 1920, height: 1080 },
}: SourcePreviewProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const { zones, selectedZoneId, setSelectedZone, updateZone } = useLayoutEditorStore();
  
  const [containerSize, setContainerSize] = useState({ width: 0, height: 0 });
  const [dragging, setDragging] = useState<string | null>(null);
  const [resizing, setResizing] = useState<{ zoneId: string; corner: string } | null>(null);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [initialCrop, setInitialCrop] = useState<CropBox | null>(null);

  // Sync video playback
  useEffect(() => {
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    }
  }, [isPlaying]);

  // Sync video time
  useEffect(() => {
    if (videoRef.current && Math.abs(videoRef.current.currentTime - currentTime) > 0.5) {
      videoRef.current.currentTime = currentTime;
    }
  }, [currentTime]);

  // Update container size
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setContainerSize({ width: rect.width, height: rect.height });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Convert normalized coords to pixels
  const toPixels = useCallback((crop: CropBox) => {
    return {
      x: crop.x * containerSize.width,
      y: crop.y * containerSize.height,
      width: crop.width * containerSize.width,
      height: crop.height * containerSize.height,
    };
  }, [containerSize]);

  // Convert pixels to normalized coords
  const toNormalized = useCallback((pixels: CropBox) => {
    return {
      x: Math.max(0, Math.min(1 - pixels.width / containerSize.width, pixels.x / containerSize.width)),
      y: Math.max(0, Math.min(1 - pixels.height / containerSize.height, pixels.y / containerSize.height)),
      width: Math.max(0.1, Math.min(1, pixels.width / containerSize.width)),
      height: Math.max(0.1, Math.min(1, pixels.height / containerSize.height)),
    };
  }, [containerSize]);

  // Handle mouse down on crop box
  const handleMouseDown = (e: React.MouseEvent, zoneId: string, action: 'move' | string) => {
    e.stopPropagation();
    const zone = zones.find(z => z.id === zoneId);
    if (!zone) return;

    setSelectedZone(zoneId);
    setDragStart({ x: e.clientX, y: e.clientY });
    setInitialCrop({
      x: zone.sourceCrop?.x ?? zone.x / 100,
      y: zone.sourceCrop?.y ?? zone.y / 100,
      width: zone.sourceCrop?.width ?? zone.width / 100,
      height: zone.sourceCrop?.height ?? zone.height / 100,
    });

    if (action === 'move') {
      setDragging(zoneId);
    } else {
      setResizing({ zoneId, corner: action });
    }
  };

  // Handle mouse move
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!initialCrop) return;

      const deltaX = (e.clientX - dragStart.x) / containerSize.width;
      const deltaY = (e.clientY - dragStart.y) / containerSize.height;

      if (dragging) {
        const newCrop = {
          ...initialCrop,
          x: Math.max(0, Math.min(1 - initialCrop.width, initialCrop.x + deltaX)),
          y: Math.max(0, Math.min(1 - initialCrop.height, initialCrop.y + deltaY)),
        };
        updateZone(dragging, { sourceCrop: newCrop });
      } else if (resizing) {
        let newCrop = { ...initialCrop };
        
        if (resizing.corner.includes('e')) {
          newCrop.width = Math.max(0.1, Math.min(1 - initialCrop.x, initialCrop.width + deltaX));
        }
        if (resizing.corner.includes('w')) {
          const newWidth = Math.max(0.1, initialCrop.width - deltaX);
          newCrop.x = initialCrop.x + (initialCrop.width - newWidth);
          newCrop.width = newWidth;
        }
        if (resizing.corner.includes('s')) {
          newCrop.height = Math.max(0.1, Math.min(1 - initialCrop.y, initialCrop.height + deltaY));
        }
        if (resizing.corner.includes('n')) {
          const newHeight = Math.max(0.1, initialCrop.height - deltaY);
          newCrop.y = initialCrop.y + (initialCrop.height - newHeight);
          newCrop.height = newHeight;
        }
        
        updateZone(resizing.zoneId, { sourceCrop: newCrop });
      }
    };

    const handleMouseUp = () => {
      setDragging(null);
      setResizing(null);
      setInitialCrop(null);
    };

    if (dragging || resizing) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
    }
  }, [dragging, resizing, dragStart, initialCrop, containerSize, updateZone]);

  // Get zone color
  const getZoneColor = (type: string) => {
    return type === 'facecam' ? 'rgb(59, 130, 246)' : 'rgb(16, 185, 129)';
  };

  return (
    <div className="flex flex-col h-full">
      <div className="px-3 py-2 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-sm font-medium text-gray-300">Source Video (16:9)</h3>
        <span className="text-xs text-gray-500">{videoSize.width}×{videoSize.height}</span>
      </div>
      
      <div 
        ref={containerRef}
        className="flex-1 relative bg-black overflow-hidden"
        onClick={() => setSelectedZone(null)}
      >
        {/* Video */}
        <video
          ref={videoRef}
          src={videoSrc}
          className="w-full h-full object-contain"
          muted
        />
        
        {/* Overlay for crop boxes */}
        <div className="absolute inset-0">
          {/* Dark overlay outside crops */}
          <div className="absolute inset-0 bg-black/40 pointer-events-none" />
          
          {/* Crop boxes */}
          {zones.map((zone) => {
            const crop = zone.sourceCrop || {
              x: zone.type === 'facecam' ? 0.7 : 0,
              y: zone.type === 'facecam' ? 0 : 0.3,
              width: zone.type === 'facecam' ? 0.3 : 1,
              height: zone.type === 'facecam' ? 0.35 : 0.7,
            };
            const pixels = toPixels(crop);
            const isSelected = selectedZoneId === zone.id;
            const color = getZoneColor(zone.type);
            
            return (
              <motion.div
                key={zone.id}
                className="absolute cursor-move"
                style={{
                  left: pixels.x,
                  top: pixels.y,
                  width: pixels.width,
                  height: pixels.height,
                  border: `2px solid ${color}`,
                  backgroundColor: `${color}20`,
                  boxShadow: isSelected ? `0 0 0 2px ${color}, 0 0 20px ${color}40` : 'none',
                }}
                onMouseDown={(e) => handleMouseDown(e, zone.id, 'move')}
              >
                {/* Label */}
                <div 
                  className="absolute -top-6 left-0 px-2 py-0.5 text-xs font-medium rounded"
                  style={{ backgroundColor: color }}
                >
                  {zone.type.toUpperCase()}
                </div>
                
                {/* Center move icon */}
                <div className="absolute inset-0 flex items-center justify-center opacity-50">
                  <Move className="w-6 h-6 text-white" />
                </div>
                
                {/* Resize handles */}
                {isSelected && (
                  <>
                    {/* Corners */}
                    {['nw', 'ne', 'sw', 'se'].map((corner) => (
                      <div
                        key={corner}
                        className="absolute w-4 h-4 bg-white rounded-full shadow-lg cursor-nwse-resize z-10"
                        style={{
                          left: corner.includes('w') ? -6 : 'auto',
                          right: corner.includes('e') ? -6 : 'auto',
                          top: corner.includes('n') ? -6 : 'auto',
                          bottom: corner.includes('s') ? -6 : 'auto',
                          cursor: corner === 'nw' || corner === 'se' ? 'nwse-resize' : 'nesw-resize',
                        }}
                        onMouseDown={(e) => handleMouseDown(e, zone.id, corner)}
                      />
                    ))}
                    
                    {/* Edge handles */}
                    {['n', 's', 'e', 'w'].map((edge) => (
                      <div
                        key={edge}
                        className="absolute bg-white/80 z-10"
                        style={{
                          left: edge === 'w' ? -3 : edge === 'e' ? 'auto' : '50%',
                          right: edge === 'e' ? -3 : 'auto',
                          top: edge === 'n' ? -3 : edge === 's' ? 'auto' : '50%',
                          bottom: edge === 's' ? -3 : 'auto',
                          width: edge === 'n' || edge === 's' ? 24 : 6,
                          height: edge === 'e' || edge === 'w' ? 24 : 6,
                          transform: edge === 'n' || edge === 's' ? 'translateX(-50%)' : 'translateY(-50%)',
                          cursor: edge === 'n' || edge === 's' ? 'ns-resize' : 'ew-resize',
                          borderRadius: 3,
                        }}
                        onMouseDown={(e) => handleMouseDown(e, zone.id, edge)}
                      />
                    ))}
                  </>
                )}
              </motion.div>
            );
          })}
        </div>
        
        {/* Time indicator */}
        <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/70 rounded text-xs text-white font-mono">
          {formatTime(currentTime)}
        </div>
      </div>
      
      {/* Instructions */}
      <div className="px-3 py-2 border-t border-white/10 text-xs text-gray-500">
        <p>Glisse les zones pour définir le crop source. Les coins permettent de redimensionner.</p>
      </div>
    </div>
  );
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default SourcePreview;

