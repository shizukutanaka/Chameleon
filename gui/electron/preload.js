const { contextBridge, ipcRenderer } = require('electron');

// Government-grade secure context bridge
contextBridge.exposeInMainWorld('electronAPI', {
  // Authentication
  authenticate: (credentials) => ipcRenderer.invoke('authenticate', credentials),
  getUserInfo: () => ipcRenderer.invoke('get-user-info'),
  logout: () => ipcRenderer.invoke('logout'),

  // Audio processing
  processAudio: (operation, filePath, options) =>
    ipcRenderer.invoke('process-audio', operation, filePath, options),

  // File operations
  openFileDialog: () => ipcRenderer.invoke('open-file-dialog'),
  saveFileDialog: (defaultPath) => ipcRenderer.invoke('save-file-dialog', defaultPath),

  // Menu events
  onMenuAction: (callback) => {
    const events = [
      'menu-open-file',
      'menu-export',
      'menu-analyze',
      'menu-normalize',
      'menu-batch',
      'menu-audit-log',
      'menu-security-settings',
      'menu-change-password'
    ];

    events.forEach(event => {
      ipcRenderer.on(event, callback);
    });
  },

  // Authentication events
  onUserAuthenticated: (callback) => ipcRenderer.on('user-authenticated', callback),

  // Security events
  onSecurityAlert: (callback) => ipcRenderer.on('security-alert', callback),

  // System info
  getSystemInfo: () => ipcRenderer.invoke('get-system-info'),

  // Version info
  version: process.versions.electron,
  platform: process.platform
});