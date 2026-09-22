const { app, BrowserWindow, Menu, dialog, ipcMain, shell } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn } = require('child_process');

// Packaged builds load the bundled file:// UI; run-from-source loads the
// dev server. electron-is-dev is not a declared dependency, so requiring it
// crashed this file at startup.
const isDev = process.env.ELECTRON_IS_DEV === '1' || !app.isPackaged;

const DOCS_BASE_PATH = path.join(__dirname, '../../docs');
const DOCS_BASE_URL = (process.env.CHAMELEON_DOCS_URL || `file://${DOCS_BASE_PATH}`).replace(/\/$/, '');
const USER_MANUAL_URL = `${DOCS_BASE_URL}/en/commands.md`;
const SECURITY_GUIDE_URL = process.env.CHAMELEON_SECURITY_URL || `${DOCS_BASE_URL}/en/advanced_config.md`;

// Renderer hardening defaults
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
            shell.openExternal(USER_MANUAL_URL);
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
              message: 'Chameleon Audio GUI',
              detail: `Version: ${app.getVersion()}\nExperimental Electron GUI scaffold for the Chameleon audio CLI.\nBackend integration is partially wired -- see gui/README.md.`
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
    const result = await authenticateUser(
      credentials.username,
      credentials.password,
      credentials.clearanceLevel
    );

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

// Authentication backend integration is not wired yet (gui/README.md marks
// the GUI as scaffolding): there is no auth service in this repo to call.
// In dev mode (running from source) admit a labelled preview session so the
// scaffold UI is exercisable; in packaged builds report the gap honestly
// instead of spawning a script that does not exist.
async function authenticateUser(username, password, clearanceLevel) {
  if (isDev) {
    return {
      success: true,
      user: {
        id: 'ui-preview',
        username: username || 'preview',
        clearanceLevel: clearanceLevel || 'UNCLASSIFIED',
        permissions: ['ui-preview'],
        lastLogin: new Date().toISOString()
      }
    };
  }
  return {
    success: false,
    error: 'Authentication backend is not integrated yet -- see gui/README.md'
  };
}

// Map a GUI operation onto the real CLI contract (main.py). Anything not in
// this table is an operation the product does not have -- answer honestly.
const PYTHON_BIN = process.env.CHAMELEON_PYTHON || 'python3';
const MAIN_PY = path.join(__dirname, '../../main.py');

function cliArgsFor(operation, filePath, options) {
  switch (operation) {
    case 'analyze': {
      // analyze writes a JSON report to --export <path>
      const exportPath = path.join(
        os.tmpdir(),
        `chameleon-analyze-${process.pid}-${Date.now()}.json`
      );
      return { args: [MAIN_PY, 'analyze', filePath, '--export', exportPath], exportPath };
    }
    case 'normalize': {
      const args = [MAIN_PY, 'process', '--normalize', filePath, '--json'];
      if (typeof options.targetPeak === 'number') {
        args.push('--target-peak', String(options.targetPeak));
      }
      return { args };
    }
    case 'convert': {
      const args = [MAIN_PY, 'process', '--convert', filePath, '--json'];
      if (typeof options.bitDepth === 'number') {
        args.push('--convert-bit-depth', String(options.bitDepth));
      }
      if (typeof options.sampleRate === 'number') {
        args.push('--convert-sample-rate', String(options.sampleRate));
      }
      return { args };
    }
    default:
      return null;
  }
}

// Audio processing backend integration
async function executeAudioOperation(operation, filePath, options = {}) {
  const spec = cliArgsFor(operation, filePath, options);
  if (!spec) {
    return { success: false, error: `Unsupported operation: ${operation}` };
  }

  return new Promise((resolve) => {
    const pythonProcess = spawn(PYTHON_BIN, spec.args);

    let output = '';
    let errOutput = '';
    pythonProcess.stdout.on('data', (data) => {
      output += data.toString();
    });
    pythonProcess.stderr.on('data', (data) => {
      errOutput += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (spec.exportPath) {
        try {
          const report = JSON.parse(fs.readFileSync(spec.exportPath, 'utf8'));
          resolve({ success: true, result: report });
        } catch (error) {
          resolve({ success: false, error: `analysis did not produce a report (exit ${code})` });
        } finally {
          fs.unlink(spec.exportPath, () => {});
        }
        return;
      }
      if (code !== 0) {
        resolve({
          success: false,
          error: errOutput.trim() || `chameleon exited with code ${code}`
        });
        return;
      }
      // `process --json` prints one JSON object per result line
      try {
        const lines = output.split('\n').filter((line) => line.trim().startsWith('{'));
        const last = JSON.parse(lines[lines.length - 1]);
        resolve({ success: true, result: last });
      } catch (error) {
        resolve({ success: false, error: 'unparseable CLI output' });
      }
    });

    pythonProcess.on('error', () => {
      resolve({ success: false, error: `cannot start ${PYTHON_BIN}` });
    });
  });
}

// Audit logging
function logAuditEvent(event) {
  const logFile = path.join(__dirname, '../../logs/gui-audit.log');
  const logEntry = JSON.stringify(event) + '\n';

  fs.mkdir(path.dirname(logFile), { recursive: true }, (mkdirErr) => {
    if (mkdirErr) {
      console.error('Failed to create audit log directory:', mkdirErr);
      return;
    }
    fs.appendFile(logFile, logEntry, (err) => {
      if (err) {
        console.error('Failed to write audit log:', err);
      }
    });
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

// No 'certificate-error' handler: the Electron default is to reject invalid
// certificates, which is the behaviour we want -- blanket-accepting them
// would silently strip TLS verification from any fetch the renderer makes.