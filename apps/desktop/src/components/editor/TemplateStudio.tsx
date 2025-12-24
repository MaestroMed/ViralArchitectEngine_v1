import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Save,
  FolderOpen,
  Trash2,
  Copy,
  Plus,
  Check,
  X,
  Layers,
  Type,
  Star,
} from 'lucide-react';
import { Button } from '@/components/ui/Button';
import { useLayoutEditorStore, useSubtitleStyleStore } from '@/store';

interface Template {
  id: string;
  name: string;
  description?: string;
  isFavorite: boolean;
  createdAt: string;
  layout: {
    zones: Array<{
      id: string;
      type: string;
      x: number;
      y: number;
      width: number;
      height: number;
    }>;
  };
  subtitles: {
    fontFamily: string;
    fontSize: number;
    fontWeight: number;
    color: string;
    backgroundColor: string;
    outlineColor: string;
    outlineWidth: number;
    position: string;
    animation: string;
    highlightColor: string;
  };
}

const STORAGE_KEY = 'forge-templates';

export function TemplateStudio() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [isCreating, setIsCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { zones, setZones } = useLayoutEditorStore();
  const { style: subtitleStyle, setStyle: setSubtitleStyle } = useSubtitleStyleStore();

  // Load templates from localStorage
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setTemplates(JSON.parse(stored));
      } catch (e) {
        console.error('Failed to parse templates:', e);
      }
    }
  }, []);

  // Save templates to localStorage
  const saveTemplates = (newTemplates: Template[]) => {
    setTemplates(newTemplates);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newTemplates));
  };

  const handleSaveTemplate = () => {
    if (!newName.trim()) return;

    const template: Template = {
      id: crypto.randomUUID(),
      name: newName.trim(),
      isFavorite: false,
      createdAt: new Date().toISOString(),
      layout: { zones: [...zones] },
      subtitles: { ...subtitleStyle },
    };

    saveTemplates([template, ...templates]);
    setNewName('');
    setIsCreating(false);
  };

  const handleLoadTemplate = (template: Template) => {
    setZones(template.layout.zones);
    setSubtitleStyle(template.subtitles);
    setSelectedId(template.id);
  };

  const handleDeleteTemplate = (id: string) => {
    saveTemplates(templates.filter((t) => t.id !== id));
    if (selectedId === id) setSelectedId(null);
  };

  const handleToggleFavorite = (id: string) => {
    saveTemplates(
      templates.map((t) =>
        t.id === id ? { ...t, isFavorite: !t.isFavorite } : t
      )
    );
  };

  const handleDuplicate = (template: Template) => {
    const copy: Template = {
      ...template,
      id: crypto.randomUUID(),
      name: `${template.name} (copie)`,
      createdAt: new Date().toISOString(),
      isFavorite: false,
    };
    saveTemplates([copy, ...templates]);
  };

  const favoriteTemplates = templates.filter((t) => t.isFavorite);
  const otherTemplates = templates.filter((t) => !t.isFavorite);

  return (
    <div className="h-full flex flex-col bg-[var(--bg-card)] rounded-xl border border-[var(--border-color)]">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border-color)]">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-[var(--text-primary)]">Templates</h3>
          <span className="text-xs text-[var(--text-muted)]">{templates.length} sauvegardés</span>
        </div>

        {/* Save current */}
        {isCreating ? (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="Nom du template..."
              className="flex-1 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)]"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleSaveTemplate();
                if (e.key === 'Escape') setIsCreating(false);
              }}
            />
            <button
              onClick={handleSaveTemplate}
              className="p-2 bg-green-500 rounded-lg hover:bg-green-600 transition-colors"
            >
              <Check className="w-4 h-4 text-white" />
            </button>
            <button
              onClick={() => setIsCreating(false)}
              className="p-2 bg-[var(--bg-tertiary)] rounded-lg hover:bg-[var(--bg-secondary)] transition-colors"
            >
              <X className="w-4 h-4 text-[var(--text-muted)]" />
            </button>
          </div>
        ) : (
          <Button
            onClick={() => setIsCreating(true)}
            className="w-full flex items-center justify-center gap-2"
            size="sm"
          >
            <Save className="w-4 h-4" />
            Sauvegarder le layout actuel
          </Button>
        )}
      </div>

      {/* Template list */}
      <div className="flex-1 overflow-auto p-4">
        {templates.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Layers className="w-12 h-12 text-[var(--text-muted)] opacity-30 mb-4" />
            <p className="text-[var(--text-muted)]">Aucun template</p>
            <p className="text-xs text-[var(--text-muted)] mt-1">
              Créez un layout et sauvegardez-le
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Favorites */}
            {favoriteTemplates.length > 0 && (
              <div>
                <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2 flex items-center gap-1">
                  <Star className="w-3 h-3" /> Favoris
                </h4>
                <div className="space-y-2">
                  {favoriteTemplates.map((template) => (
                    <TemplateCard
                      key={template.id}
                      template={template}
                      isSelected={selectedId === template.id}
                      onLoad={() => handleLoadTemplate(template)}
                      onDelete={() => handleDeleteTemplate(template.id)}
                      onToggleFavorite={() => handleToggleFavorite(template.id)}
                      onDuplicate={() => handleDuplicate(template)}
                    />
                  ))}
                </div>
              </div>
            )}

            {/* Others */}
            {otherTemplates.length > 0 && (
              <div>
                {favoriteTemplates.length > 0 && (
                  <h4 className="text-xs font-medium text-[var(--text-muted)] mb-2">
                    Autres templates
                  </h4>
                )}
                <div className="space-y-2">
                  {otherTemplates.map((template) => (
                    <TemplateCard
                      key={template.id}
                      template={template}
                      isSelected={selectedId === template.id}
                      onLoad={() => handleLoadTemplate(template)}
                      onDelete={() => handleDeleteTemplate(template.id)}
                      onToggleFavorite={() => handleToggleFavorite(template.id)}
                      onDuplicate={() => handleDuplicate(template)}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Footer tip */}
      <div className="p-3 border-t border-[var(--border-color)] bg-[var(--bg-secondary)]">
        <p className="text-xs text-[var(--text-muted)]">
          💡 Les templates sauvegardent le layout des zones ET les styles de sous-titres
        </p>
      </div>
    </div>
  );
}

function TemplateCard({
  template,
  isSelected,
  onLoad,
  onDelete,
  onToggleFavorite,
  onDuplicate,
}: {
  template: Template;
  isSelected: boolean;
  onLoad: () => void;
  onDelete: () => void;
  onToggleFavorite: () => void;
  onDuplicate: () => void;
}) {
  const zonesCount = template.layout.zones.length;
  const date = new Date(template.createdAt).toLocaleDateString();

  return (
    <motion.div
      layout
      className={`p-3 rounded-lg transition-colors cursor-pointer group ${
        isSelected
          ? 'bg-blue-500/20 border border-blue-500'
          : 'bg-[var(--bg-secondary)] border border-transparent hover:bg-[var(--bg-tertiary)]'
      }`}
      onClick={onLoad}
    >
      <div className="flex items-center gap-3">
        {/* Preview mini */}
        <div className="w-10 h-16 bg-black rounded overflow-hidden flex-shrink-0 relative">
          {template.layout.zones.map((zone, i) => (
            <div
              key={zone.id}
              className={`absolute ${
                zone.type === 'facecam' ? 'bg-purple-500/50' : 'bg-blue-500/50'
              }`}
              style={{
                left: `${zone.x}%`,
                top: `${zone.y}%`,
                width: `${zone.width}%`,
                height: `${zone.height}%`,
              }}
            />
          ))}
        </div>

        {/* Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-[var(--text-primary)] truncate">
              {template.name}
            </span>
            {isSelected && (
              <Check className="w-4 h-4 text-blue-400 flex-shrink-0" />
            )}
          </div>
          <div className="text-xs text-[var(--text-muted)] mt-0.5">
            {zonesCount} zones • {date}
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onToggleFavorite();
            }}
            className={`p-1.5 rounded-lg transition-colors ${
              template.isFavorite ? 'text-amber-400' : 'text-[var(--text-muted)] hover:text-amber-400'
            }`}
            title={template.isFavorite ? 'Retirer des favoris' : 'Ajouter aux favoris'}
          >
            <Star className={`w-4 h-4 ${template.isFavorite ? 'fill-current' : ''}`} />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDuplicate();
            }}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            title="Dupliquer"
          >
            <Copy className="w-4 h-4" />
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-red-400 transition-colors"
            title="Supprimer"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>
    </motion.div>
  );
}

export default TemplateStudio;





