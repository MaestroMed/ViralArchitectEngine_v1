"use strict";
var __importDefault = (this && this.__importDefault) || function (mod) {
    return (mod && mod.__esModule) ? mod : { "default": mod };
};
Object.defineProperty(exports, "__esModule", { value: true });
const electron_1 = require("electron");
const path_1 = __importDefault(require("path"));
const child_process_1 = require("child_process");
let mainWindow = null;
let engineProcess = null;
const isDev = process.env.NODE_ENV === 'development' || !electron_1.app.isPackaged;
const ENGINE_PORT = 8420;
async function createWindow() {
    mainWindow = new electron_1.BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 1200,
        minHeight: 700,
        frame: false,
        titleBarStyle: 'hidden',
        titleBarOverlay: {
            color: '#FAFAF8',
            symbolColor: '#1A1A1A',
            height: 40,
        },
        backgroundColor: '#FAFAF8',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path_1.default.join(__dirname, 'preload.js'),
        },
    });
    // Load the app
    if (isDev) {
        mainWindow.loadURL('http://localhost:5173');
        mainWindow.webContents.openDevTools();
    }
    else {
        mainWindow.loadFile(path_1.default.join(__dirname, '../dist/index.html'));
    }
    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}
async function startEngine() {
    // Check if engine is already running
    try {
        const response = await fetch(`http://localhost:${ENGINE_PORT}/health`);
        if (response.ok) {
            console.log('Engine already running');
            return true;
        }
    }
    catch {
        // Engine not running, start it
    }
    console.log('Starting FORGE Engine...');
    const enginePath = isDev
        ? path_1.default.join(__dirname, '../../forge-engine')
        : path_1.default.join(process.resourcesPath, 'forge-engine');
    // Use venv Python in dev mode
    const pythonPath = isDev && process.platform === 'win32'
        ? path_1.default.join(enginePath, '.venv', 'Scripts', 'python.exe')
        : process.platform === 'win32' ? 'python' : 'python3';
    engineProcess = (0, child_process_1.spawn)(pythonPath, ['-m', 'uvicorn', 'forge_engine.main:app', '--host', '0.0.0.0', '--port', ENGINE_PORT.toString()], {
        cwd: enginePath,
        env: {
            ...process.env,
            PYTHONPATH: path_1.default.join(enginePath, 'src'),
            // Ensure FFmpeg is in PATH
            PATH: process.env.PATH,
        },
    });
    engineProcess.stdout?.on('data', (data) => {
        console.log(`[Engine] ${data}`);
    });
    engineProcess.stderr?.on('data', (data) => {
        console.error(`[Engine] ${data}`);
    });
    engineProcess.on('error', (error) => {
        console.error('Failed to start engine:', error);
    });
    // Wait for engine to be ready
    for (let i = 0; i < 30; i++) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        try {
            const response = await fetch(`http://localhost:${ENGINE_PORT}/health`);
            if (response.ok) {
                console.log('Engine started successfully');
                return true;
            }
        }
        catch {
            // Keep waiting
        }
    }
    console.error('Engine failed to start within timeout');
    return false;
}
function stopEngine() {
    if (engineProcess) {
        console.log('Stopping FORGE Engine...');
        engineProcess.kill();
        engineProcess = null;
    }
}
// IPC Handlers
electron_1.ipcMain.handle('app:get-version', () => electron_1.app.getVersion());
electron_1.ipcMain.handle('app:get-library-path', () => {
    return path_1.default.join(electron_1.app.getPath('home'), 'FORGE_LIBRARY');
});
electron_1.ipcMain.handle('file:open', async () => {
    if (!mainWindow)
        return null;
    const result = await electron_1.dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: 'Video Files', extensions: ['mp4', 'mkv', 'mov', 'avi', 'webm'] },
            { name: 'All Files', extensions: ['*'] },
        ],
    });
    return result.canceled ? null : result.filePaths[0];
});
electron_1.ipcMain.handle('file:select-directory', async () => {
    if (!mainWindow)
        return null;
    const result = await electron_1.dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
    });
    return result.canceled ? null : result.filePaths[0];
});
electron_1.ipcMain.handle('shell:open-path', async (_, path) => {
    return electron_1.shell.openPath(path);
});
electron_1.ipcMain.handle('shell:show-item', async (_, path) => {
    electron_1.shell.showItemInFolder(path);
});
electron_1.ipcMain.handle('engine:status', async () => {
    try {
        const response = await fetch(`http://localhost:${ENGINE_PORT}/health`);
        if (response.ok) {
            return { running: true, port: ENGINE_PORT };
        }
    }
    catch {
        // Engine not running
    }
    return { running: false, port: ENGINE_PORT };
});
electron_1.ipcMain.handle('engine:start', async () => {
    return startEngine();
});
electron_1.ipcMain.handle('engine:stop', async () => {
    stopEngine();
    return true;
});
// App lifecycle
electron_1.app.whenReady().then(async () => {
    await startEngine();
    await createWindow();
    electron_1.app.on('activate', () => {
        if (electron_1.BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});
electron_1.app.on('window-all-closed', () => {
    stopEngine();
    if (process.platform !== 'darwin') {
        electron_1.app.quit();
    }
});
electron_1.app.on('before-quit', () => {
    stopEngine();
});
