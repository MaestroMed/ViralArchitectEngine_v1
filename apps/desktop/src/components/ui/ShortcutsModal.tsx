import { motion, AnimatePresence } from 'framer-motion';
import { X, Keyboard } from 'lucide-react';
import { useUIStore } from '@/store';

const SHORTCUTS = [
  {
    category: 'Lecture',
    shortcuts: [
      { keys: ['Espace'], description: 'Lecture / Pause' },
      { keys: ['J'], description: 'Reculer de 5s' },
      { keys: ['K'], description: 'Lecture / Pause' },
      { keys: ['L'], description: 'Avancer de 5s' },
      { keys: ['←'], description: 'Reculer de 1s' },
      { keys: ['→'], description: 'Avancer de 1s' },
    ],
  },
  {
    category: 'Édition',
    shortcuts: [
      { keys: ['I'], description: 'Définir le point d\'entrée' },
      { keys: ['O'], description: 'Définir le point de sortie' },
      { keys: ['Ctrl', 'Z'], description: 'Annuler' },
      { keys: ['Ctrl', 'Shift', 'Z'], description: 'Rétablir' },
    ],
  },
  {
    category: 'Navigation',
    shortcuts: [
      { keys: ['1'], description: 'Panel Ingest' },
      { keys: ['2'], description: 'Panel Analyze' },
      { keys: ['3'], description: 'Panel Forge' },
      { keys: ['4'], description: 'Panel Export' },
    ],
  },
  {
    category: 'Export',
    shortcuts: [
      { keys: ['E'], description: 'Exporter le segment' },
      { keys: ['Ctrl', 'E'], description: 'Export rapide' },
    ],
  },
  {
    category: 'Interface',
    shortcuts: [
      { keys: ['?'], description: 'Afficher les raccourcis' },
      { keys: ['Échap'], description: 'Fermer le modal / Annuler' },
      { keys: ['D'], description: 'Basculer Dark Mode' },
    ],
  },
];

export default function ShortcutsModal() {
  const { shortcutsModalOpen, setShortcutsModalOpen } = useUIStore();

  if (!shortcutsModalOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4"
        onClick={() => setShortcutsModalOpen(false)}
      >
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          className="glass rounded-2xl w-full max-w-2xl max-h-[80vh] overflow-hidden shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-6 border-b border-[var(--border-color)]">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-viral flex items-center justify-center">
                <Keyboard className="w-5 h-5 text-white" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-[var(--text-primary)] font-display">
                  Raccourcis clavier
                </h2>
                <p className="text-sm text-[var(--text-muted)]">
                  Appuyez sur ? pour afficher ce menu
                </p>
              </div>
            </div>
            <button
              onClick={() => setShortcutsModalOpen(false)}
              className="p-2 rounded-lg hover:bg-[var(--bg-tertiary)] transition-colors"
            >
              <X className="w-5 h-5 text-[var(--text-muted)]" />
            </button>
          </div>

          {/* Content */}
          <div className="p-6 max-h-[60vh] overflow-auto scrollbar-thin">
            <div className="grid grid-cols-2 gap-6">
              {SHORTCUTS.map((group) => (
                <div key={group.category}>
                  <h3 className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-3">
                    {group.category}
                  </h3>
                  <div className="space-y-2">
                    {group.shortcuts.map((shortcut, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between py-1.5"
                      >
                        <span className="text-sm text-[var(--text-secondary)]">
                          {shortcut.description}
                        </span>
                        <div className="flex items-center gap-1">
                          {shortcut.keys.map((key, keyIdx) => (
                            <span key={keyIdx}>
                              <kbd className="px-2 py-1 bg-[var(--bg-tertiary)] border border-[var(--border-color)] rounded text-xs font-mono text-[var(--text-primary)]">
                                {key}
                              </kbd>
                              {keyIdx < shortcut.keys.length - 1 && (
                                <span className="mx-1 text-[var(--text-muted)]">+</span>
                              )}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Footer */}
          <div className="px-6 py-4 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
            <p className="text-xs text-[var(--text-muted)] text-center">
              Appuyez sur <kbd className="px-1.5 py-0.5 bg-[var(--bg-tertiary)] rounded text-xs font-mono">Échap</kbd> pour fermer
            </p>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}




