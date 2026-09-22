import React, { useState, useRef, useCallback } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Box,
  Button,
  LinearProgress,
  Alert,
  Chip,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Slider,
  Paper,
  Divider,
} from '@mui/material';
import {
  Upload as UploadIcon,
  PlayArrow as PlayIcon,
  Stop as StopIcon,
  AudioFile as AudioIcon,
  Tune as TuneIcon,
  Analytics as AnalyticsIcon,
} from '@mui/icons-material';
import { useDropzone } from 'react-dropzone';

interface AudioProcessorProps {
  user: any;
}

interface AudioFile {
  file: File;
  name: string;
  size: number;
  duration?: number;
  sampleRate?: number;
  channels?: number;
  bitDepth?: number;
}

interface ProcessingResult {
  success: boolean;
  // Real results come from the CLI; simulated previews set `simulated`.
  simulated?: boolean;
  duration?: number;
  peakLevel?: number;
  rmsLevel?: number;
  outputPath?: string;
  error?: string;
}

interface ProcessingOptions {
  operation: string;
  targetPeak: number;
  bitDepth: number;
  // 0 = keep the source rate (no --convert-sample-rate flag)
  sampleRate: number;
}

function AudioProcessor({ user }: AudioProcessorProps) {
  const [audioFile, setAudioFile] = useState<AudioFile | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<ProcessingResult | null>(null);
  const [options, setOptions] = useState<ProcessingOptions>({
    operation: 'analyze',
    targetPeak: 0.95,
    bitDepth: 16,
    sampleRate: 0,
  });

  const audioRef = useRef<HTMLAudioElement>(null);

  const onDrop = useCallback((acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (file) {
      const audioFileData: AudioFile = {
        file,
        name: file.name,
        size: file.size,
      };
      setAudioFile(audioFileData);
      setResult(null);

      // Create object URL for audio preview
      if (audioRef.current) {
        audioRef.current.src = URL.createObjectURL(file);
      }
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    // The backend reads WAV/WAVE only -- don't accept formats it would reject
    accept: {
      'audio/wav': ['.wav', '.wave'],
    },
    maxFiles: 1,
  });

  const handleProcessAudio = async () => {
    if (!audioFile) return;

    setIsProcessing(true);
    setProgress(0);

    try {
      // Simulate processing progress
      const progressInterval = setInterval(() => {
        setProgress(prev => {
          if (prev >= 90) {
            clearInterval(progressInterval);
            return 90;
          }
          return prev + 10;
        });
      }, 500);

      // Call Electron API for audio processing
      if (window.electronAPI) {
        const result = await window.electronAPI.processAudio(
          options.operation,
          (audioFile.file as any).path || audioFile.name,
          options
        );

        clearInterval(progressInterval);
        setProgress(100);

        if (result.success) {
          // The main process returns { success, result } where `result` is
          // the CLI's own payload -- map it onto the display fields.
          const payload = result.result;
          const mapped: ProcessingResult = { success: true };
          if (options.operation === 'analyze' && Array.isArray(payload) && payload[0]) {
            const meta = payload[0].metadata || {};
            mapped.duration = payload[0].time;
            mapped.peakLevel = meta.peak_level;
            mapped.rmsLevel = meta.rms_level;
          } else if (payload && payload.result) {
            mapped.duration = payload.result.time;
            mapped.outputPath = payload.result.output;
          }
          setResult(mapped);
        } else {
          throw new Error(result.error || 'Processing failed');
        }
      } else {
        // Browser preview: no backend exists, so the preview is explicitly
        // labelled simulated rather than presented as a real result.
        await new Promise(resolve => setTimeout(resolve, 1500));
        clearInterval(progressInterval);
        setProgress(100);

        setResult({
          success: true,
          simulated: true,
          duration: 0,
          peakLevel: 0,
          rmsLevel: 0,
          outputPath: `processed_${audioFile.name}`,
        });
      }
    } catch (error) {
      setResult({
        success: false,
        duration: 0,
        peakLevel: 0,
        rmsLevel: 0,
        error: error instanceof Error ? error.message : 'Unknown error',
      });
    } finally {
      setIsProcessing(false);
      setTimeout(() => setProgress(0), 2000);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <Box>
      {/* Header */}
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        Audio Processor
      </Typography>

      <Grid container spacing={3}>
        {/* File Upload Section */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                <UploadIcon sx={{ mr: 1 }} />
                Audio File Input
              </Typography>

              {/* Dropzone */}
              <Paper
                {...getRootProps()}
                sx={{
                  p: 4,
                  textAlign: 'center',
                  border: '2px dashed',
                  borderColor: isDragActive ? 'primary.main' : 'grey.300',
                  backgroundColor: isDragActive ? 'primary.50' : 'grey.50',
                  cursor: 'pointer',
                  transition: 'all 0.2s',
                  mb: 2,
                }}
              >
                <input {...getInputProps()} />
                <AudioIcon sx={{ fontSize: 48, color: 'grey.400', mb: 2 }} />
                {isDragActive ? (
                  <Typography>Drop the audio file here...</Typography>
                ) : (
                  <Box>
                    <Typography variant="h6" sx={{ mb: 1 }}>
                      Drop audio file here or click to browse
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                      Supported formats: WAV, WAVE
                    </Typography>
                  </Box>
                )}
              </Paper>

              {/* File Info */}
              {audioFile && (
                <Box>
                  <Alert severity="info" sx={{ mb: 2 }}>
                    <strong>File loaded:</strong> {audioFile.name}
                  </Alert>
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mb: 2 }}>
                    <Chip label={`Size: ${formatFileSize(audioFile.size)}`} size="small" />
                    {audioFile.duration && (
                      <Chip label={`Duration: ${formatDuration(audioFile.duration)}`} size="small" />
                    )}
                    {audioFile.sampleRate && (
                      <Chip label={`${audioFile.sampleRate} Hz`} size="small" />
                    )}
                    {audioFile.channels && (
                      <Chip label={`${audioFile.channels} ch`} size="small" />
                    )}
                  </Box>

                  {/* Audio Preview */}
                  <audio
                    ref={audioRef}
                    controls
                    style={{ width: '100%', marginBottom: 16 }}
                  />
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Processing Options */}
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                <TuneIcon sx={{ mr: 1 }} />
                Processing Options
              </Typography>

              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <FormControl fullWidth>
                    <InputLabel>Operation</InputLabel>
                    <Select
                      value={options.operation}
                      label="Operation"
                      onChange={(e) => setOptions({ ...options, operation: e.target.value })}
                    >
                      {/* Only operations the CLI actually has (main.py). */}
                      <MenuItem value="analyze">Analyze Audio</MenuItem>
                      <MenuItem value="normalize">Normalize Audio</MenuItem>
                      <MenuItem value="convert">Format Conversion</MenuItem>
                    </Select>
                  </FormControl>
                </Grid>

                {options.operation === 'normalize' && (
                  <Grid item xs={12}>
                    <Typography gutterBottom>Target Peak Level</Typography>
                    <Slider
                      value={options.targetPeak}
                      onChange={(_, value) => setOptions({ ...options, targetPeak: value as number })}
                      min={0.1}
                      max={1.0}
                      step={0.05}
                      marks={[
                        { value: 0.5, label: '50%' },
                        { value: 0.75, label: '75%' },
                        { value: 0.95, label: '95%' },
                      ]}
                      valueLabelDisplay="auto"
                      valueLabelFormat={(value) => `${(value * 100).toFixed(0)}%`}
                    />
                  </Grid>
                )}

                {options.operation === 'convert' && (
                  <>
                    {/* Real --convert-bit-depth flag (16/24/32) */}
                    <Grid item xs={12}>
                      <FormControl fullWidth>
                        <InputLabel>Bit Depth</InputLabel>
                        <Select
                          value={options.bitDepth}
                          label="Bit Depth"
                          onChange={(e) => setOptions({ ...options, bitDepth: e.target.value as number })}
                        >
                          <MenuItem value={16}>16-bit</MenuItem>
                          <MenuItem value={24}>24-bit</MenuItem>
                          <MenuItem value={32}>32-bit float</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>

                    <Grid item xs={12}>
                      <FormControl fullWidth>
                        <InputLabel>Sample Rate</InputLabel>
                        <Select
                          value={options.sampleRate}
                          label="Sample Rate"
                          onChange={(e) => setOptions({ ...options, sampleRate: e.target.value as number })}
                        >
                          <MenuItem value={0}>Keep source rate</MenuItem>
                          <MenuItem value={44100}>44100 Hz</MenuItem>
                          <MenuItem value={48000}>48000 Hz</MenuItem>
                        </Select>
                      </FormControl>
                    </Grid>
                  </>
                )}
              </Grid>

              <Divider sx={{ my: 2 }} />

              {/* Process Button */}
              <Button
                variant="contained"
                size="large"
                fullWidth
                onClick={handleProcessAudio}
                disabled={!audioFile || isProcessing}
                startIcon={isProcessing ? <StopIcon /> : <PlayIcon />}
                sx={{ mb: 2 }}
              >
                {isProcessing ? 'Processing...' : `${options.operation.charAt(0).toUpperCase() + options.operation.slice(1)} Audio`}
              </Button>

              {/* Progress */}
              {isProcessing && (
                <Box sx={{ mb: 2 }}>
                  <LinearProgress variant="determinate" value={progress} sx={{ mb: 1 }} />
                  <Typography variant="body2" color="text.secondary" align="center">
                    {progress}% complete
                  </Typography>
                </Box>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Results Section */}
        {result && (
          <Grid item xs={12}>
            <Card>
              <CardContent>
                <Typography variant="h6" sx={{ mb: 2, display: 'flex', alignItems: 'center' }}>
                  <AnalyticsIcon sx={{ mr: 1 }} />
                  Processing Results
                </Typography>

                {result.success ? (
                  <Box>
                    {result.simulated ? (
                      <Alert severity="warning" sx={{ mb: 2 }}>
                        Simulated preview -- no backend is connected, so these
                        values are placeholders, not measurements.
                      </Alert>
                    ) : (
                      <Alert severity="success" sx={{ mb: 2 }}>
                        Processing completed successfully!
                      </Alert>
                    )}

                    <Grid container spacing={2}>
                      {result.duration != null && (
                        <Grid item xs={12} sm={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4" color="primary" sx={{ fontWeight: 700 }}>
                              {result.duration.toFixed(1)}s
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Processing Time
                            </Typography>
                          </Paper>
                        </Grid>
                      )}

                      {result.peakLevel != null && (
                        <Grid item xs={12} sm={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4" color="primary" sx={{ fontWeight: 700 }}>
                              {(result.peakLevel * 100).toFixed(1)}%
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Peak Level
                            </Typography>
                          </Paper>
                        </Grid>
                      )}

                      {result.rmsLevel != null && (
                        <Grid item xs={12} sm={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="h4" color="primary" sx={{ fontWeight: 700 }}>
                              {(result.rmsLevel * 100).toFixed(1)}%
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              RMS Level
                            </Typography>
                          </Paper>
                        </Grid>
                      )}

                      {result.outputPath && (
                        <Grid item xs={12} sm={6} md={3}>
                          <Paper sx={{ p: 2, textAlign: 'center' }}>
                            <Typography variant="body2" sx={{ fontWeight: 600, wordBreak: 'break-all' }}>
                              {result.outputPath}
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                              Output Path
                            </Typography>
                          </Paper>
                        </Grid>
                      )}
                    </Grid>
                  </Box>
                ) : (
                  <Alert severity="error">
                    <strong>Processing failed:</strong> {result.error}
                  </Alert>
                )}
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>
    </Box>
  );
}

export default AudioProcessor;