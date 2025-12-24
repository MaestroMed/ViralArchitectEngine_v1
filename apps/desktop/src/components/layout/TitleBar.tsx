import { useEngineStore } from '@/store';
import { ThemeToggle } from './ThemeToggle';

export default function TitleBar() {
  const { connected, services } = useEngineStore();

  return (
    <header className="h-10 bg-[var(--bg-card)] border-b border-[var(--border-color)] flex items-center px-4 drag-region">
      {/* Logo and title */}
      <div className="flex items-center gap-3 no-drag">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-[var(--accent)] flex items-center justify-center">
            <span className="text-[var(--bg-primary)] text-xs font-bold">F</span>
          </div>
          <span className="text-sm font-semibold tracking-tight text-[var(--text-primary)]">FORGE LAB</span>
        </div>
      </div>

      {/* Engine status + Theme toggle - décalé à gauche pour éviter les boutons Windows */}
      <div className="flex items-center gap-4 no-drag ml-8">
        {/* Service indicators */}
        <div className="flex items-center gap-3">
          <StatusDot label="Engine" active={connected} />
          <StatusDot label="GPU" active={services.nvenc} />
          <StatusDot label="Whisper" active={services.whisper} />
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-[var(--border-color)]" />

        {/* Theme toggle */}
        <ThemeToggle />
      </div>

      {/* Spacer - pousse le reste vers la gauche, loin des boutons Windows */}
      <div className="flex-1" />
      
      {/* Zone réservée pour les boutons Windows (150px environ) */}
      <div className="w-36" />
    </header>
  );
}

function StatusDot({ label, active }: { label: string; active: boolean }) {
  return (
    <div className="flex items-center gap-1.5">
      <div
        className={`w-2 h-2 rounded-full transition-all duration-300 ${
          active 
            ? 'bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)]' 
            : 'bg-[var(--text-muted)] opacity-40'
        }`}
      />
      <span className={`text-xs font-medium ${active ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}`}>
        {label}
      </span>
    </div>
  );
}


