import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Link2, Youtube, Twitch, Loader2, Download, Clock, Eye, User, AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { api } from '@/lib/api';
import { useToastStore, useJobsStore } from '@/store';
import { formatDuration } from '@/lib/utils';

interface VideoInfo {
  id: string;
  title: string;
  description: string;
  duration: number;
  thumbnailUrl?: string;
  channel: string;
  channelId: string;
  uploadDate: string;
  viewCount: number;
  url: string;
  platform: string;
}

interface UrlImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onImportComplete?: (projectId: string) => void;
}

export function UrlImportModal({ isOpen, onClose, onImportComplete }: UrlImportModalProps) {
  const { addToast } = useToastStore();
  const { addJob } = useJobsStore();
  
  const [url, setUrl] = useState('');
  const [quality, setQuality] = useState<'best' | '1080' | '720' | '480'>('best');
  const [autoIngest, setAutoIngest] = useState(true);
  const [autoAnalyze, setAutoAnalyze] = useState(true);
  
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  // Debounced URL info fetch
  const fetchInfo = useCallback(async (inputUrl: string) => {
    if (!inputUrl.trim()) {
      setVideoInfo(null);
      setError(null);
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      const response = await api.getUrlInfo(inputUrl);
      if (response.success && response.data) {
        setVideoInfo(response.data as VideoInfo);
      } else {
        setError(response.error || 'URL non reconnue');
        setVideoInfo(null);
      }
    } catch (err) {
      setError('Impossible de récupérer les informations');
      setVideoInfo(null);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    const timer = setTimeout(() => {
      if (url.includes('youtube') || url.includes('youtu.be') || url.includes('twitch')) {
        fetchInfo(url);
      }
    }, 500);
    
    return () => clearTimeout(timer);
  }, [url, fetchInfo]);
  
  const handleImport = async () => {
    if (!videoInfo) return;
    
    setImporting(true);
    
    try {
      const response = await api.importFromUrl(url, quality, autoIngest, autoAnalyze);
      
      if (response.success && response.data) {
        const { project, jobId } = response.data;
        
        addJob({
          id: jobId,
          type: 'download',
          projectId: project.id,
          status: 'running',
          progress: 0,
          stage: 'Téléchargement...',
        });
        
        addToast({
          type: 'success',
          title: 'Import lancé',
          message: `"${videoInfo.title}" est en cours de téléchargement`,
        });
        
        onImportComplete?.(project.id);
        onClose();
      } else {
        throw new Error(response.error || 'Import failed');
      }
    } catch (err) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: err instanceof Error ? err.message : 'Échec de l\'import',
      });
    } finally {
      setImporting(false);
    }
  };
  
  const formatDate = (dateStr: string) => {
    if (!dateStr || dateStr.length !== 8) return '';
    const year = dateStr.slice(0, 4);
    const month = dateStr.slice(4, 6);
    const day = dateStr.slice(6, 8);
    return `${day}/${month}/${year}`;
  };
  
  const formatViews = (count: number) => {
    if (count >= 1000000) return `${(count / 1000000).toFixed(1)}M`;
    if (count >= 1000) return `${(count / 1000).toFixed(0)}k`;
    return count.toString();
  };
  
  const PlatformIcon = videoInfo?.platform === 'twitch' ? Twitch : Youtube;
  const platformColor = videoInfo?.platform === 'twitch' ? 'text-purple-500' : 'text-red-500';
  
  if (!isOpen) return null;
  
  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      >
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          className="w-full max-w-xl bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)]">
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-red-500/20 to-purple-500/20">
                <Link2 className="w-5 h-5 text-[var(--text-primary)]" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-[var(--text-primary)]">
                  Importer depuis URL
                </h2>
                <p className="text-xs text-[var(--text-muted)]">YouTube, Twitch VOD, Clips</p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X className="w-5 h-5 text-[var(--text-muted)]" />
            </button>
          </div>
          
          {/* Content */}
          <div className="p-6 space-y-4">
            {/* URL Input */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                URL de la vidéo
              </label>
              <div className="relative">
                <input
                  type="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://youtube.com/watch?v=... ou twitch.tv/videos/..."
                  className="w-full px-4 py-3 pr-10 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                />
                {loading && (
                  <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-5 h-5 text-[var(--text-muted)] animate-spin" />
                )}
              </div>
            </div>
            
            {/* Error */}
            {error && (
              <div className="flex items-center gap-2 px-4 py-3 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
                <AlertCircle className="w-4 h-4" />
                {error}
              </div>
            )}
            
            {/* Video Preview */}
            {videoInfo && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex gap-4 p-4 bg-[var(--bg-secondary)] rounded-xl border border-[var(--border-color)]"
              >
                {/* Thumbnail */}
                <div className="relative w-40 aspect-video rounded-lg overflow-hidden bg-[var(--bg-tertiary)] shrink-0">
                  {videoInfo.thumbnailUrl ? (
                    <img
                      src={videoInfo.thumbnailUrl}
                      alt={videoInfo.title}
                      className="w-full h-full object-cover"
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center">
                      <PlatformIcon className={`w-8 h-8 ${platformColor} opacity-50`} />
                    </div>
                  )}
                  {/* Duration badge */}
                  <div className="absolute bottom-1 right-1 px-1.5 py-0.5 bg-black/80 rounded text-[10px] font-medium text-white">
                    {formatDuration(videoInfo.duration)}
                  </div>
                </div>
                
                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start gap-2">
                    <PlatformIcon className={`w-4 h-4 mt-0.5 ${platformColor} shrink-0`} />
                    <h3 className="font-medium text-[var(--text-primary)] line-clamp-2 text-sm">
                      {videoInfo.title}
                    </h3>
                  </div>
                  
                  <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-[var(--text-muted)]">
                    <span className="flex items-center gap-1">
                      <User className="w-3 h-3" />
                      {videoInfo.channel}
                    </span>
                    {videoInfo.uploadDate && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        {formatDate(videoInfo.uploadDate)}
                      </span>
                    )}
                    {videoInfo.viewCount > 0 && (
                      <span className="flex items-center gap-1">
                        <Eye className="w-3 h-3" />
                        {formatViews(videoInfo.viewCount)} vues
                      </span>
                    )}
                  </div>
                </div>
              </motion.div>
            )}
            
            {/* Options */}
            {videoInfo && (
              <div className="grid grid-cols-2 gap-4">
                {/* Quality */}
                <div>
                  <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                    Qualité
                  </label>
                  <select
                    value={quality}
                    onChange={(e) => setQuality(e.target.value as typeof quality)}
                    className="w-full px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
                  >
                    <option value="best">Meilleure qualité</option>
                    <option value="1080">1080p</option>
                    <option value="720">720p</option>
                    <option value="480">480p</option>
                  </select>
                </div>
                
                {/* Options */}
                <div className="space-y-2">
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoIngest}
                      onChange={(e) => setAutoIngest(e.target.checked)}
                      className="w-4 h-4 rounded border-[var(--border-color)] bg-[var(--bg-secondary)] text-blue-500 focus:ring-blue-500/30"
                    />
                    <span className="text-sm text-[var(--text-secondary)]">Auto-ingestion</span>
                  </label>
                  <label className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={autoAnalyze}
                      onChange={(e) => setAutoAnalyze(e.target.checked)}
                      className="w-4 h-4 rounded border-[var(--border-color)] bg-[var(--bg-secondary)] text-blue-500 focus:ring-blue-500/30"
                    />
                    <span className="text-sm text-[var(--text-secondary)]">Auto-analyse</span>
                  </label>
                </div>
              </div>
            )}
          </div>
          
          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
            <Button variant="ghost" onClick={onClose}>
              Annuler
            </Button>
            <Button
              onClick={handleImport}
              disabled={!videoInfo || importing}
              loading={importing}
            >
              <Download className="w-4 h-4 mr-2" />
              Importer
            </Button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

