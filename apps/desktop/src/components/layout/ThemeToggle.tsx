import { Moon, Sun } from 'lucide-react';
import { useThemeStore } from '@/store';
import { motion } from 'framer-motion';

export function ThemeToggle() {
  const { theme, toggleTheme } = useThemeStore();
  const isDark = theme === 'dark';

  return (
    <button
      onClick={toggleTheme}
      className="relative p-2 rounded-lg transition-colors hover:bg-[var(--bg-tertiary)]"
      aria-label={isDark ? 'Passer en mode clair' : 'Passer en mode sombre'}
    >
      <motion.div
        initial={false}
        animate={{ rotate: isDark ? 180 : 0 }}
        transition={{ duration: 0.3, ease: 'easeInOut' }}
      >
        {isDark ? (
          <Moon className="w-4 h-4 text-[var(--text-secondary)]" />
        ) : (
          <Sun className="w-4 h-4 text-[var(--text-secondary)]" />
        )}
      </motion.div>
    </button>
  );
}








