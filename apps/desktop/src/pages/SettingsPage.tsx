import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/Card';
import { api } from '@/lib/api';
import { useEngineStore, useToastStore } from '@/store';
import { FolderOpen, Cpu, HardDrive, RefreshCw } from 'lucide-react';

export default function SettingsPage() {
  const { connected, services } = useEngineStore();
  const { addToast } = useToastStore();
  const [libraryPath, setLibraryPath] = useState('');
  const [capabilities, setCapabilities] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadSettings();
  }, []);

  const loadSettings = async () => {
    try {
      // Get library path
      if (window.forge) {
        const path = await window.forge.getLibraryPath();
        setLibraryPath(path);
      }

      // Get capabilities
      if (connected) {
        const caps = await api.getCapabilities();
        setCapabilities(caps);
      }
    } catch (error) {
      console.error('Failed to load settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const selectLibraryPath = async () => {
    if (!window.forge) return;
    
    const path = await window.forge.selectDirectory();
    if (path) {
      setLibraryPath(path);
      addToast({
        type: 'info',
        title: 'Chemin mis à jour',
        message: 'Redémarrez l\'application pour appliquer le changement',
      });
    }
  };

  const openLibrary = async () => {
    if (window.forge && libraryPath) {
      await window.forge.openPath(libraryPath);
    }
  };

  return (
    <div className="h-full overflow-auto">
      <div className="max-w-3xl mx-auto p-8">
        <h1 className="text-2xl font-semibold text-[var(--text-primary)] mb-2">Paramètres</h1>
        <p className="text-[var(--text-muted)] mb-8">
          Configuration de FORGE LAB
        </p>

        <div className="space-y-6">
          {/* Storage */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <HardDrive className="w-5 h-5" />
                Stockage
              </CardTitle>
              <CardDescription>
                Emplacement des projets et fichiers générés
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="text-sm font-medium text-[var(--text-primary)] block mb-2">
                  Dossier Library
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={libraryPath}
                    readOnly
                    className="input flex-1"
                  />
                  <Button variant="secondary" onClick={selectLibraryPath}>
                    Changer
                  </Button>
                  <Button variant="ghost" size="icon" onClick={openLibrary}>
                    <FolderOpen className="w-4 h-4" />
                  </Button>
                </div>
              </div>

              {capabilities?.storage && (
                <div className="text-sm text-[var(--text-muted)]">
                  Espace libre : {formatBytes(capabilities.storage.freeSpace)}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Engine Status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="w-5 h-5" />
                Moteur FORGE
              </CardTitle>
              <CardDescription>
                État des services et capacités
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <StatusItem
                  label="Moteur"
                  status={connected}
                  detail={connected ? 'Connecté' : 'Déconnecté'}
                />
                <StatusItem
                  label="FFmpeg"
                  status={services.ffmpeg}
                  detail={capabilities?.ffmpeg?.version || 'Non détecté'}
                />
                <StatusItem
                  label="NVENC (GPU)"
                  status={services.nvenc}
                  detail={
                    capabilities?.gpu?.available
                      ? capabilities.gpu.name
                      : 'Non disponible'
                  }
                />
                <StatusItem
                  label="Whisper"
                  status={services.whisper}
                  detail={capabilities?.whisper?.currentModel || 'Non chargé'}
                />
              </div>

              <Button
                variant="secondary"
                className="mt-4"
                onClick={loadSettings}
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Actualiser
              </Button>
            </CardContent>
          </Card>

          {/* About */}
          <Card>
            <CardHeader>
              <CardTitle>À propos</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-[var(--text-muted)]">
              <p>
                <strong className="text-[var(--text-primary)]">FORGE LAB</strong> v1.0.0
              </p>
              <p>
                Atelier de viralité local pour créer des clips optimisés
                à partir de VODs.
              </p>
              <p className="text-xs">
                © 2024 FORGE LAB. Tous droits réservés.
              </p>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatusItem({
  label,
  status,
  detail,
}: {
  label: string;
  status: boolean;
  detail: string;
}) {
  return (
    <div className="flex items-center gap-3 p-3 bg-[var(--bg-secondary)] rounded-lg border border-[var(--border-color)]">
      <div
        className={`w-3 h-3 rounded-full transition-all duration-300 ${
          status 
            ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' 
            : 'bg-[var(--text-muted)]'
        }`}
      />
      <div>
        <div className="text-sm font-medium text-[var(--text-primary)]">{label}</div>
        <div className={`text-xs ${status ? 'text-emerald-400' : 'text-[var(--text-muted)]'}`}>
          {detail}
        </div>
      </div>
    </div>
  );
}

function formatBytes(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let unitIndex = 0;
  let size = bytes;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }

  return `${size.toFixed(1)} ${units[unitIndex]}`;
}


