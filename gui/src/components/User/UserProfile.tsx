import React from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Avatar,
  Chip,
  List,
  ListItem,
  ListItemText,
} from '@mui/material';

interface UserProfileProps {
  user: any;
}

function UserProfile({ user }: UserProfileProps) {
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        User Profile
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
                <Avatar
                  sx={{
                    width: 80,
                    height: 80,
                    bgcolor: '#2a5298',
                    fontSize: 24,
                    fontWeight: 'bold',
                    mr: 3,
                  }}
                >
                  {user?.username?.slice(0, 2).toUpperCase() || 'U'}
                </Avatar>
                <Box>
                  <Typography variant="h5" sx={{ fontWeight: 600 }}>
                    {user?.username || 'Unknown User'}
                  </Typography>
                  <Chip
                    label={user?.clearanceLevel || 'UNCLASSIFIED'}
                    color="primary"
                    sx={{ mt: 1 }}
                  />
                </Box>
              </Box>

              <List>
                <ListItem>
                  <ListItemText
                    primary="User ID"
                    secondary={user?.id || 'N/A'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Security Clearance"
                    secondary={user?.clearanceLevel || 'UNCLASSIFIED'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Last Login"
                    secondary={user?.lastLogin || 'N/A'}
                  />
                </ListItem>
                <ListItem>
                  <ListItemText
                    primary="Account Status"
                    secondary="Active"
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

export default UserProfile;