import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  LinearProgress,
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
                    secondary={
                      <Box>
                        <LinearProgress variant="determinate" value={45} sx={{ mt: 1 }} />
                        <Typography variant="body2">45%</Typography>
                      </Box>
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <MemoryIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Memory Usage"
                    secondary={
                      <Box>
                        <LinearProgress variant="determinate" value={62} sx={{ mt: 1 }} />
                        <Typography variant="body2">62%</Typography>
                      </Box>
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <StorageIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Disk Usage"
                    secondary={
                      <Box>
                        <LinearProgress variant="determinate" value={78} sx={{ mt: 1 }} />
                        <Typography variant="body2">78%</Typography>
                      </Box>
                    }
                  />
                </ListItem>
                <ListItem>
                  <ListItemIcon>
                    <NetworkIcon />
                  </ListItemIcon>
                  <ListItemText
                    primary="Network Status"
                    secondary={<Chip label="Connected" color="success" size="small" />}
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
                    secondary="Linux 6.6.87.2-microsoft-standard-WSL2"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Application Version"
                    secondary="1.0.0"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Python Version"
                    secondary="3.11.5"
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Security Status"
                    secondary={<Chip label="Secure" color="success" size="small" />}
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