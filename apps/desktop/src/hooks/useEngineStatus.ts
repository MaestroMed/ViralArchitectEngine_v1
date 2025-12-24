import { useEffect, useCallback } from 'react';
import { useEngineStore, useToastStore } from '@/store';
import { api } from '@/lib/api';

export function useEngineStatus() {
  const { setConnected, setServices } = useEngineStore();
  const { addToast } = useToastStore();

  const checkStatus = useCallback(async () => {
    try {
      const health = await api.checkHealth();
      setConnected(true);
      setServices(health.services);
    } catch {
      setConnected(false);
      setServices({
        ffmpeg: false,
        whisper: false,
        nvenc: false,
        database: false,
      });
    }
  }, [setConnected, setServices]);

  useEffect(() => {
    // Initial check
    checkStatus();

    // Poll every 10 seconds
    const interval = setInterval(checkStatus, 10000);

    return () => clearInterval(interval);
  }, [checkStatus]);

  const startEngine = useCallback(async () => {
    if (window.forge) {
      addToast({
        type: 'info',
        title: 'Démarrage du moteur...',
        message: 'FORGE Engine est en cours de démarrage',
      });

      const success = await window.forge.startEngine();
      
      if (success) {
        addToast({
          type: 'success',
          title: 'Moteur démarré',
          message: 'FORGE Engine est prêt',
        });
        await checkStatus();
      } else {
        addToast({
          type: 'error',
          title: 'Erreur',
          message: 'Impossible de démarrer le moteur',
        });
      }
    }
  }, [addToast, checkStatus]);

  return { checkStatus, startEngine };
}









