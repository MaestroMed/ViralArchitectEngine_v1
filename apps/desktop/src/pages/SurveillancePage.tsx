import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye, Plus, Twitch, Youtube, Loader2, RefreshCw, Check,
  Clock, Download, X, MoreVertical, Trash2, Settings2
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { api } from '@/lib/api';
import { formatDuration } from '@/lib/utils';
import { useToastStore, useJobsStore } from '@/store';

interface WatchedChannel {
  id: string;
  channelId: string;
  channelName: string;
  displayName?: string;
  platform: string;
  profileImageUrl?: string;
  enabled: boolean;
  checkInterval: number;
  autoImport: boolean;
  lastCheckAt?: string;
  createdAt: string;
}

interface DetectedVOD {
  id: string;
  externalId: string;
  title: string;
  channelId: string;
  channelName: string;
  platform: string;
  url: string;
  thumbnailUrl?: string;
  duration?: number;
  publishedAt?: string;
  viewCount: number;
  status: string;
  projectId?: string;
  estimatedScore?: number;
  detectedAt: string;
}

export default function SurveillancePage() {
  const { addToast } = useToastStore();
  const { addJob } = useJobsStore();
  
  const [channels, setChannels] = useState<WatchedChannel[]>([]);
  const [vods, setVods] = useState<DetectedVOD[]>([]);
  const [loading, setLoading] = useState(true);
  const [addModalOpen, setAddModalOpen] = useState(false);
  const [checkingChannel, setCheckingChannel] = useState<string | null>(null);
  
  const loadData = useCallback(async () => {
    try {
      const [channelsRes, vodsRes] = await Promise.all([
        api.request<{ success: boolean; data: WatchedChannel[] }>('/channels'),
        api.request<{ success: boolean; data: { items: DetectedVOD[] } }>('/channels/vods/detected?status=new'),
      ]);
      
      if (channelsRes.success) setChannels(channelsRes.data || []);
      if (vodsRes.success) setVods(vodsRes.data?.items || []);
    } catch (error) {
      console.error('Failed to load surveillance data:', error);
    } finally {
      setLoading(false);
    }
  }, []);
  
  useEffect(() => {
    loadData();
  }, [loadData]);
  
  const handleCheckChannel = async (channelId: string) => {
    setCheckingChannel(channelId);
    try {
      const response = await api.request<{ success: boolean; data: { newVods: DetectedVOD[] } }>(
        `/channels/${channelId}/check`,
        { method: 'POST' }
      );
      
      if (response.success) {
        const newVods = response.data?.newVods || [];
        if (newVods.length > 0) {
          setVods((prev) => [...newVods, ...prev]);
          addToast({
            type: 'success',
            title: 'Nouvelles VODs',
            message: `${newVods.length} nouvelle(s) VOD(s) détectée(s)`,
          });
        } else {
          addToast({
            type: 'info',
            title: 'Aucune nouvelle VOD',
            message: 'La chaîne est à jour',
          });
        }
        loadData();
      }
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Échec de la vérification',
      });
    } finally {
      setCheckingChannel(null);
    }
  };
  
  const handleImportVOD = async (vodId: string) => {
    try {
      const response = await api.request<{ success: boolean; data: { project: any; jobId: string } }>(
        `/channels/vods/${vodId}/import`,
        { method: 'POST' }
      );
      
      if (response.success && response.data) {
        addJob({
          id: response.data.jobId,
          type: 'download',
          projectId: response.data.project.id,
          status: 'running',
          progress: 0,
          stage: 'Téléchargement...',
        });
        
        addToast({
          type: 'success',
          title: 'Import lancé',
          message: 'La VOD est en cours de téléchargement',
        });
        
        // Update VOD status locally
        setVods((prev) => prev.filter((v) => v.id !== vodId));
      }
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Échec de l\'import',
      });
    }
  };
  
  const handleIgnoreVOD = async (vodId: string) => {
    try {
      await api.request(`/channels/vods/${vodId}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: 'ignored' }),
      });
      setVods((prev) => prev.filter((v) => v.id !== vodId));
    } catch (error) {
      console.error('Failed to ignore VOD:', error);
    }
  };
  
  const handleDeleteChannel = async (channelId: string) => {
    if (!confirm('Supprimer cette chaîne de la surveillance ?')) return;
    
    try {
      await api.request(`/channels/${channelId}`, { method: 'DELETE' });
      setChannels((prev) => prev.filter((c) => c.id !== channelId));
      addToast({
        type: 'success',
        title: 'Chaîne supprimée',
        message: 'La chaîne a été retirée de la surveillance',
      });
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: 'Échec de la suppression',
      });
    }
  };
  
  const PlatformIcon = ({ platform }: { platform: string }) => {
    if (platform === 'twitch') return <Twitch className="w-4 h-4 text-purple-500" />;
    return <Youtube className="w-4 h-4 text-red-500" />;
  };
  
  const formatRelativeTime = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(minutes / 60);
    const days = Math.floor(hours / 24);
    
    if (minutes < 1) return "À l'instant";
    if (minutes < 60) return `Il y a ${minutes}min`;
    if (hours < 24) return `Il y a ${hours}h`;
    return `Il y a ${days}j`;
  };
  
  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <header className="px-8 py-6 border-b border-[var(--border-color)] bg-[var(--bg-card)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-xl bg-gradient-to-br from-purple-500/20 to-pink-500/20">
              <Eye className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-semibold text-[var(--text-primary)]">Surveillance</h1>
              <p className="text-sm text-[var(--text-muted)] mt-0.5">
                Détection automatique des nouvelles VODs
              </p>
            </div>
          </div>
          
          <Button onClick={() => setAddModalOpen(true)}>
            <Plus className="w-4 h-4 mr-2" />
            Ajouter une chaîne
          </Button>
        </div>
      </header>
      
      {/* Content */}
      <div className="flex-1 overflow-auto p-8">
        {loading ? (
          <div className="flex items-center justify-center h-64">
            <Loader2 className="w-8 h-8 animate-spin text-[var(--text-muted)]" />
          </div>
        ) : (
          <div className="space-y-8">
            {/* Watched Channels */}
            <section>
              <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">
                Chaînes surveillées ({channels.length})
              </h2>
              
              {channels.length === 0 ? (
                <Card className="p-8 text-center bg-[var(--bg-card)]">
                  <Eye className="w-12 h-12 mx-auto text-[var(--text-muted)] opacity-30 mb-4" />
                  <p className="text-[var(--text-muted)]">
                    Aucune chaîne surveillée. Ajoutez des streamers pour détecter leurs nouvelles VODs.
                  </p>
                </Card>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {channels.map((channel) => (
                    <Card
                      key={channel.id}
                      className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)]"
                    >
                      <div className="flex items-start gap-3">
                        {/* Avatar */}
                        <div className="w-12 h-12 rounded-full bg-[var(--bg-tertiary)] flex items-center justify-center overflow-hidden">
                          {channel.profileImageUrl ? (
                            <img
                              src={channel.profileImageUrl}
                              alt={channel.channelName}
                              className="w-full h-full object-cover"
                            />
                          ) : (
                            <PlatformIcon platform={channel.platform} />
                          )}
                        </div>
                        
                        {/* Info */}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <PlatformIcon platform={channel.platform} />
                            <span className="font-medium text-[var(--text-primary)] truncate">
                              {channel.displayName || channel.channelName}
                            </span>
                          </div>
                          <p className="text-xs text-[var(--text-muted)] mt-1">
                            @{channel.channelId}
                          </p>
                          {channel.lastCheckAt && (
                            <p className="text-xs text-[var(--text-muted)] mt-1 flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              {formatRelativeTime(channel.lastCheckAt)}
                            </p>
                          )}
                        </div>
                        
                        {/* Actions */}
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => handleCheckChannel(channel.id)}
                            disabled={checkingChannel === channel.id}
                            className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors disabled:opacity-50"
                            title="Vérifier maintenant"
                          >
                            {checkingChannel === channel.id ? (
                              <Loader2 className="w-4 h-4 animate-spin text-[var(--text-muted)]" />
                            ) : (
                              <RefreshCw className="w-4 h-4 text-[var(--text-muted)]" />
                            )}
                          </button>
                          <button
                            onClick={() => handleDeleteChannel(channel.id)}
                            className="p-2 rounded-lg hover:bg-red-500/10 transition-colors"
                            title="Supprimer"
                          >
                            <Trash2 className="w-4 h-4 text-red-400" />
                          </button>
                        </div>
                      </div>
                      
                      {/* Status badges */}
                      <div className="flex items-center gap-2 mt-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                          channel.enabled
                            ? 'bg-green-500/10 text-green-400'
                            : 'bg-gray-500/10 text-gray-400'
                        }`}>
                          {channel.enabled ? 'Actif' : 'Pausé'}
                        </span>
                        {channel.autoImport && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-blue-500/10 text-blue-400">
                            Auto-import
                          </span>
                        )}
                      </div>
                    </Card>
                  ))}
                </div>
              )}
            </section>
            
            {/* Detected VODs */}
            <section>
              <h2 className="text-lg font-medium text-[var(--text-primary)] mb-4">
                VODs détectées ({vods.length})
              </h2>
              
              {vods.length === 0 ? (
                <Card className="p-8 text-center bg-[var(--bg-card)]">
                  <Download className="w-12 h-12 mx-auto text-[var(--text-muted)] opacity-30 mb-4" />
                  <p className="text-[var(--text-muted)]">
                    Aucune nouvelle VOD détectée. Les VODs apparaîtront ici après vérification.
                  </p>
                </Card>
              ) : (
                <div className="space-y-3">
                  {vods.map((vod) => (
                    <motion.div
                      key={vod.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                    >
                      <Card className="p-4 bg-[var(--bg-card)] border border-[var(--border-color)]">
                        <div className="flex gap-4">
                          {/* Thumbnail */}
                          <div className="w-40 aspect-video rounded-lg overflow-hidden bg-[var(--bg-tertiary)] shrink-0">
                            {vod.thumbnailUrl ? (
                              <img
                                src={vod.thumbnailUrl}
                                alt={vod.title}
                                className="w-full h-full object-cover"
                              />
                            ) : (
                              <div className="w-full h-full flex items-center justify-center">
                                <PlatformIcon platform={vod.platform} />
                              </div>
                            )}
                          </div>
                          
                          {/* Info */}
                          <div className="flex-1 min-w-0">
                            <div className="flex items-start gap-2">
                              <PlatformIcon platform={vod.platform} />
                              <h3 className="font-medium text-[var(--text-primary)] line-clamp-2">
                                {vod.title}
                              </h3>
                            </div>
                            
                            <div className="flex items-center gap-3 mt-2 text-xs text-[var(--text-muted)]">
                              <span>{vod.channelName}</span>
                              {vod.duration && (
                                <>
                                  <span>•</span>
                                  <span>{formatDuration(vod.duration)}</span>
                                </>
                              )}
                              <span>•</span>
                              <span>{formatRelativeTime(vod.detectedAt)}</span>
                            </div>
                          </div>
                          
                          {/* Actions */}
                          <div className="flex items-center gap-2 shrink-0">
                            <Button
                              size="sm"
                              onClick={() => handleImportVOD(vod.id)}
                            >
                              <Download className="w-4 h-4 mr-1" />
                              Importer
                            </Button>
                            <button
                              onClick={() => handleIgnoreVOD(vod.id)}
                              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
                              title="Ignorer"
                            >
                              <X className="w-4 h-4 text-[var(--text-muted)]" />
                            </button>
                          </div>
                        </div>
                      </Card>
                    </motion.div>
                  ))}
                </div>
              )}
            </section>
          </div>
        )}
      </div>
      
      {/* Add Channel Modal */}
      <AddChannelModal
        isOpen={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdded={(channel) => {
          setChannels((prev) => [channel, ...prev]);
          setAddModalOpen(false);
        }}
      />
    </div>
  );
}


function AddChannelModal({
  isOpen,
  onClose,
  onAdded,
}: {
  isOpen: boolean;
  onClose: () => void;
  onAdded: (channel: WatchedChannel) => void;
}) {
  const { addToast } = useToastStore();
  
  const [platform, setPlatform] = useState<'twitch' | 'youtube'>('twitch');
  const [channelId, setChannelId] = useState('');
  const [autoImport, setAutoImport] = useState(false);
  const [checkInterval, setCheckInterval] = useState(3600);
  const [loading, setLoading] = useState(false);
  
  const handleSubmit = async () => {
    if (!channelId.trim()) return;
    
    setLoading(true);
    try {
      const response = await api.request<{ success: boolean; data: WatchedChannel }>('/channels', {
        method: 'POST',
        body: JSON.stringify({
          channel_id: channelId.trim(),
          channel_name: channelId.trim(),
          platform,
          auto_import: autoImport,
          check_interval: checkInterval,
          enabled: true,
        }),
      });
      
      if (response.success && response.data) {
        onAdded(response.data);
        addToast({
          type: 'success',
          title: 'Chaîne ajoutée',
          message: `${channelId} est maintenant surveillée`,
        });
        setChannelId('');
      }
    } catch (error) {
      addToast({
        type: 'error',
        title: 'Erreur',
        message: error instanceof Error ? error.message : 'Échec de l\'ajout',
      });
    } finally {
      setLoading(false);
    }
  };
  
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
          className="w-full max-w-md bg-[var(--bg-card)] border border-[var(--border-color)] rounded-2xl shadow-2xl overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)]">
            <h2 className="text-lg font-semibold text-[var(--text-primary)]">
              Ajouter une chaîne
            </h2>
            <button
              onClick={onClose}
              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X className="w-5 h-5 text-[var(--text-muted)]" />
            </button>
          </div>
          
          {/* Content */}
          <div className="p-6 space-y-4">
            {/* Platform select */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Plateforme
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => setPlatform('twitch')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border transition-all ${
                    platform === 'twitch'
                      ? 'border-purple-500 bg-purple-500/10 text-purple-400'
                      : 'border-[var(--border-color)] text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]'
                  }`}
                >
                  <Twitch className="w-5 h-5" />
                  Twitch
                </button>
                <button
                  onClick={() => setPlatform('youtube')}
                  className={`flex-1 flex items-center justify-center gap-2 px-4 py-3 rounded-xl border transition-all ${
                    platform === 'youtube'
                      ? 'border-red-500 bg-red-500/10 text-red-400'
                      : 'border-[var(--border-color)] text-[var(--text-muted)] hover:bg-[var(--bg-tertiary)]'
                  }`}
                >
                  <Youtube className="w-5 h-5" />
                  YouTube
                </button>
              </div>
            </div>
            
            {/* Channel ID */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Nom de la chaîne
              </label>
              <input
                type="text"
                value={channelId}
                onChange={(e) => setChannelId(e.target.value)}
                placeholder={platform === 'twitch' ? 'etostark' : 'EtoStarkTV'}
                className="w-full px-4 py-3 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] placeholder:text-[var(--text-muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              />
            </div>
            
            {/* Check interval */}
            <div>
              <label className="block text-sm font-medium text-[var(--text-secondary)] mb-2">
                Fréquence de vérification
              </label>
              <select
                value={checkInterval}
                onChange={(e) => setCheckInterval(Number(e.target.value))}
                className="w-full px-4 py-3 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-xl text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-blue-500/30"
              >
                <option value={3600}>Toutes les heures</option>
                <option value={21600}>Toutes les 6 heures</option>
                <option value={86400}>Une fois par jour</option>
              </select>
            </div>
            
            {/* Auto import */}
            <label className="flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={autoImport}
                onChange={(e) => setAutoImport(e.target.checked)}
                className="w-5 h-5 rounded border-[var(--border-color)] bg-[var(--bg-secondary)] text-blue-500 focus:ring-blue-500/30"
              />
              <div>
                <span className="text-sm text-[var(--text-primary)]">Import automatique</span>
                <p className="text-xs text-[var(--text-muted)]">
                  Importer automatiquement les nouvelles VODs
                </p>
              </div>
            </label>
          </div>
          
          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
            <Button variant="ghost" onClick={onClose}>
              Annuler
            </Button>
            <Button onClick={handleSubmit} disabled={!channelId.trim()} loading={loading}>
              <Plus className="w-4 h-4 mr-2" />
              Ajouter
            </Button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}

