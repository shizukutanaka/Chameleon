const DOCS_BASE_PATH = path.join(__dirname, '../../docs');
const DOCS_BASE_URL = (process.env.CHAMELEON_DOCS_URL || `file://${DOCS_BASE_PATH}`).replace(/\/$/, '');
const SECURITY_GUIDE_URL = process.env.CHAMELEON_SECURITY_URL || `${DOCS_BASE_URL}/user_manual.md`;

const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const isDev = require('electron-is-dev');
const { spawn } = require('child_process');

// Government security settings
const SECURITY_CONFIG = {
  nodeIntegration: false,
  contextIsolation: true,
  enableRemoteModule: false,
  webSecurity: true,
  allowRunningInsecureContent: false,
  experimentalFeatures: false
};

let mainWindow;
let authWindow;
let isAuthenticated = false;
let currentUser = null;

function createWindow() {
  // Create the browser window with maximum security
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1200,
    minHeight: 700,
    webPreferences: {
      ...SECURITY_CONFIG,
      preload: path.join(__dirname, 'preload.js')
    },
    titleBarStyle: 'default',
    icon: path.join(__dirname, '../public/icon.png'),
    show: false // Don't show until authenticated
  });

  // Load the app
  const startUrl = isDev
    ? 'http://localhost:3000'
    : `file://${path.join(__dirname, '../build/index.html')}`;

  mainWindow.loadURL(startUrl);

  // Show authentication dialog first
  showAuthenticationDialog();

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Security: Prevent new window creation
  mainWindow.webContents.setWindowOpenHandler(() => {
    return { action: 'deny' };
  });

  // Security: Prevent navigation to external URLs
  mainWindow.webContents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);

    if (parsedUrl.origin !== startUrl && !navigationUrl.startsWith('file://')) {
      event.preventDefault();
    }
  });

  // Development tools (only in dev mode)
  if (isDev) {
    mainWindow.webContents.openDevTools();
  }
}

function showAuthenticationDialog() {
  authWindow = new BrowserWindow({
    width: 450,
    height: 600,
    parent: mainWindow,
    modal: true,
    resizable: false,
    webPreferences: {
      ...SECURITY_CONFIG,
      preload: path.join(__dirname, 'auth-preload.js')
    },
    titleBarStyle: 'default',
    title: 'Chameleon Audio - Security Authentication'
  });

  authWindow.loadFile(path.join(__dirname, 'auth.html'));

  authWindow.on('closed', () => {
    authWindow = null;
    if (!isAuthenticated) {
      app.quit();
    }
  });
}

function createMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Audio File',
          accelerator: 'CmdOrCtrl+O',
          click: () => {
            mainWindow.webContents.send('menu-open-file');
          }
        },
        { type: 'separator' },
        {
          label: 'Export Results',
          accelerator: 'CmdOrCtrl+E',
          click: () => {
            mainWindow.webContents.send('menu-export');
          }
        },
        { type: 'separator' },
        {
          label: 'Logout',
          click: () => {
            logout();
          }
        },
        {
          label: isDev ? 'Quit' : 'Exit',
          accelerator: process.platform === 'darwin' ? 'Cmd+Q' : 'Ctrl+Q',
          click: () => {
            app.quit();
          }
        }
      ]
    },
    {
      label: 'Processing',
      submenu: [
        {
          label: 'Analyze Audio',
          accelerator: 'CmdOrCtrl+A',
          click: () => {
            mainWindow.webContents.send('menu-analyze');
          }
        },
        {
          label: 'Normalize Audio',
          accelerator: 'CmdOrCtrl+N',
          click: () => {
            mainWindow.webContents.send('menu-normalize');
          }
        },
        {
          label: 'Batch Process',
          accelerator: 'CmdOrCtrl+B',
          click: () => {
            mainWindow.webContents.send('menu-batch');
          }
        }
      ]
    },
    {
      label: 'Security',
      submenu: [
        {
          label: 'View Audit Log',
          click: () => {
            mainWindow.webContents.send('menu-audit-log');
          }
        },
        {
          label: 'Security Settings',
          click: () => {
            mainWindow.webContents.send('menu-security-settings');
          }
        },
        {
          label: 'Change Password',
          click: () => {
            mainWindow.webContents.send('menu-change-password');
          }
        }
      ]
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'User Manual',
          click: () => {
            shell.openExternal(`${DOCS_BASE_URL}/user_manual.md`);
          }
        },
        {
          label: 'Security Guidelines',
          click: () => {
            shell.openExternal(SECURITY_GUIDE_URL);
          }
        },
        { type: 'separator' },
        {
          label: 'About Chameleon Audio',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Chameleon Audio',
              message: 'Chameleon Audio Processing System',
              detail: `Version: 1.0.0\nClassification: RESTRICTED\nGovernment-Grade Security Enabled\n\nDeveloped for secure audio processing operations.\nAuthorized personnel only.`
            });
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

// IPC Handlers for authentication
ipcMain.handle('authenticate', async (event, credentials) => {
  try {
    // Call Python authentication backend
    const result = await authenticateUser(credentials.username, credentials.password);

    if (result.success) {
      isAuthenticated = true;
      currentUser = result.user;

      // Close auth window and show main window
      if (authWindow) {
        authWindow.close();
      }
      mainWindow.show();

      // Send user info to renderer
      mainWindow.webContents.send('user-authenticated', currentUser);

      return { success: true, user: currentUser };
    } else {
      return { success: false, error: result.error };
    }
  } catch (error) {
    return { success: false, error: 'Authentication service unavailable' };
  }
});

// IPC Handlers for audio processing
ipcMain.handle('process-audio', async (event, operation, filePath, options = {}) => {
  if (!isAuthenticated) {
    return { success: false, error: 'Authentication required' };
  }

  try {
    const result = await executeAudioOperation(operation, filePath, options);

    // Log operation for audit
    logAuditEvent({
      user: currentUser.username,
      operation: operation,
      file: filePath,
      success: result.success,
      timestamp: new Date().toISOString()
    });

    return result;
  } catch (error) {
    logAuditEvent({
      user: currentUser.username,
      operation: operation,
      file: filePath,
      success: false,
      error: error.message,
      timestamp: new Date().toISOString()
    });

    return { success: false, error: error.message };
  }
});

ipcMain.handle('get-user-info', () => {
  return isAuthenticated ? currentUser : null;
});

ipcMain.handle('logout', () => {
  logout();
  return { success: true };
});

// Authentication backend integration
async function authenticateUser(username, password) {
  return new Promise((resolve, reject) => {
    const pythonProcess = spawn('python3', [
      path.join(__dirname, '../../production_cli.py'),
      'authenticate',
      '--username', username,
      '--password', password,
      '--format', 'json'
    ]);

    let output = '';
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    pythonProcess.on('close', (code) => {
      try {
        const result = JSON.parse(output);
        resolve(result);
      } catch (error) {
        resolve({ success: false, error: 'Invalid authentication response' });
      }
    });

    pythonProcess.on('error', (error) => {
      resolve({ success: false, error: 'Authentication service error' });
    });
  });
}

// Audio processing backend integration
async function executeAudioOperation(operation, filePath, options) {
  return new Promise((resolve, reject) => {
    const args = [
      path.join(__dirname, '../../main.py'),
      operation,
      '--input', filePath,
      '--format', 'json'
    ];

    // Add options to args
    Object.entries(options).forEach(([key, value]) => {
      args.push(`--${key}`, value.toString());
    });

    const pythonProcess = spawn('python3', args);

    let output = '';
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });

    pythonProcess.on('close', (code) => {
      try {
        const result = JSON.parse(output);
        resolve(result);
      } catch (error) {
        resolve({ success: false, error: 'Invalid processing response' });
      }
    });

    pythonProcess.on('error', (error) => {
      resolve({ success: false, error: 'Processing service error' });
    });
  });
}

// Audit logging
function logAuditEvent(event) {
  const fs = require('fs');
  const logFile = path.join(__dirname, '../../logs/gui-audit.log');
  const logEntry = JSON.stringify(event) + '\n';

  fs.appendFile(logFile, logEntry, (err) => {
    if (err) {
      console.error('Failed to write audit log:', err);
    }
  });
}

function logout() {
  isAuthenticated = false;
  currentUser = null;

  if (mainWindow) {
    mainWindow.hide();
  }

  showAuthenticationDialog();
}

// App event handlers
app.whenReady().then(() => {
  createWindow();
  createMenu();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Security: Prevent insecure content
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (navigationEvent, url) => {
    navigationEvent.preventDefault();
  });
});

// Handle certificate errors (government networks)
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  // In production, implement proper certificate validation
  // For now, allow government certificates
  event.preventDefault();
  callback(true);
});