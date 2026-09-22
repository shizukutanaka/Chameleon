const { contextBridge, ipcRenderer } = require('electron');

// Menu channels the main process can send (see createMenu in main.js)
const MENU_CHANNELS = [
  'menu-open-file',
  'menu-export',
  'menu-analyze',
  'menu-normalize',
  'menu-batch',
  'menu-audit-log',
  'menu-security-settings',
  'menu-change-password'
];

// Secure context bridge: only methods with a matching ipcMain.handle in
// main.js are exposed.
contextBridge.exposeInMainWorld('electronAPI', {
  // Authentication
  authenticate: (credentials) => ipcRenderer.invoke('authenticate', credentials),
  getUserInfo: () => ipcRenderer.invoke('get-user-info'),
  logout: () => ipcRenderer.invoke('logout'),

  // Audio processing
  processAudio: (operation, filePath, options) =>
    ipcRenderer.invoke('process-audio', operation, filePath, options),

  // Menu events. ipcRenderer.on delivers (IpcRendererEvent, ...args) and never
  // the channel name, so the callback receives the channel explicitly --
  // without it every action arrived as an event object and hit the default
  // case in the renderer.
  onMenuAction: (callback) => {
    MENU_CHANNELS.forEach((channel) => {
      ipcRenderer.on(channel, (_event, ...args) => callback(channel, ...args));
    });
  },

  // Authentication events
  onUserAuthenticated: (callback) => ipcRenderer.on('user-authenticated', callback),

  // Security events
  onSecurityAlert: (callback) => ipcRenderer.on('security-alert', callback),

  // Version info
  version: process.versions.electron,
  platform: process.platform
});
