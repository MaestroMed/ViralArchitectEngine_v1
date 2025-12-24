import { motion } from 'framer-motion';
import { useLayoutEditorStore } from '@/store';
import { Monitor, Square, Columns, PictureInPicture, Video } from 'lucide-react';

const PRESETS = [
  {
    id: 'facecam-top',
    name: 'Facecam en haut',
    icon: Monitor,
    preview: (
      <div className="w-full h-full flex flex-col gap-0.5">
        <div className="h-[35%] bg-blue-400 rounded-sm" />
        <div className="flex-1 bg-purple-400 rounded-sm" />
      </div>
    ),
  },
  {
    id: 'facecam-bottom',
    name: 'Facecam en bas',
    icon: Monitor,
    preview: (
      <div className="w-full h-full flex flex-col gap-0.5">
        <div className="flex-1 bg-purple-400 rounded-sm" />
        <div className="h-[35%] bg-blue-400 rounded-sm" />
      </div>
    ),
  },
  {
    id: 'split-50-50',
    name: 'Split 50/50',
    icon: Columns,
    preview: (
      <div className="w-full h-full flex flex-col gap-0.5">
        <div className="h-1/2 bg-blue-400 rounded-sm" />
        <div className="h-1/2 bg-purple-400 rounded-sm" />
      </div>
    ),
  },
  {
    id: 'pip-corner',
    name: 'PiP coin',
    icon: PictureInPicture,
    preview: (
      <div className="w-full h-full relative">
        <div className="absolute inset-0 bg-purple-400 rounded-sm" />
        <div className="absolute top-1 right-1 w-[30%] h-[25%] bg-blue-400 rounded-sm" />
      </div>
    ),
  },
  {
    id: 'content-only',
    name: 'Contenu seul',
    icon: Video,
    preview: (
      <div className="w-full h-full">
        <div className="w-full h-full bg-purple-400 rounded-sm" />
      </div>
    ),
  },
];

export function LayoutPresets() {
  const { presetName, applyPreset } = useLayoutEditorStore();

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-medium text-[var(--text-primary)]">Presets de layout</h4>
      
      <div className="grid grid-cols-5 gap-2">
        {PRESETS.map((preset) => (
          <motion.button
            key={preset.id}
            className={`flex flex-col items-center gap-1.5 p-2 rounded-lg transition-colors ${
              presetName === preset.id
                ? 'bg-blue-500/20 ring-2 ring-blue-500'
                : 'bg-[var(--bg-tertiary)] hover:bg-[var(--bg-secondary)]'
            }`}
            onClick={() => applyPreset(preset.id)}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
          >
            <div
              className="w-8 h-14 rounded border border-[var(--border-color)] overflow-hidden p-0.5"
              style={{ aspectRatio: '9/16' }}
            >
              {preset.preview}
            </div>
            <span className="text-xs text-[var(--text-muted)] text-center leading-tight">
              {preset.name}
            </span>
          </motion.button>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 pt-2 text-xs text-[var(--text-muted)]">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-blue-400 rounded-sm" />
          <span>Facecam</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 bg-purple-400 rounded-sm" />
          <span>Contenu</span>
        </div>
      </div>
    </div>
  );
}








