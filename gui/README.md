# Chameleon Audio GUI

A React + Electron desktop interface for the Chameleon audio toolkit.

> **Status: experimental / work in progress.** This is UI scaffolding. The
> components render, but the Electron backend integration with the Python CLI
> is not yet wired up, and the "security/clearance" concepts below are planned
> UI ideas, not implemented controls. Do not rely on them for access control.

## Features (planned)

### Core Functionality
- **Audio Processing**: analysis, normalization, and format conversion
- **Batch Processing**: queue-based processing for multiple files
- **Audit Logging**: activity logging view
- **System Monitoring**: system status and performance metrics

### User Interface
- **Modern Design**: Material-UI components
- **Responsive Layout**: Works on desktop and tablet devices
- **Dark/Light Modes**: Light and dark color schemes
- **Accessibility**: WCAG 2.1 AA compliant interface
- **Real-time Updates**: Live status updates and progress indicators

## Quick Start

### Prerequisites
```bash
Node.js 18+
npm or yarn
Python 3.11+ (for backend integration)
```

### Installation
```bash
cd gui
npm install
```

### Development
```bash
# Start React development server
npm run dev

# Start Electron in development mode
npm run electron-dev
```

### Production Build
```bash
# Build React app
npm run build

# Build Electron app
npm run electron-pack

# Create distribution packages
npm run dist
```

## Architecture

### Frontend Stack
- **React 18**: Modern UI framework with hooks
- **TypeScript**: Type-safe development
- **Material-UI 5**: component library
- **React Router**: Client-side routing
- **Recharts**: Data visualization and charts

### Desktop Integration
- **Electron 22**: Cross-platform desktop application
- **IPC Security**: Secure communication between processes
- **Context Isolation**: Maximum security with process separation
- **Auto-updater**: Secure application updates

### Backend Integration (planned, not yet wired up)
- **Python Integration**: connection to the audio processing backend
- **Authentication API**: integration with an external authentication service
- **File Processing**: file handling and temporary storage
- **Audit API**: logging of processing activity

## Security Architecture

### Authentication Flow
1. **Initial Authentication**: Secure login window with clearance selection
2. **Token Generation**: Cryptographically secure session tokens
3. **Permission Validation**: Real-time permission checking
4. **Session Management**: Automatic timeout and renewal
5. **Logout Cleanup**: Secure session termination

### Data Protection
- **Encryption at Rest**: All temporary files encrypted with AES-256
- **Secure Transmission**: TLS 1.3 for all network communication
- **Memory Protection**: Secure memory allocation and cleanup
- **File Integrity**: SHA-256 verification for all processed files

### Access Control Matrix
| Clearance Level | Dashboard | Processor | Batch | Security | Audit | System |
|----------------|-----------|-----------|-------|----------|-------|--------|
| UNCLASSIFIED   | ✅        | ✅        | ❌    | ❌       | ❌    | ❌     |
| CONFIDENTIAL   | ✅        | ✅        | ✅    | ❌       | ❌    | ❌     |
| SECRET         | ✅        | ✅        | ✅    | ✅       | ✅    | ❌     |
| TOP_SECRET     | ✅        | ✅        | ✅    | ✅       | ✅    | ✅     |

## Components Overview

### Core Components
- **Layout**: Main application shell with navigation
- **Dashboard**: System overview and metrics
- **AudioProcessor**: Single file processing interface
- **BatchProcessor**: Multi-file processing queue
- **SecuritySettings**: Security configuration panel
- **AuditLog**: Activity monitoring and logging
- **UserProfile**: User information and preferences
- **SystemStatus**: System health and performance

### Security Components
- **AuthenticationDialog**: Secure login interface
- **PermissionGuard**: Route-level access control
- **SecurityContext**: Application-wide security state
- **AuditLogger**: Comprehensive activity tracking

### Utility Components
- **FileDropzone**: Secure file upload interface
- **ProgressIndicator**: Real-time processing status
- **AlertSystem**: User notification system
- **ChartVisualization**: Data visualization components

## Development Guidelines

### Security Requirements
- All user inputs must be validated and sanitized
- File operations require explicit permission checking
- Network requests must use secure protocols
- Sensitive data must be encrypted in memory
- Audit logging required for all user actions

### Code Standards
- TypeScript for all new code
- ESLint/Prettier for code formatting
- Component-based architecture
- Comprehensive error handling
- Vetted dependencies only

### Testing Requirements
- Unit tests for all components
- Integration tests for security flows
- End-to-end tests for critical paths
- Security penetration testing
- Accessibility compliance testing

## Deployment

### Development Environment
```bash
npm run electron-dev
```

### Production Environment
```bash
npm run build
npm run electron-pack
```

### Packaged Distribution
- Code signing with a release certificate
- Package verification and integrity checking
- Installation validation and logging

## Support

### Documentation
- User Manual: `/docs/user-manual.pdf`
- Security Guide: `/docs/security-guide.pdf`
- API Documentation: `/docs/api-reference.pdf`

### Contact
- **Security Team**: `<organization-security@domain>`
- **Technical Support**: `<organization-support@domain>`
- **Emergency Contact**: `<organization-emergency-number>`

---

**Status**: Experimental UI scaffolding (backend integration in progress)
**Document Control**: GUI-README-2025-001