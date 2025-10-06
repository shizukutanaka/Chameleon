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

      // Audio processing
      processAudio: (
        operation: string,
        filePath: string,
        options: any
      ) => Promise<{
        success: boolean;
        duration?: number;
        peakLevel?: number;
        rmsLevel?: number;
        outputPath?: string;
        error?: string;
      }>;

      // File operations
      openFileDialog: () => Promise<string[]>;
      saveFileDialog: (defaultPath?: string) => Promise<string>;

      // Event handlers
      onMenuAction: (callback: (event: any) => void) => void;
      onUserAuthenticated: (callback: (event: any, user: any) => void) => void;
      onSecurityAlert: (callback: (event: any, alert: any) => void) => void;

      // System info
      getSystemInfo: () => Promise<any>;
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
  duration: number;
  peakLevel: number;
  rmsLevel: number;
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