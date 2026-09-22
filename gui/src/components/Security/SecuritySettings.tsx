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

      {/* This page is a design preview: none of the controls below are wired
          to enforcement, so present them as planned behaviour, not active
          protection. */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Design preview:</strong> these settings are concept UI only --
        nothing on this page is enforced yet (see gui/README.md).
      </Alert>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                <SecurityIcon sx={{ mr: 1 }} />
                Security Status
              </Typography>

              <List>
                <ListItem>
                  <ListItemIcon>
                    <ShieldIcon sx={{ color: '#6c757d' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Encryption"
                    secondary="At-rest file encryption -- not implemented"
                  />
                  <Chip label="Planned" color="default" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <LockIcon sx={{ color: '#6c757d' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Authentication"
                    secondary="Auth backend integration -- not implemented"
                  />
                  <Chip label="Planned" color="default" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <KeyIcon sx={{ color: '#6c757d' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Access Control"
                    secondary={`Clearance labels are UI display only (current: ${user?.clearanceLevel})`}
                  />
                  <Chip label="Display only" color="default" size="small" />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <VisibilityIcon sx={{ color: '#6c757d' }} />
                  </ListItemIcon>
                  <ListItemText
                    primary="Audit Logging"
                    secondary="GUI operations log to logs/gui-audit.log when run under Electron"
                  />
                  <Chip label="Partial" color="default" size="small" />
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
                These toggles are illustrative; no enforcement layer reads them.
              </Alert>

              <Button
                variant="outlined"
                fullWidth
                sx={{ mt: 2 }}
                disabled
              >
                Change Password (not implemented)
              </Button>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default SecuritySettings;