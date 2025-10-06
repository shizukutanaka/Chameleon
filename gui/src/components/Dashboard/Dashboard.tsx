import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  LinearProgress,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Tooltip,
  Alert,
} from '@mui/material';
import {
  AudioFile as AudioIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  Storage as StorageIcon,
  TrendingUp as TrendingIcon,
  CheckCircle as CheckIcon,
  Warning as WarningIcon,
  Error as ErrorIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts';

interface DashboardProps {
  user: any;
}

interface SystemMetrics {
  cpuUsage: number;
  memoryUsage: number;
  diskUsage: number;
  networkActivity: number;
  activeProcesses: number;
  queuedJobs: number;
  completedJobs: number;
  errorRate: number;
}

interface ProcessingHistory {
  timestamp: string;
  operation: string;
  duration: number;
  fileSize: number;
  success: boolean;
}

const mockProcessingData = [
  { time: '00:00', processed: 12, errors: 0 },
  { time: '04:00', processed: 18, errors: 1 },
  { time: '08:00', processed: 35, errors: 0 },
  { time: '12:00', processed: 42, errors: 2 },
  { time: '16:00', processed: 38, errors: 1 },
  { time: '20:00', processed: 28, errors: 0 },
];

const mockFileTypes = [
  { name: 'WAV', value: 65, color: '#2a5298' },
  { name: 'MP3', value: 20, color: '#4a7bc8' },
  { name: 'FLAC', value: 10, color: '#7ba7d7' },
  { name: 'Other', value: 5, color: '#b3cceb' },
];

function Dashboard({ user }: DashboardProps) {
  const [systemMetrics, setSystemMetrics] = useState<SystemMetrics>({
    cpuUsage: 0,
    memoryUsage: 0,
    diskUsage: 0,
    networkActivity: 0,
    activeProcesses: 0,
    queuedJobs: 0,
    completedJobs: 0,
    errorRate: 0,
  });

  const [recentActivity, setRecentActivity] = useState<ProcessingHistory[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    // Initialize dashboard data
    fetchSystemMetrics();
    fetchRecentActivity();

    // Set up periodic updates
    const interval = setInterval(() => {
      fetchSystemMetrics();
    }, 30000); // Update every 30 seconds

    return () => clearInterval(interval);
  }, []);

  const fetchSystemMetrics = async () => {
    setIsLoading(true);
    try {
      // Simulate API call to get system metrics
      await new Promise(resolve => setTimeout(resolve, 1000));

      // Generate mock data (in real app, this would come from backend)
      setSystemMetrics({
        cpuUsage: Math.random() * 100,
        memoryUsage: 45 + Math.random() * 30,
        diskUsage: 68 + Math.random() * 10,
        networkActivity: Math.random() * 50,
        activeProcesses: Math.floor(Math.random() * 10),
        queuedJobs: Math.floor(Math.random() * 5),
        completedJobs: 1247 + Math.floor(Math.random() * 100),
        errorRate: Math.random() * 5,
      });

      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to fetch system metrics:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRecentActivity = async () => {
    try {
      // Mock recent activity data
      const mockActivity: ProcessingHistory[] = [
        {
          timestamp: new Date(Date.now() - 300000).toISOString(),
          operation: 'Audio Analysis',
          duration: 2.3,
          fileSize: 15.2,
          success: true,
        },
        {
          timestamp: new Date(Date.now() - 600000).toISOString(),
          operation: 'Normalization',
          duration: 4.1,
          fileSize: 28.7,
          success: true,
        },
        {
          timestamp: new Date(Date.now() - 900000).toISOString(),
          operation: 'Batch Processing',
          duration: 12.5,
          fileSize: 156.3,
          success: false,
        },
        {
          timestamp: new Date(Date.now() - 1200000).toISOString(),
          operation: 'Format Conversion',
          duration: 1.8,
          fileSize: 8.4,
          success: true,
        },
      ];

      setRecentActivity(mockActivity);
    } catch (error) {
      console.error('Failed to fetch recent activity:', error);
    }
  };

  const getMetricColor = (value: number, thresholds: { warning: number; critical: number }) => {
    if (value >= thresholds.critical) return '#dc3545';
    if (value >= thresholds.warning) return '#ffc107';
    return '#198754';
  };

  const getStatusIcon = (success: boolean) => {
    return success ? (
      <CheckIcon sx={{ color: '#198754', fontSize: 20 }} />
    ) : (
      <ErrorIcon sx={{ color: '#dc3545', fontSize: 20 }} />
    );
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Typography variant="h4" sx={{ fontWeight: 700, color: '#2a5298' }}>
          System Dashboard
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <Typography variant="body2" color="text.secondary">
            Last updated: {lastUpdate.toLocaleTimeString()}
          </Typography>
          <Tooltip title="Refresh Data">
            <IconButton onClick={fetchSystemMetrics} disabled={isLoading}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </Box>
      </Box>

      {/* Security Alert */}
      <Alert
        severity="info"
        sx={{ mb: 3 }}
        icon={<SecurityIcon />}
      >
        <strong>Security Status:</strong> All systems operational. Current classification level: {user?.clearanceLevel}
      </Alert>

      {/* Metrics Cards */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <SpeedIcon sx={{ mr: 1, color: '#2a5298' }} />
                <Typography variant="h6">CPU Usage</Typography>
              </Box>
              <Typography variant="h3" sx={{ mb: 1, fontWeight: 700 }}>
                {systemMetrics.cpuUsage.toFixed(1)}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={systemMetrics.cpuUsage}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getMetricColor(systemMetrics.cpuUsage, { warning: 70, critical: 90 }),
                  },
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <StorageIcon sx={{ mr: 1, color: '#2a5298' }} />
                <Typography variant="h6">Memory</Typography>
              </Box>
              <Typography variant="h3" sx={{ mb: 1, fontWeight: 700 }}>
                {systemMetrics.memoryUsage.toFixed(1)}%
              </Typography>
              <LinearProgress
                variant="determinate"
                value={systemMetrics.memoryUsage}
                sx={{
                  height: 8,
                  borderRadius: 4,
                  '& .MuiLinearProgress-bar': {
                    backgroundColor: getMetricColor(systemMetrics.memoryUsage, { warning: 75, critical: 90 }),
                  },
                }}
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <AudioIcon sx={{ mr: 1, color: '#2a5298' }} />
                <Typography variant="h6">Active Jobs</Typography>
              </Box>
              <Typography variant="h3" sx={{ mb: 1, fontWeight: 700 }}>
                {systemMetrics.activeProcesses}
              </Typography>
              <Chip
                label={`${systemMetrics.queuedJobs} queued`}
                size="small"
                color="primary"
                variant="outlined"
              />
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                <TrendingIcon sx={{ mr: 1, color: '#2a5298' }} />
                <Typography variant="h6">Completed</Typography>
              </Box>
              <Typography variant="h3" sx={{ mb: 1, fontWeight: 700 }}>
                {systemMetrics.completedJobs.toLocaleString()}
              </Typography>
              <Typography variant="body2" color="text.secondary">
                {systemMetrics.errorRate.toFixed(1)}% error rate
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Charts */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={8}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                Processing Activity (24 Hours)
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={mockProcessingData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="time" />
                  <YAxis />
                  <RechartsTooltip />
                  <Area
                    type="monotone"
                    dataKey="processed"
                    stroke="#2a5298"
                    fill="#2a5298"
                    fillOpacity={0.1}
                    name="Processed Files"
                  />
                  <Area
                    type="monotone"
                    dataKey="errors"
                    stroke="#dc3545"
                    fill="#dc3545"
                    fillOpacity={0.1}
                    name="Errors"
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </Grid>

        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2 }}>
                File Type Distribution
              </Typography>
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={mockFileTypes}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={100}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {mockFileTypes.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <RechartsTooltip />
                </PieChart>
              </ResponsiveContainer>
              <Box sx={{ mt: 2 }}>
                {mockFileTypes.map((type) => (
                  <Box key={type.name} sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                    <Box
                      sx={{
                        width: 12,
                        height: 12,
                        backgroundColor: type.color,
                        borderRadius: '50%',
                        mr: 1,
                      }}
                    />
                    <Typography variant="body2">
                      {type.name}: {type.value}%
                    </Typography>
                  </Box>
                ))}
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Activity */}
      <Card>
        <CardContent>
          <Typography variant="h6" sx={{ mb: 2 }}>
            Recent Processing Activity
          </Typography>
          <List>
            {recentActivity.map((activity, index) => (
              <ListItem key={index} divider={index < recentActivity.length - 1}>
                <ListItemIcon>
                  {getStatusIcon(activity.success)}
                </ListItemIcon>
                <ListItemText
                  primary={
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <Typography variant="subtitle2">
                        {activity.operation}
                      </Typography>
                      <Chip
                        label={activity.success ? 'Success' : 'Failed'}
                        size="small"
                        color={activity.success ? 'success' : 'error'}
                        variant="outlined"
                      />
                    </Box>
                  }
                  secondary={
                    <Typography variant="body2" color="text.secondary">
                      {formatTimestamp(activity.timestamp)} •
                      Duration: {activity.duration}s •
                      Size: {activity.fileSize}MB
                    </Typography>
                  }
                />
              </ListItem>
            ))}
          </List>
        </CardContent>
      </Card>
    </Box>
  );
}

export default Dashboard;