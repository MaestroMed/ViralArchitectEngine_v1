/// <reference types="vite/client" />

interface Window {
  forge: {
    getVersion: () => Promise<string>;
    getLibraryPath: () => Promise<string>;
    openFile: () => Promise<string | null>;
    selectDirectory: () => Promise<string | null>;
    openPath: (path: string) => Promise<string>;
    showItem: (path: string) => void;
    getEngineStatus: () => Promise<{ running: boolean; port: number }>;
    startEngine: () => Promise<boolean>;
    stopEngine: () => Promise<boolean>;
    platform: NodeJS.Platform;
  };
}









