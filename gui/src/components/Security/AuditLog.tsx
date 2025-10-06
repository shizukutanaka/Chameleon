import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Paper,
  TextField,
  InputAdornment,
  IconButton,
} from '@mui/material';
import {
  Search as SearchIcon,
  CheckCircle as SuccessIcon,
  Error as ErrorIcon,
  Warning as WarningIcon,
  Info as InfoIcon,
} from '@mui/icons-material';

interface AuditLogProps {
  user: any;
}

interface AuditEntry {
  id: string;
  timestamp: string;
  user: string;
  operation: string;
  resource: string;
  result: 'success' | 'error' | 'warning' | 'info';
  details: string;
  ipAddress: string;
}

const mockAuditEntries: AuditEntry[] = [
  {
    id: '1',
    timestamp: new Date(Date.now() - 300000).toISOString(),
    user: 'admin',
    operation: 'Audio Analysis',
    resource: 'test_audio.wav',
    result: 'success',
    details: 'File analyzed successfully',
    ipAddress: '192.168.1.100',
  },
  {
    id: '2',
    timestamp: new Date(Date.now() - 600000).toISOString(),
    user: 'operator1',
    operation: 'User Login',
    resource: 'System',
    result: 'success',
    details: 'User authenticated with SECRET clearance',
    ipAddress: '192.168.1.101',
  },
  {
    id: '3',
    timestamp: new Date(Date.now() - 900000).toISOString(),
    user: 'operator2',
    operation: 'Batch Processing',
    resource: 'audio_batch_001',
    result: 'error',
    details: 'Processing failed: Insufficient permissions',
    ipAddress: '192.168.1.102',
  },
  {
    id: '4',
    timestamp: new Date(Date.now() - 1200000).toISOString(),
    user: 'admin',
    operation: 'Security Settings',
    resource: 'System Configuration',
    result: 'warning',
    details: 'Security policy updated',
    ipAddress: '192.168.1.100',
  },
];

function AuditLog({ user }: AuditLogProps) {
  const [searchTerm, setSearchTerm] = useState('');
  const [entries] = useState<AuditEntry[]>(mockAuditEntries);

  const filteredEntries = entries.filter(entry =>
    entry.operation.toLowerCase().includes(searchTerm.toLowerCase()) ||
    entry.user.toLowerCase().includes(searchTerm.toLowerCase()) ||
    entry.resource.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getResultIcon = (result: string) => {
    switch (result) {
      case 'success':
        return <SuccessIcon sx={{ color: '#198754', fontSize: 20 }} />;
      case 'error':
        return <ErrorIcon sx={{ color: '#dc3545', fontSize: 20 }} />;
      case 'warning':
        return <WarningIcon sx={{ color: '#ffc107', fontSize: 20 }} />;
      case 'info':
        return <InfoIcon sx={{ color: '#0dcaf0', fontSize: 20 }} />;
      default:
        return <InfoIcon sx={{ fontSize: 20 }} />;
    }
  };

  const getResultColor = (result: string) => {
    switch (result) {
      case 'success': return 'success';
      case 'error': return 'error';
      case 'warning': return 'warning';
      case 'info': return 'info';
      default: return 'default';
    }
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleString();
  };

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#2a5298' }}>
        Audit Log
      </Typography>

      <Card>
        <CardContent>
          <Box sx={{ mb: 3 }}>
            <TextField
              fullWidth
              placeholder="Search audit entries..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon />
                  </InputAdornment>
                ),
              }}
            />
          </Box>

          <TableContainer component={Paper}>
            <Table>
              <TableHead>
                <TableRow sx={{ backgroundColor: '#f5f7fa' }}>
                  <TableCell><strong>Timestamp</strong></TableCell>
                  <TableCell><strong>User</strong></TableCell>
                  <TableCell><strong>Operation</strong></TableCell>
                  <TableCell><strong>Resource</strong></TableCell>
                  <TableCell><strong>Result</strong></TableCell>
                  <TableCell><strong>Details</strong></TableCell>
                  <TableCell><strong>IP Address</strong></TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {filteredEntries.map((entry) => (
                  <TableRow key={entry.id} hover>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {formatTimestamp(entry.timestamp)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontWeight: 600 }}>
                        {entry.user}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {entry.operation}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {entry.resource}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        {getResultIcon(entry.result)}
                        <Chip
                          label={entry.result.toUpperCase()}
                          size="small"
                          color={getResultColor(entry.result) as any}
                          variant="outlined"
                        />
                      </Box>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2">
                        {entry.details}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {entry.ipAddress}
                      </Typography>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>

          {filteredEntries.length === 0 && (
            <Box sx={{ textAlign: 'center', py: 4 }}>
              <Typography color="text.secondary">
                No audit entries found matching your search criteria.
              </Typography>
            </Box>
          )}
        </CardContent>
      </Card>
    </Box>
  );
}

export default AuditLog;