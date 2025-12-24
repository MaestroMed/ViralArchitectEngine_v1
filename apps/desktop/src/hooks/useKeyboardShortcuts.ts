import { useHotkeys } from 'react-hotkeys-hook';
import { useClipEditorStore, useLayoutEditorStore, useUIStore, useThemeStore } from '@/store';

export function useKeyboardShortcuts() {
  const {
    isPlaying,
    setIsPlaying,
    playbackTime,
    setPlaybackTime,
    setTrimRange,
    trimStart,
    trimEnd,
    zoom,
    setZoom
  } = useClipEditorStore();

  const { setShortcutsModalOpen, setCurrentPanel } = useUIStore();
  const { toggleTheme } = useThemeStore();

  const { undo, redo } = useLayoutEditorStore.temporal?.getState() || { undo: () => {}, redo: () => {} };

  // Play/Pause
  useHotkeys('space', (e) => {
    e.preventDefault();
    setIsPlaying(!isPlaying);
  }, [isPlaying]);

  useHotkeys('k', (e) => {
    e.preventDefault();
    setIsPlaying(false);
  });

  // Navigation
  useHotkeys('j', () => setPlaybackTime(Math.max(0, playbackTime - 10)), [playbackTime]);
  useHotkeys('l', () => setPlaybackTime(playbackTime + 10), [playbackTime]);
  useHotkeys('left', () => setPlaybackTime(Math.max(0, playbackTime - 1)), [playbackTime]);
  useHotkeys('right', () => setPlaybackTime(playbackTime + 1), [playbackTime]);

  // Trimming
  useHotkeys('i', () => setTrimRange(playbackTime, trimEnd), [playbackTime, trimEnd]);
  useHotkeys('o', () => setTrimRange(trimStart, playbackTime), [playbackTime, trimStart]);

  // Zoom
  useHotkeys('ctrl+wheel', (e) => {
    // Note: wheel event handling might be better in the component directly, 
    // but hotkeys hook supports it? Not standard hotkey. 
    // Usually 'ctrl++' or 'ctrl+-'
  });
  useHotkeys('ctrl+=', (e) => {
    e.preventDefault();
    setZoom(zoom + 0.5);
  }, [zoom]);
  useHotkeys('ctrl+-', (e) => {
    e.preventDefault();
    setZoom(zoom - 0.5);
  }, [zoom]);

  // Undo/Redo (will be active once zundo is integrated)
  useHotkeys('ctrl+z', (e) => {
    e.preventDefault();
    if (useLayoutEditorStore.temporal) useLayoutEditorStore.temporal.getState().undo();
  });
  useHotkeys('ctrl+shift+z', (e) => {
    e.preventDefault();
    if (useLayoutEditorStore.temporal) useLayoutEditorStore.temporal.getState().redo();
  });
  useHotkeys('ctrl+y', (e) => {
    e.preventDefault();
    if (useLayoutEditorStore.temporal) useLayoutEditorStore.temporal.getState().redo();
  });

  // Shortcuts modal
  useHotkeys('shift+/', (e) => {
    e.preventDefault();
    setShortcutsModalOpen(true);
  });
  
  useHotkeys('escape', () => {
    setShortcutsModalOpen(false);
  });

  // Panel navigation
  useHotkeys('1', () => setCurrentPanel('ingest'));
  useHotkeys('2', () => setCurrentPanel('analyze'));
  useHotkeys('3', () => setCurrentPanel('forge'));
  useHotkeys('4', () => setCurrentPanel('export'));

  // Theme toggle
  useHotkeys('d', (e) => {
    // Only toggle if not in an input
    if ((e.target as HTMLElement).tagName !== 'INPUT' && (e.target as HTMLElement).tagName !== 'TEXTAREA') {
      toggleTheme();
    }
  });

  return {
    isPlaying
  };
}

