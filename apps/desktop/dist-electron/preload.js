"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
// Expose protected methods to renderer
electron_1.contextBridge.exposeInMainWorld('forge', {
    // App info
    getVersion: () => electron_1.ipcRenderer.invoke('app:get-version'),
    getLibraryPath: () => electron_1.ipcRenderer.invoke('app:get-library-path'),
    // File operations
    openFile: () => electron_1.ipcRenderer.invoke('file:open'),
    selectDirectory: () => electron_1.ipcRenderer.invoke('file:select-directory'),
    // Shell
    openPath: (path) => electron_1.ipcRenderer.invoke('shell:open-path', path),
    showItem: (path) => electron_1.ipcRenderer.invoke('shell:show-item', path),
    // Engine
    getEngineStatus: () => electron_1.ipcRenderer.invoke('engine:status'),
    startEngine: () => electron_1.ipcRenderer.invoke('engine:start'),
    stopEngine: () => electron_1.ipcRenderer.invoke('engine:stop'),
    // Platform info
    platform: process.platform,
});
