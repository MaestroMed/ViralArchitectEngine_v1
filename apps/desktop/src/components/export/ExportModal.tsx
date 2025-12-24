import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X,
  Download,
  Settings,
  Image,
  FileText,
  Video,
  Subtitles,
  Folder,
  Check,
  ChevronDown,
  Loader2,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';

interface ExportOptions {
  format: 'mp4' | 'mov' | 'webm';
  resolution: '1080x1920' | '720x1280' | '480x854';
  fps: 30 | 60;
  quality: 'high' | 'medium' | 'low';
  codec: 'h264' | 'h265' | 'vp9';
  includeSubtitles: boolean;
  burnSubtitles: boolean;
  exportSrt: boolean;
  exportCover: boolean;
  exportMetadata: boolean;
  outputDir?: string;
}

interface ExportModalProps {
  isOpen: boolean;
  onClose: () => void;
  segmentName: string;
  duration: number;
  onExport: (options: ExportOptions) => void;
}

const RESOLUTION_OPTIONS = [
  { value: '1080x1920', label: '1080×1920 (Full HD)', recommended: true },
  { value: '720x1280', label: '720×1280 (HD)' },
  { value: '480x854', label: '480×854 (SD)' },
];

const FORMAT_OPTIONS = [
  { value: 'mp4', label: 'MP4', description: 'Meilleure compatibilité' },
  { value: 'mov', label: 'MOV', description: 'Qualité Apple' },
  { value: 'webm', label: 'WebM', description: 'Web optimisé' },
];

const QUALITY_OPTIONS = [
  { value: 'high', label: 'Haute', bitrate: '12 Mbps', size: '~100MB/min' },
  { value: 'medium', label: 'Moyenne', bitrate: '6 Mbps', size: '~50MB/min' },
  { value: 'low', label: 'Basse', bitrate: '3 Mbps', size: '~25MB/min' },
];

export function ExportModal({
  isOpen,
  onClose,
  segmentName,
  duration,
  onExport,
}: ExportModalProps) {
  const [options, setOptions] = useState<ExportOptions>({
    format: 'mp4',
    resolution: '1080x1920',
    fps: 30,
    quality: 'high',
    codec: 'h264',
    includeSubtitles: true,
    burnSubtitles: true,
    exportSrt: true,
    exportCover: true,
    exportMetadata: true,
  });

  const [exporting, setExporting] = useState(false);
  const [activeTab, setActiveTab] = useState<'video' | 'subtitles' | 'extras'>('video');

  const estimatedSize = () => {
    const bitrateMap = { high: 12, medium: 6, low: 3 };
    const mbps = bitrateMap[options.quality];
    const sizeMB = (mbps * duration) / 8;
    return sizeMB < 1000 ? `~${Math.round(sizeMB)} MB` : `~${(sizeMB / 1000).toFixed(1)} GB`;
  };

  const handleExport = async () => {
    setExporting(true);
    await onExport(options);
    setExporting(false);
    onClose();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={onClose}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="glass border border-white/10 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-white/10">
            <div>
              <h2 className="text-xl font-bold text-white">Exporter le clip</h2>
              <p className="text-sm text-gray-400 mt-1">
                {segmentName} • {formatDuration(duration)} • {estimatedSize()}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5 text-gray-400" />
            </button>
          </div>

          {/* Tabs */}
          <div className="flex border-b border-white/10">
            {[
              { id: 'video', label: 'Vidéo', icon: Video },
              { id: 'subtitles', label: 'Sous-titres', icon: Subtitles },
              { id: 'extras', label: 'Extras', icon: FileText },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-gray-400 hover:text-gray-300'
                }`}
              >
                <tab.icon className="w-4 h-4" />
                {tab.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="p-6 max-h-[400px] overflow-auto">
            {activeTab === 'video' && (
              <div className="space-y-6">
                {/* Format */}
                <div>
                  <label className="text-sm font-medium text-gray-300 block mb-3">Format</label>
                  <div className="grid grid-cols-3 gap-2">
                    {FORMAT_OPTIONS.map((fmt) => (
                      <button
                        key={fmt.value}
                        onClick={() => setOptions({ ...options, format: fmt.value as any })}
                        className={`p-3 rounded-xl text-left transition-colors ${
                          options.format === fmt.value
                            ? 'bg-blue-500/20 border-2 border-blue-500'
                            : 'bg-white/5 border-2 border-transparent hover:bg-white/10'
                        }`}
                      >
                        <div className="font-medium text-white">{fmt.label}</div>
                        <div className="text-xs text-gray-400">{fmt.description}</div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Resolution */}
                <div>
                  <label className="text-sm font-medium text-gray-300 block mb-3">Résolution</label>
                  <div className="grid grid-cols-3 gap-2">
                    {RESOLUTION_OPTIONS.map((res) => (
                      <button
                        key={res.value}
                        onClick={() => setOptions({ ...options, resolution: res.value as any })}
                        className={`p-3 rounded-xl text-center transition-colors relative ${
                          options.resolution === res.value
                            ? 'bg-blue-500/20 border-2 border-blue-500'
                            : 'bg-white/5 border-2 border-transparent hover:bg-white/10'
                        }`}
                      >
                        <div className="font-medium text-white text-sm">{res.label}</div>
                        {res.recommended && (
                          <span className="absolute -top-2 -right-2 px-1.5 py-0.5 bg-green-500 rounded text-xs text-white">
                            Rec
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Quality & FPS */}
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="text-sm font-medium text-gray-300 block mb-3">Qualité</label>
                    <div className="space-y-2">
                      {QUALITY_OPTIONS.map((q) => (
                        <button
                          key={q.value}
                          onClick={() => setOptions({ ...options, quality: q.value as any })}
                          className={`w-full p-3 rounded-lg text-left transition-colors flex items-center justify-between ${
                            options.quality === q.value
                              ? 'bg-blue-500/20 border border-blue-500'
                              : 'bg-white/5 border border-transparent hover:bg-white/10'
                          }`}
                        >
                          <span className="font-medium text-white">{q.label}</span>
                          <span className="text-xs text-gray-400">{q.size}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="text-sm font-medium text-gray-300 block mb-3">FPS</label>
                    <div className="space-y-2">
                      {[30, 60].map((fps) => (
                        <button
                          key={fps}
                          onClick={() => setOptions({ ...options, fps: fps as any })}
                          className={`w-full p-3 rounded-lg text-left transition-colors ${
                            options.fps === fps
                              ? 'bg-blue-500/20 border border-blue-500'
                              : 'bg-white/5 border border-transparent hover:bg-white/10'
                          }`}
                        >
                          <span className="font-medium text-white">{fps} FPS</span>
                          <span className="text-xs text-gray-400 ml-2">
                            {fps === 60 ? 'Fluide' : 'Standard'}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'subtitles' && (
              <div className="space-y-4">
                <ToggleOption
                  label="Inclure les sous-titres"
                  description="Ajouter les sous-titres à la vidéo"
                  checked={options.includeSubtitles}
                  onChange={(v) => setOptions({ ...options, includeSubtitles: v })}
                />
                <ToggleOption
                  label="Incruster dans la vidéo"
                  description="Les sous-titres seront gravés dans l'image"
                  checked={options.burnSubtitles}
                  onChange={(v) => setOptions({ ...options, burnSubtitles: v })}
                  disabled={!options.includeSubtitles}
                />
                <ToggleOption
                  label="Exporter fichier SRT"
                  description="Fichier de sous-titres séparé"
                  checked={options.exportSrt}
                  onChange={(v) => setOptions({ ...options, exportSrt: v })}
                />
              </div>
            )}

            {activeTab === 'extras' && (
              <div className="space-y-4">
                <ToggleOption
                  label="Générer une cover"
                  description="Image de couverture 1080×1920 au meilleur moment"
                  checked={options.exportCover}
                  onChange={(v) => setOptions({ ...options, exportCover: v })}
                  icon={<Image className="w-5 h-5" />}
                />
                <ToggleOption
                  label="Exporter les métadonnées"
                  description="Titre, description, tags pour les réseaux sociaux"
                  checked={options.exportMetadata}
                  onChange={(v) => setOptions({ ...options, exportMetadata: v })}
                  icon={<FileText className="w-5 h-5" />}
                />

                {/* Output directory */}
                <div className="pt-4 border-t border-white/10">
                  <label className="text-sm font-medium text-gray-300 block mb-2">Dossier de sortie</label>
                  <button className="w-full p-3 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 transition-colors flex items-center gap-3">
                    <Folder className="w-5 h-5 text-gray-400" />
                    <span className="text-gray-300 flex-1 text-left text-sm truncate">
                      {options.outputDir || 'Dossier par défaut (à côté du projet)'}
                    </span>
                    <ChevronDown className="w-4 h-4 text-gray-400" />
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between p-6 border-t border-white/10 bg-white/5">
            <div className="text-sm text-gray-400">
              Taille estimée: <strong className="text-white">{estimatedSize()}</strong>
            </div>
            <div className="flex items-center gap-3">
              <Button variant="secondary" onClick={onClose}>
                Annuler
              </Button>
              <Button onClick={handleExport} disabled={exporting}>
                {exporting ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Export en cours...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4 mr-2" />
                    Exporter
                  </>
                )}
              </Button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

function ToggleOption({
  label,
  description,
  checked,
  onChange,
  disabled,
  icon,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  icon?: React.ReactNode;
}) {
  return (
    <button
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      className={`w-full p-4 rounded-xl text-left transition-colors flex items-center gap-4 ${
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      } ${checked ? 'bg-blue-500/10 border border-blue-500/30' : 'bg-white/5 border border-transparent hover:bg-white/10'}`}
    >
      {icon && <div className="text-gray-400">{icon}</div>}
      <div className="flex-1">
        <div className="font-medium text-white">{label}</div>
        <div className="text-xs text-gray-400">{description}</div>
      </div>
      <div
        className={`w-10 h-6 rounded-full transition-colors relative ${
          checked ? 'bg-blue-500' : 'bg-white/20'
        }`}
      >
        <div
          className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
            checked ? 'left-5' : 'left-1'
          }`}
        />
      </div>
    </button>
  );
}

function formatDuration(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}m ${secs}s`;
}

export default ExportModal;


