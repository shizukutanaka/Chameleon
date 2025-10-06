import React, { useState } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  IconButton,
  Chip,
  LinearProgress,
  Alert,
} from '@mui/material';
import {
  FolderOpen as FolderIcon,
  PlayArrow as PlayIcon,
  Delete as DeleteIcon,
  CheckCircle as CheckIcon,
  Error as ErrorIcon,
  Pending as PendingIcon,
} from '@mui/icons-material';

interface BatchProcessorProps {
  user: any;
}

interface BatchFile {
  id: string;
  name: string;
  size: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress: number;
  error?: string;
}

function BatchProcessor({ user }: BatchProcessorProps) {
  const [files, setFiles] = useState<BatchFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);

  const addFiles = () => {
    // Mock adding files
    const newFiles: BatchFile[] = [
      { id: '1', name: 'audio1.wav', size: 15000000, status: 'pending', progress: 0 },
      { id: '2', name: 'audio2.wav', size: 22000000, status: 'pending', progress: 0 },
      { id: '3', name: 'audio3.wav', size: 18000000, status: 'pending', progress: 0 },
    ];
    setFiles(newFiles);
  };

  const removeFile = (id: string) => {
    setFiles(files.filter(f => f.id !== id));
  };

  const startBatchProcessing = async () => {
    setIsProcessing(true);

    for (let i = 0; i < files.length; i++) {
      setFiles(prev => prev.map(f =>
        f.id === files[i].id ? { ...f, status: 'processing' } : f
      ));

      // Simulate processing
      for (let progress = 0; progress <= 100; progress += 10) {
        await new Promise(resolve => setTimeout(resolve, 100));
        setFiles(prev => prev.map(f =>
          f.id === files[i].id ? { ...f, progress } : f
        ));
      }

      setFiles(prev => prev.map(f =>
        f.id === files[i].id ? { ...f, status: 'completed', progress: 100 } : f
      ));
    }

    setIsProcessing(false);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'pending': return <PendingIcon sx={{ color: '#ffc107' }} />;
      case 'processing': return <PendingIcon sx={{ color: '#2a5298' }} />;
      case 'completed': return <CheckIcon sx={{ color: '#198754' }} />;
      case 'error': return <ErrorIcon sx={{ color: '#dc3545' }} />;
      default: return <PendingIcon />;
    }
  };

  const formatFileSize = (bytes: number) => {
    return (bytes / 1024 / 1024).toFixed(1) + ' MB';
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        Batch Processor
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                <Typography variant="h6">Batch Processing Queue</Typography>
                <Box sx={{ display: 'flex', gap: 1 }}>
                  <Button
                    variant="outlined"
                    startIcon={<FolderIcon />}
                    onClick={addFiles}
                    disabled={isProcessing}
                  >
                    Add Files
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<PlayIcon />}
                    onClick={startBatchProcessing}
                    disabled={files.length === 0 || isProcessing}
                  >
                    Start Processing
                  </Button>
                </Box>
              </Box>

              {files.length === 0 ? (
                <Alert severity="info">
                  No files in queue. Click "Add Files" to select audio files for batch processing.
                </Alert>
              ) : (
                <List>
                  {files.map((file) => (
                    <ListItem key={file.id} sx={{ border: '1px solid #e0e0e0', mb: 1, borderRadius: 1 }}>
                      <ListItemIcon>
                        {getStatusIcon(file.status)}
                      </ListItemIcon>
                      <ListItemText
                        primary={
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <Typography variant="subtitle1">{file.name}</Typography>
                            <Chip
                              label={file.status.toUpperCase()}
                              size="small"
                              color={
                                file.status === 'completed' ? 'success' :
                                file.status === 'error' ? 'error' :
                                file.status === 'processing' ? 'primary' : 'default'
                              }
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="text.secondary">
                              Size: {formatFileSize(file.size)}
                            </Typography>
                            {file.status === 'processing' && (
                              <LinearProgress
                                variant="determinate"
                                value={file.progress}
                                sx={{ mt: 1, width: '50%' }}
                              />
                            )}
                            {file.error && (
                              <Typography variant="body2" color="error">
                                Error: {file.error}
                              </Typography>
                            )}
                          </Box>
                        }
                      />
                      <IconButton
                        onClick={() => removeFile(file.id)}
                        disabled={isProcessing}
                      >
                        <DeleteIcon />
                      </IconButton>
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}

export default BatchProcessor;