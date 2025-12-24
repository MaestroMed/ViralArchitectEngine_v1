import { ReactNode } from 'react';
import { motion } from 'framer-motion';
import Sidebar from './Sidebar';
import TitleBar from './TitleBar';
import StatusBar from './StatusBar';
import JobDrawer from './JobDrawer';
import ShortcutsModal from '@/components/ui/ShortcutsModal';

interface LayoutProps {
  children: ReactNode;
}

export default function Layout({ children }: LayoutProps) {
  return (
    <div className="h-screen flex flex-col bg-[var(--bg-primary)] text-[var(--text-primary)]">
      {/* Title bar */}
      <TitleBar />

      <div className="flex-1 flex overflow-hidden">
        {/* Sidebar */}
        <Sidebar />

        {/* Main content */}
        <main className="flex-1 overflow-auto bg-[var(--bg-secondary)]">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="h-full"
          >
            {children}
          </motion.div>
        </main>
      </div>

      {/* Status bar */}
      <StatusBar />

      {/* Job drawer */}
      <JobDrawer />

      {/* Shortcuts modal */}
      <ShortcutsModal />
    </div>
  );
}


