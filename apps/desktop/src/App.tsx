import { Routes, Route } from 'react-router-dom';
import { AnimatePresence } from 'framer-motion';
import { Toaster } from '@/components/ui/Toaster';
import Layout from '@/components/layout/Layout';
import HomePage from '@/pages/HomePage';
import ProjectPage from '@/pages/ProjectPage';
import SettingsPage from '@/pages/SettingsPage';
import ClipEditorPage from '@/pages/ClipEditorPage';
import { useEngineStatus } from '@/hooks/useEngineStatus';
import { useWebSocketStore } from '@/store';
import { useEffect } from 'react';

export default function App() {
  // Check engine status on mount
  useEngineStatus();
  
  // Connect to WebSocket
  const { connect } = useWebSocketStore();
  useEffect(() => {
    connect();
    
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }, [connect]);

  return (
    <>
      <Layout>
        <AnimatePresence mode="wait">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/project/:id/*" element={<ProjectPage />} />
            <Route path="/editor/:projectId" element={<ClipEditorPage />} />
            <Route path="/settings" element={<SettingsPage />} />
          </Routes>
        </AnimatePresence>
      </Layout>
      <Toaster />
    </>
  );
}


