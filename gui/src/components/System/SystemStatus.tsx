import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Alert,
} from '@mui/material';
import {
  Computer as ComputerIcon,
  Memory as MemoryIcon,
  Storage as StorageIcon,
  NetworkCheck as NetworkIcon,
} from '@mui/icons-material';

interface SystemStatusProps {
  user: any;
}

function SystemStatus({ user }: SystemStatusProps) {
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        System Status
      </Typography>

      {/* Every value below was hardcoded placeholder text -- present the
          page as a design preview instead of fake live readings. */}
      <Alert severity="info" sx={{ mb: 3 }}>
        <strong>Design preview:</strong> no system metrics are collected yet --
        values below are placeholders (see gui/README.md).
      </Alert>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                System Resources
              </Typography>

              <List>
                <ListItem>
                  <ListItemIcon>
                    <ComputerIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="CPU Usage"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MemoryIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Memory Usage"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <StorageIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Disk Usage"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <NetworkIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Network Status"
                    secondary="not collected"
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                System Information
              </Typography>

              <List>
                <ListItem>
                  <ListItemText
                    primary="Operating System"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Application Version"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Python Version"
                    secondary="not collected"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Security Status"
                    secondary="not evaluated"
                  />
                </ListItem>
              </List>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default SystemStatus;