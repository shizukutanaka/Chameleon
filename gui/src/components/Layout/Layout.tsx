import React, { useState } from 'react';
import {
  AppBar,
  Toolbar,
  Typography,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Box,
  IconButton,
  Avatar,
  Menu,
  MenuItem,
  Chip,
  Divider,
  Badge,
  Tooltip,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  AudioFile as AudioIcon,
  Batch as BatchIcon,
  Security as SecurityIcon,
  Assignment as AuditIcon,
  Person as ProfileIcon,
  Monitor as SystemIcon,
  Logout as LogoutIcon,
  Settings as SettingsIcon,
  Notifications as NotificationsIcon,
  Lock as LockIcon,
} from '@mui/icons-material';
import { useNavigate, useLocation } from 'react-router-dom';

interface LayoutProps {
  user: any;
  onLogout: () => void;
  alerts: any[];
  children: React.ReactNode;
}

const drawerWidth = 280;

const menuItems = [
  { path: '/dashboard', label: 'Dashboard', icon: DashboardIcon, clearance: 1 },
  { path: '/processor', label: 'Audio Processor', icon: AudioIcon, clearance: 1 },
  { path: '/batch', label: 'Batch Processing', icon: BatchIcon, clearance: 2 },
  { path: '/security', label: 'Security Settings', icon: SecurityIcon, clearance: 3 },
  { path: '/audit', label: 'Audit Log', icon: AuditIcon, clearance: 3 },
  { path: '/system', label: 'System Status', icon: SystemIcon, clearance: 4 },
  { path: '/profile', label: 'User Profile', icon: ProfileIcon, clearance: 1 },
];

const clearanceLevels: { [key: string]: number } = {
  'UNCLASSIFIED': 1,
  'CONFIDENTIAL': 2,
  'SECRET': 3,
  'TOP_SECRET': 4,
};

const clearanceColors: { [key: string]: string } = {
  'UNCLASSIFIED': '#28a745',
  'CONFIDENTIAL': '#ffc107',
  'SECRET': '#fd7e14',
  'TOP_SECRET': '#dc3545',
};

function Layout({ user, onLogout, alerts, children }: LayoutProps) {
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [userMenuAnchor, setUserMenuAnchor] = useState<null | HTMLElement>(null);
  const navigate = useNavigate();
  const location = useLocation();

  const userClearanceLevel = clearanceLevels[user?.clearanceLevel] || 1;

  const handleDrawerToggle = () => {
    setDrawerOpen(!drawerOpen);
  };

  const handleUserMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchor(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchor(null);
  };

  const handleNavigation = (path: string) => {
    navigate(path);
  };

  const getInitials = (username: string) => {
    return username.slice(0, 2).toUpperCase();
  };

  const drawer = (
    <Box sx={{ height: '100%', background: 'linear-gradient(180deg, #2a5298 0%, #1e3c72 100%)' }}>
      {/* Logo Section */}
      <Box
        sx={{
          p: 3,
          textAlign: 'center',
          borderBottom: '1px solid rgba(255,255,255,0.1)',
        }}
      >
        <Box
          sx={{
            width: 60,
            height: 60,
            background: 'rgba(255,255,255,0.1)',
            borderRadius: '50%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            fontSize: 24,
            fontWeight: 'bold',
            color: 'white',
            border: '2px solid rgba(255,255,255,0.2)',
          }}
        >
          CA
        </Box>
        <Typography variant="h6" sx={{ color: 'white', fontWeight: 700 }}>
          Chameleon Audio
        </Typography>
        <Typography variant="caption" sx={{ color: 'rgba(255,255,255,0.7)' }}>
          Government-Grade Processing
        </Typography>
      </Box>

      {/* User Info Section */}
      <Box sx={{ p: 2, borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Avatar
            sx={{
              bgcolor: 'rgba(255,255,255,0.2)',
              color: 'white',
              fontWeight: 'bold',
            }}
          >
            {getInitials(user?.username || 'U')}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography
              variant="subtitle1"
              sx={{ color: 'white', fontWeight: 600, fontSize: '0.9rem' }}
              noWrap
            >
              {user?.username}
            </Typography>
            <Chip
              label={user?.clearanceLevel}
              size="small"
              sx={{
                bgcolor: clearanceColors[user?.clearanceLevel] || '#6c757d',
                color: 'white',
                fontSize: '0.7rem',
                height: 20,
                fontWeight: 600,
              }}
            />
          </Box>
        </Box>
      </Box>

      {/* Navigation Menu */}
      <List sx={{ p: 0, flex: 1 }}>
        {menuItems
          .filter(item => item.clearance <= userClearanceLevel)
          .map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;

            return (
              <ListItem
                key={item.path}
                onClick={() => handleNavigation(item.path)}
                sx={{
                  py: 1.5,
                  px: 2,
                  mx: 1,
                  my: 0.5,
                  borderRadius: 2,
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  bgcolor: isActive ? 'rgba(255,255,255,0.1)' : 'transparent',
                  '&:hover': {
                    bgcolor: 'rgba(255,255,255,0.05)',
                  },
                }}
              >
                <ListItemIcon sx={{ minWidth: 40 }}>
                  <Icon sx={{ color: 'white', fontSize: 20 }} />
                </ListItemIcon>
                <ListItemText
                  primary={item.label}
                  sx={{
                    '& .MuiListItemText-primary': {
                      color: 'white',
                      fontSize: '0.9rem',
                      fontWeight: isActive ? 600 : 400,
                    },
                  }}
                />
              </ListItem>
            );
          })}
      </List>

      {/* Classification Banner */}
      <Box
        sx={{
          p: 2,
          background: '#dc3545',
          color: 'white',
          textAlign: 'center',
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 1 }}>
          <LockIcon sx={{ fontSize: 16 }} />
          <Typography variant="caption" sx={{ fontWeight: 700, letterSpacing: 1 }}>
            RESTRICTED
          </Typography>
        </Box>
        <Typography variant="caption" sx={{ fontSize: '0.7rem', opacity: 0.9 }}>
          Authorized Personnel Only
        </Typography>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* App Bar */}
      <AppBar
        position="fixed"
        sx={{
          width: { sm: `calc(100% - ${drawerOpen ? drawerWidth : 0}px)` },
          ml: { sm: `${drawerOpen ? drawerWidth : 0}px` },
          transition: 'width 0.2s, margin 0.2s',
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2 }}
          >
            <MenuIcon />
          </IconButton>

          <Typography variant="h6" component="div" sx={{ flexGrow: 1, fontWeight: 600 }}>
            {menuItems.find(item => item.path === location.pathname)?.label || 'Chameleon Audio'}
          </Typography>

          {/* Alerts */}
          <Tooltip title="System Alerts">
            <IconButton color="inherit" sx={{ mr: 1 }}>
              <Badge badgeContent={alerts.length} color="error">
                <NotificationsIcon />
              </Badge>
            </IconButton>
          </Tooltip>

          {/* User Menu */}
          <IconButton
            onClick={handleUserMenuOpen}
            color="inherit"
            sx={{ ml: 1 }}
          >
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: 'rgba(255,255,255,0.2)',
                fontSize: '0.8rem',
                fontWeight: 'bold',
              }}
            >
              {getInitials(user?.username || 'U')}
            </Avatar>
          </IconButton>

          <Menu
            anchorEl={userMenuAnchor}
            open={Boolean(userMenuAnchor)}
            onClose={handleUserMenuClose}
            PaperProps={{
              sx: { minWidth: 200 },
            }}
          >
            <MenuItem onClick={() => { handleNavigation('/profile'); handleUserMenuClose(); }}>
              <ProfileIcon sx={{ mr: 2 }} />
              Profile
            </MenuItem>
            <MenuItem onClick={() => { handleNavigation('/security'); handleUserMenuClose(); }}>
              <SettingsIcon sx={{ mr: 2 }} />
              Settings
            </MenuItem>
            <Divider />
            <MenuItem onClick={() => { onLogout(); handleUserMenuClose(); }}>
              <LogoutIcon sx={{ mr: 2 }} />
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>

      {/* Drawer */}
      <Drawer
        variant="persistent"
        sx={{
          width: drawerOpen ? drawerWidth : 0,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
            border: 'none',
          },
        }}
        open={drawerOpen}
      >
        {drawer}
      </Drawer>

      {/* Main Content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          transition: 'margin 0.2s',
          ml: drawerOpen ? 0 : `-${drawerWidth}px`,
          mt: 8, // Account for AppBar height
        }}
      >
        {children}
      </Box>
    </Box>
  );
}

export default Layout;