const { contextBridge, ipcRenderer } = require('electron');

// Preload for the authentication dialog (auth.html): expose only what that
// window needs -- a single invoke to the 'authenticate' handler in main.js.
contextBridge.exposeInMainWorld('electronAPI', {
  authenticate: (credentials) => ipcRenderer.invoke('authenticate', credentials)
});
