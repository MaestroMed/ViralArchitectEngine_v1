import { useMemo } from 'react';
import { motion } from 'framer-motion';

interface TimelineLayer {
  id: string;
  name: string;
  type: string;
  data: Array<{ time: number; value: number }>;
  color: string;
}

interface TimelineData {
  projectId: string;
  duration: number;
  layers: TimelineLayer[];
  segments: Array<{
    id: string;
    startTime: number;
    endTime: number;
    score: number;
    label?: string;
  }>;
}

interface Segment {
  id: string;
  startTime: number;
  endTime: number;
  score: { total: number };
}

interface ViralDNAMapProps {
  timeline: TimelineData;
  segments: Segment[];
  selectedSegmentId?: string;
  onSegmentClick: (id: string) => void;
}

export default function ViralDNAMap({
  timeline,
  segments,
  selectedSegmentId,
  onSegmentClick,
}: ViralDNAMapProps) {
  const { duration, layers } = timeline;

  // Generate path for each layer
  const layerPaths = useMemo(() => {
    return layers.map((layer) => {
      if (layer.data.length === 0) return null;

      const points = layer.data.map((point) => ({
        x: (point.time / duration) * 100,
        y: (1 - point.value) * 100,
      }));

      // Create smooth path
      let d = `M ${points[0].x} ${points[0].y}`;
      for (let i = 1; i < points.length; i++) {
        const cp1x = points[i - 1].x + (points[i].x - points[i - 1].x) / 3;
        const cp2x = points[i - 1].x + (2 * (points[i].x - points[i - 1].x)) / 3;
        d += ` C ${cp1x} ${points[i - 1].y}, ${cp2x} ${points[i].y}, ${points[i].x} ${points[i].y}`;
      }

      // Close the path for fill
      d += ` L ${points[points.length - 1].x} 100 L ${points[0].x} 100 Z`;

      return {
        ...layer,
        path: d,
      };
    }).filter(Boolean);
  }, [layers, duration]);

  return (
    <div className="h-full relative">
      {/* SVG Visualization */}
      <svg
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        className="w-full h-full"
      >
        {/* Grid lines */}
        <defs>
          <pattern id="grid" width="10" height="10" patternUnits="userSpaceOnUse">
            <path
              d="M 10 0 L 0 0 0 10"
              fill="none"
              stroke="var(--border-color)"
              strokeWidth="0.1"
            />
          </pattern>
        </defs>
        <rect width="100" height="100" fill="url(#grid)" opacity="0.5" />

        {/* Layer paths */}
        {layerPaths.map((layer, i) => (
          <motion.path
            key={layer!.id}
            d={layer!.path}
            fill={layer!.color}
            fillOpacity={0.3}
            stroke={layer!.color}
            strokeWidth="0.5"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: i * 0.1 }}
          />
        ))}

        {/* Segment markers */}
        {segments.map((segment) => {
          const x1 = (segment.startTime / duration) * 100;
          const x2 = (segment.endTime / duration) * 100;
          const isSelected = segment.id === selectedSegmentId;

          return (
            <g key={segment.id}>
              {/* Segment range */}
              <motion.rect
                x={x1}
                y="0"
                width={x2 - x1}
                height="100"
                fill={isSelected ? '#1A1A1A' : '#10B981'}
                fillOpacity={isSelected ? 0.2 : 0.1}
                stroke={isSelected ? '#1A1A1A' : '#10B981'}
                strokeWidth={isSelected ? 0.5 : 0.2}
                className="cursor-pointer"
                onClick={() => onSegmentClick(segment.id)}
                whileHover={{ fillOpacity: 0.3 }}
              />

              {/* Score indicator */}
              <circle
                cx={(x1 + x2) / 2}
                cy="10"
                r="3"
                fill={getScoreColor(segment.score.total)}
                className="pointer-events-none"
              />
            </g>
          );
        })}
      </svg>

      {/* Legend */}
      <div className="absolute bottom-0 left-0 right-0 flex items-center gap-4 px-2 py-1 bg-[var(--bg-secondary)]/80 backdrop-blur-sm text-2xs">
        {layers.map((layer) => (
          <div key={layer.id} className="flex items-center gap-1">
            <div
              className="w-2 h-2 rounded-full"
              style={{ backgroundColor: layer.color }}
            />
            <span className="text-[var(--text-muted)]">{layer.name}</span>
          </div>
        ))}
      </div>

      {/* Time markers */}
      <div className="absolute top-0 left-0 right-0 h-4 flex justify-between px-1 text-2xs text-[var(--text-muted)]">
        <span>0:00</span>
        <span>{formatTime(duration / 4)}</span>
        <span>{formatTime(duration / 2)}</span>
        <span>{formatTime((duration * 3) / 4)}</span>
        <span>{formatTime(duration)}</span>
      </div>
    </div>
  );
}

function getScoreColor(score: number): string {
  if (score >= 70) return '#10B981';
  if (score >= 40) return '#F59E0B';
  return '#6B7280';
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}




