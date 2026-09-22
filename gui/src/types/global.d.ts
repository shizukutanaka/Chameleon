// Global type declarations for Chameleon Audio GUI

declare global {
  interface Window {
    electronAPI?: {
      // Authentication
      authenticate: (credentials: {
        username: string;
        password: string;
        clearanceLevel: string;
      }) => Promise<{
        success: boolean;
        user?: any;
        error?: string;
      }>;
      getUserInfo: () => Promise<any>;
      logout: () => Promise<{ success: boolean }>;

      // Audio processing -- `result` carries the CLI's own JSON payload
      processAudio: (
        operation: string,
        filePath: string,
        options: any
      ) => Promise<{
        success: boolean;
        result?: any;
        error?: string;
      }>;

      // Event handlers
      onMenuAction: (callback: (channel: string, ...args: any[]) => void) => void;
      onUserAuthenticated: (callback: (event: any, user: any) => void) => void;
      onSecurityAlert: (callback: (event: any, alert: any) => void) => void;

      version: string;
      platform: string;
    };
  }
}

export interface User {
  id: string;
  username: string;
  clearanceLevel: 'UNCLASSIFIED' | 'CONFIDENTIAL' | 'SECRET' | 'TOP_SECRET';
  permissions: string[];
  lastLogin: string;
}

export interface AudioFile {
  file: File;
  name: string;
  size: number;
  duration?: number;
  sampleRate?: number;
  channels?: number;
  bitDepth?: number;
}

export interface ProcessingResult {
  success: boolean;
  simulated?: boolean;
  duration?: number;
  peakLevel?: number;
  rmsLevel?: number;
  outputPath?: string;
  error?: string;
}

export interface SystemAlert {
  id: string;
  type: 'success' | 'warning' | 'error' | 'info';
  message: string;
  timestamp: Date;
}

export interface AuditEntry {
  id: string;
  timestamp: string;
  user: string;
  operation: string;
  resource: string;
  result: 'success' | 'error' | 'warning' | 'info';
  details: string;
  ipAddress: string;
}

export {};