import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Switch,
  FormControlLabel,
  Button,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  Security as SecurityIcon,
  Lock as LockIcon,
  Shield as ShieldIcon,
  Key as KeyIcon,
  Visibility as VisibilityIcon,
} from '@mui/icons-material';

interface SecuritySettingsProps {
  user: any;
}

function SecuritySettings({ user }: SecuritySettingsProps) {
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        Security Settings
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                <SecurityIcon sx={{ mr: 1 }} />
                Security Status
              </Typography>

              <Alert severity="success" sx={{ mb: 2 }}>
                <strong>Security Level:</strong> Government-Grade Protection Active
              </Alert>

              <List>
                <ListItem>
                  <ListItemIcon>
                    <ShieldIcon sx={{ color: '#198754' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Encryption Status"
                    secondary="AES-256 encryption enabled for all data"
                  />
                  <Chip label="Active" color="success" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <LockIcon sx={{ color: '#198754' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Authentication"
                    secondary="Multi-factor authentication required"
                  />
                  <Chip label="Enforced" color="success" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <KeyIcon sx={{ color: '#198754' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Access Control"
                    secondary={`Clearance Level: ${user?.clearanceLevel}`}
                  />
                  <Chip
                    label="Verified"
                    color="success"
                    size="small"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <VisibilityIcon sx={{ color: '#198754' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Audit Logging"
                    secondary="All activities are monitored and logged"
                  />
                  <Chip label="Enabled" color="success" size="small" />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Security Controls
              </Typography>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={<Switch checked disabled />}
                  label="Require authentication for all operations"
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={<Switch checked disabled />}
                  label="Enable comprehensive audit logging"
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={<Switch checked disabled />}
                  label="Enforce file integrity checking"
                />
              </Box>

              <Box sx={{ mb: 2 }}>
                <FormControlLabel
                  control={<Switch checked disabled />}
                  label="Require secure deletion of temporary files"
                />
              </Box>

              <Alert severity="info" sx={{ mt: 2 }}>
                Security settings are managed by system administrators and cannot be modified by end users.
              </Alert>

              <Button
                variant="outlined"
                fullWidth
                sx={{ mt: 2 }}
                disabled
              >
                Change Password
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default SecuritySettings;