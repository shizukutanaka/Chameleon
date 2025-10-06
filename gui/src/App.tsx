import React, { useState, useEffect } from 'react';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { CssBaseline, Box, Alert, Snackbar } from '@mui/material';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import './App.css';

// Components
import Layout from './components/Layout/Layout';
import Dashboard from './components/Dashboard/Dashboard';
import AudioProcessor from './components/AudioProcessor/AudioProcessor';
import BatchProcessor from './components/BatchProcessor/BatchProcessor';
import SecuritySettings from './components/Security/SecuritySettings';
import AuditLog from './components/Security/AuditLog';
import UserProfile from './components/User/UserProfile';
import SystemStatus from './components/System/SystemStatus';

// Types
interface User {
  id: string;
  username: string;
  clearanceLevel: string;
  permissions: string[];
  lastLogin: string;
}

interface SystemAlert {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  message: string;
  timestamp: Date;
}

// Government theme
const governmentTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2a5298',
      dark: '#1e3c72',
      light: '#4a7bc8',
    },
    secondary: {
      main: '#546e7a',
      dark: '#37474f',
      light: '#78909c',
    },
    error: {
      main: '#dc3545',
    },
    warning: {
      main: '#ffc107',
    },
    success: {
      main: '#198754',
    },
    background: {
      default: '#f5f7fa',
      paper: '#ffffff',
    },
    text: {
      primary: '#212529',
      secondary: '#6c757d',
    },
  },
  typography: {
    fontFamily: '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", sans-serif',
    h1: {
      fontWeight: 700,
      fontSize: '2.5rem',
    },
    h2: {
      fontWeight: 600,
      fontSize: '2rem',
    },
    h3: {
      fontWeight: 600,
      fontSize: '1.5rem',
    },
    h4: {
      fontWeight: 600,
      fontSize: '1.25rem',
    },
    h5: {
      fontWeight: 600,
      fontSize: '1.1rem',
    },
    h6: {
      fontWeight: 600,
      fontSize: '1rem',
    },
    button: {
      fontWeight: 600,
      textTransform: 'none',
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 8,
          textTransform: 'none',
          fontWeight: 600,
        },
      },
    },
    MuiCard: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          boxShadow: '0 4px 12px rgba(0,0,0,0.1)',
        },
      },
    },
    MuiAppBar: {
      styleOverrides: {
        root: {
          background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)',
        },
      },
    },
  },
});

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [alerts, setAlerts] = useState<SystemAlert[]>([]);
  const [currentAlert, setCurrentAlert] = useState<SystemAlert | null>(null);

  useEffect(() => {
    // Initialize application
    initializeApp();

    // Setup event listeners
    setupEventListeners();

    return () => {
      // Cleanup
      cleanupEventListeners();
    };
  }, []);

  const initializeApp = async () => {
    try {
      // Check if user is already authenticated (Electron context)
      if (window.electronAPI) {
        const userInfo = await window.electronAPI.getUserInfo();
        if (userInfo) {
          setUser(userInfo);
          setIsAuthenticated(true);
          showAlert('success', 'Welcome back! Authentication verified.');
        }
      }
    } catch (error) {
      console.error('Failed to initialize app:', error);
      showAlert('error', 'Failed to initialize application. Please restart.');
    }
  };

  const setupEventListeners = () => {
    if (window.electronAPI) {
      // User authentication events
      window.electronAPI.onUserAuthenticated((event: any, userData: User) => {
        setUser(userData);
        setIsAuthenticated(true);
        showAlert('success', `Welcome ${userData.username}! Access granted.`);
      });

      // Security alerts
      window.electronAPI.onSecurityAlert((event: any, alert: any) => {
        showAlert('warning', alert.message);
      });

      // Menu actions
      window.electronAPI.onMenuAction((event: any) => {
        handleMenuAction(event);
      });
    }
  };

  const cleanupEventListeners = () => {
    // Remove any event listeners if needed
  };

  const handleMenuAction = (event: any) => {
    // Handle menu actions from Electron
    const action = event.type || event;

    switch (action) {
      case 'menu-open-file':
        // Trigger file open dialog
        break;
      case 'menu-export':
        // Trigger export dialog
        break;
      case 'menu-analyze':
        // Navigate to audio processor
        break;
      case 'menu-normalize':
        // Navigate to audio processor with normalize mode
        break;
      case 'menu-batch':
        // Navigate to batch processor
        break;
      case 'menu-audit-log':
        // Navigate to audit log
        break;
      case 'menu-security-settings':
        // Navigate to security settings
        break;
      case 'menu-change-password':
        // Show change password dialog
        break;
      default:
        console.log('Unhandled menu action:', action);
    }
  };

  const showAlert = (type: 'success' | 'warning' | 'error' | 'info', message: string) => {
    const alert: SystemAlert = {
      id: Date.now().toString(),
      type,
      message,
      timestamp: new Date(),
    };

    setAlerts(prev => [alert, ...prev.slice(0, 9)]); // Keep last 10 alerts
    setCurrentAlert(alert);
  };

  const handleCloseAlert = () => {
    setCurrentAlert(null);
  };

  const handleLogout = async () => {
    try {
      if (window.electronAPI) {
        await window.electronAPI.logout();
      }
      setUser(null);
      setIsAuthenticated(false);
      showAlert('info', 'Successfully logged out.');
    } catch (error) {
      showAlert('error', 'Logout failed. Please try again.');
    }
  };

  if (!isAuthenticated) {
    return (
      <ThemeProvider theme={governmentTheme}>
        <CssBaseline />
        <Box
          sx={{
            height: '100vh',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)',
            color: 'white',
            textAlign: 'center',
          }}
        >
          <Box>
            <Box
              sx={{
                width: 120,
                height: 120,
                background: 'rgba(255,255,255,0.1)',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: 36,
                fontWeight: 'bold',
                margin: '0 auto 30px',
                border: '3px solid rgba(255,255,255,0.3)',
              }}
            >
              CA
            </Box>
            <h1>Authentication Required</h1>
            <p>Please authenticate through the secure login window.</p>
          </Box>
        </Box>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={governmentTheme}>
      <CssBaseline />
      <Router>
        <Layout user={user} onLogout={handleLogout} alerts={alerts}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard user={user} />} />
            <Route path="/processor" element={<AudioProcessor user={user} />} />
            <Route path="/batch" element={<BatchProcessor user={user} />} />
            <Route path="/security" element={<SecuritySettings user={user} />} />
            <Route path="/audit" element={<AuditLog user={user} />} />
            <Route path="/profile" element={<UserProfile user={user} />} />
            <Route path="/system" element={<SystemStatus user={user} />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Layout>

        {/* Global alert snackbar */}
        <Snackbar
          open={!!currentAlert}
          autoHideDuration={6000}
          onClose={handleCloseAlert}
          anchorOrigin={{ vertical: 'top', horizontal: 'right' }}
        >
          {currentAlert && (
            <Alert
              onClose={handleCloseAlert}
              severity={currentAlert.type}
              variant="filled"
              sx={{ width: '100%' }}
            >
              {currentAlert.message}
            </Alert>
          )}
        </Snackbar>
      </Router>
    </ThemeProvider>
  );
}

export default App;