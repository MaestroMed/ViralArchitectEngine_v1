import { motion, AnimatePresence } from 'framer-motion';
import { Download, Trash2, Tag, X, CheckSquare } from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useBatchSelectionStore } from '@/store';
import { api } from '@/lib/api';

interface BatchActionBarProps {
  projectId: string;
  onExportSelected: (ids: string[]) => void;
  onDeleteSelected?: (ids: string[]) => void;
}

export default function BatchActionBar({
  projectId,
  onExportSelected,
  onDeleteSelected,
}: BatchActionBarProps) {
  const { selectedIds, clearSelection, isSelectionMode, setSelectionMode } =
    useBatchSelectionStore();

  const count = selectedIds.size;

  if (!isSelectionMode && count === 0) return null;

  return (
    <AnimatePresence>
      {(isSelectionMode || count > 0) && (
        <motion.div
          initial={{ y: 100, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: 100, opacity: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="fixed bottom-20 left-1/2 -translate-x-1/2 z-40"
        >
          <div className="glass px-4 py-3 rounded-2xl shadow-2xl flex items-center gap-4">
            {/* Selection count */}
            <div className="flex items-center gap-2 px-3 py-1.5 bg-[var(--accent-color)]/10 rounded-lg">
              <CheckSquare className="w-4 h-4 text-[var(--accent-color)]" />
              <span className="text-sm font-medium text-[var(--text-primary)]">
                {count} sélectionné{count > 1 ? 's' : ''}
              </span>
            </div>

            {/* Separator */}
            <div className="w-px h-8 bg-[var(--border-color)]" />

            {/* Actions */}
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => onExportSelected(Array.from(selectedIds))}
                disabled={count === 0}
              >
                <Download className="w-4 h-4 mr-1.5" />
                Exporter
              </Button>

              {onDeleteSelected && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onDeleteSelected(Array.from(selectedIds))}
                  disabled={count === 0}
                  className="text-red-400 hover:text-red-300 hover:bg-red-500/10"
                >
                  <Trash2 className="w-4 h-4 mr-1.5" />
                  Supprimer
                </Button>
              )}
            </div>

            {/* Separator */}
            <div className="w-px h-8 bg-[var(--border-color)]" />

            {/* Cancel */}
            <button
              onClick={clearSelection}
              className="p-2 hover:bg-[var(--bg-tertiary)] rounded-lg transition-colors"
              title="Annuler la sélection"
            >
              <X className="w-4 h-4 text-[var(--text-muted)]" />
            </button>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}




