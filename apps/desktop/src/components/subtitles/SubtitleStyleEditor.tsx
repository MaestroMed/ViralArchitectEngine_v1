import { useState } from 'react';
import { useSubtitleStyleStore } from '@/store';
import { motion } from 'framer-motion';
import { Type, Palette, AlignCenter, Sparkles } from 'lucide-react';

const FONTS = [
  'Inter',
  'Impact',
  'Arial Black',
  'Montserrat',
  'Bebas Neue',
  'Roboto',
  'Open Sans',
  'Poppins',
];

const ANIMATION_OPTIONS = [
  { id: 'none', name: 'Aucune' },
  { id: 'fade', name: 'Fondu' },
  { id: 'pop', name: 'Pop' },
  { id: 'bounce', name: 'Rebond' },
  { id: 'typewriter', name: 'Machine à écrire' },
];

const POSITION_OPTIONS = [
  { id: 'bottom', name: 'Bas' },
  { id: 'center', name: 'Centre' },
  { id: 'top', name: 'Haut' },
];

const PRESETS = [
  { id: 'default', name: 'Standard', preview: { bg: 'transparent', color: '#FFF', outline: '#000' } },
  { id: 'mrbeast', name: 'MrBeast', preview: { bg: 'transparent', color: '#FFF', outline: '#000' } },
  { id: 'minimalist', name: 'Minimaliste', preview: { bg: 'rgba(0,0,0,0.6)', color: '#FFF', outline: 'transparent' } },
  { id: 'karaoke', name: 'Karaoké', preview: { bg: 'transparent', color: '#FFF', outline: '#000' } },
];

export function SubtitleStyleEditor() {
  const { style, presetName, setStyle, applyPreset } = useSubtitleStyleStore();
  const [activeTab, setActiveTab] = useState<'presets' | 'font' | 'color' | 'animation'>('presets');

  return (
    <div className="space-y-4">
      {/* Tabs */}
      <div className="flex items-center gap-1 p-1 bg-[var(--bg-tertiary)] rounded-lg">
        <TabButton
          active={activeTab === 'presets'}
          onClick={() => setActiveTab('presets')}
          icon={<Sparkles className="w-4 h-4" />}
          label="Presets"
        />
        <TabButton
          active={activeTab === 'font'}
          onClick={() => setActiveTab('font')}
          icon={<Type className="w-4 h-4" />}
          label="Police"
        />
        <TabButton
          active={activeTab === 'color'}
          onClick={() => setActiveTab('color')}
          icon={<Palette className="w-4 h-4" />}
          label="Couleurs"
        />
        <TabButton
          active={activeTab === 'animation'}
          onClick={() => setActiveTab('animation')}
          icon={<AlignCenter className="w-4 h-4" />}
          label="Animation"
        />
      </div>

      {/* Tab content */}
      <div className="min-h-[200px]">
        {activeTab === 'presets' && (
          <div className="grid grid-cols-2 gap-2">
            {PRESETS.map((preset) => (
              <motion.button
                key={preset.id}
                className={`p-3 rounded-lg text-left transition-colors ${
                  presetName === preset.id
                    ? 'bg-blue-500/20 ring-2 ring-blue-500'
                    : 'bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)]'
                }`}
                onClick={() => applyPreset(preset.id)}
                whileHover={{ scale: 1.02 }}
              >
                {/* Preview */}
                <div
                  className="h-8 rounded flex items-center justify-center text-sm font-bold mb-2"
                  style={{
                    backgroundColor: preset.preview.bg,
                    color: preset.preview.color,
                    textShadow:
                      preset.preview.outline !== 'transparent'
                        ? `2px 2px 0 ${preset.preview.outline}, -2px 2px 0 ${preset.preview.outline}, 2px -2px 0 ${preset.preview.outline}, -2px -2px 0 ${preset.preview.outline}`
                        : 'none',
                  }}
                >
                  Exemple
                </div>
                <span className="text-sm font-medium text-[var(--text-primary)]">{preset.name}</span>
              </motion.button>
            ))}
          </div>
        )}

        {activeTab === 'font' && (
          <div className="space-y-4">
            {/* Font family */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Police
              </label>
              <select
                value={style.fontFamily}
                onChange={(e) => setStyle({ fontFamily: e.target.value })}
                className="w-full px-3 py-2 bg-[var(--bg-secondary)] border border-[var(--border-color)] rounded-lg text-[var(--text-primary)]"
              >
                {FONTS.map((font) => (
                  <option key={font} value={font} style={{ fontFamily: font }}>
                    {font}
                  </option>
                ))}
              </select>
            </div>

            {/* Font size */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Taille: {style.fontSize}px
              </label>
              <input
                type="range"
                min="24"
                max="72"
                value={style.fontSize}
                onChange={(e) => setStyle({ fontSize: Number(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Font weight */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Épaisseur: {style.fontWeight}
              </label>
              <input
                type="range"
                min="400"
                max="900"
                step="100"
                value={style.fontWeight}
                onChange={(e) => setStyle({ fontWeight: Number(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Position */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Position
              </label>
              <div className="flex gap-2">
                {POSITION_OPTIONS.map((pos) => (
                  <button
                    key={pos.id}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors ${
                      style.position === pos.id
                        ? 'bg-blue-500 text-white'
                        : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)] hover:bg-[var(--bg-tertiary)]'
                    }`}
                    onClick={() => setStyle({ position: pos.id as 'bottom' | 'center' | 'top' })}
                  >
                    {pos.name}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'color' && (
          <div className="space-y-4">
            {/* Text color */}
            <ColorPicker
              label="Couleur du texte"
              value={style.color}
              onChange={(color) => setStyle({ color })}
            />

            {/* Outline color */}
            <ColorPicker
              label="Couleur du contour"
              value={style.outlineColor}
              onChange={(color) => setStyle({ outlineColor: color })}
            />

            {/* Outline width */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Épaisseur du contour: {style.outlineWidth}px
              </label>
              <input
                type="range"
                min="0"
                max="6"
                value={style.outlineWidth}
                onChange={(e) => setStyle({ outlineWidth: Number(e.target.value) })}
                className="w-full"
              />
            </div>

            {/* Highlight color */}
            <ColorPicker
              label="Couleur de surbrillance (mot actuel)"
              value={style.highlightColor}
              onChange={(color) => setStyle({ highlightColor: color })}
            />

            {/* Background */}
            <div>
              <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
                Fond
              </label>
              <div className="flex gap-2">
                <button
                  className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                    style.backgroundColor === 'transparent'
                      ? 'bg-blue-500 text-white'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)]'
                  }`}
                  onClick={() => setStyle({ backgroundColor: 'transparent' })}
                >
                  Transparent
                </button>
                <button
                  className={`flex-1 py-2 rounded-lg text-sm transition-colors ${
                    style.backgroundColor !== 'transparent'
                      ? 'bg-blue-500 text-white'
                      : 'bg-[var(--bg-secondary)] text-[var(--text-secondary)]'
                  }`}
                  onClick={() => setStyle({ backgroundColor: 'rgba(0,0,0,0.6)' })}
                >
                  Fond sombre
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'animation' && (
          <div className="space-y-4">
            <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">
              Style d'animation
            </label>
            <div className="grid grid-cols-2 gap-2">
              {ANIMATION_OPTIONS.map((anim) => (
                <motion.button
                  key={anim.id}
                  className={`p-3 rounded-lg text-center transition-colors ${
                    style.animation === anim.id
                      ? 'bg-blue-500/20 ring-2 ring-blue-500'
                      : 'bg-[var(--bg-secondary)] hover:bg-[var(--bg-tertiary)]'
                  }`}
                  onClick={() => setStyle({ animation: anim.id as any })}
                  whileHover={{ scale: 1.02 }}
                >
                  <span className="text-sm font-medium text-[var(--text-primary)]">{anim.name}</span>
                </motion.button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Live preview */}
      <div className="p-4 bg-gray-900 rounded-lg">
        <p className="text-center text-xs text-gray-500 mb-2">Aperçu</p>
        <p
          className="text-center"
          style={{
            fontFamily: style.fontFamily,
            fontSize: `${style.fontSize / 2}px`,
            fontWeight: style.fontWeight,
            color: style.color,
            backgroundColor: style.backgroundColor,
            textShadow:
              style.outlineWidth > 0
                ? `${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor},
                   -${style.outlineWidth}px ${style.outlineWidth}px 0 ${style.outlineColor},
                   ${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor},
                   -${style.outlineWidth}px -${style.outlineWidth}px 0 ${style.outlineColor}`
                : 'none',
            padding: '8px',
            borderRadius: '4px',
          }}
        >
          C'est <span style={{ color: style.highlightColor }}>incroyable</span> ce truc !
        </p>
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg text-xs font-medium transition-colors ${
        active
          ? 'bg-[var(--bg-card)] text-[var(--text-primary)]'
          : 'text-[var(--text-muted)] hover:text-[var(--text-secondary)]'
      }`}
      onClick={onClick}
    >
      {icon}
      {label}
    </button>
  );
}

function ColorPicker({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (color: string) => void;
}) {
  const presetColors = ['#FFFFFF', '#000000', '#FF0000', '#00FF00', '#0000FF', '#FFFF00', '#FF00FF', '#00FFFF'];

  return (
    <div>
      <label className="block text-xs font-medium text-[var(--text-muted)] mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-10 h-10 rounded cursor-pointer"
        />
        <div className="flex gap-1">
          {presetColors.map((color) => (
            <button
              key={color}
              className={`w-6 h-6 rounded border-2 transition-transform hover:scale-110 ${
                value === color ? 'border-blue-500' : 'border-transparent'
              }`}
              style={{ backgroundColor: color }}
              onClick={() => onChange(color)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}








