# Chameleon Audio GUI

Government-grade audio processing interface built with React and Electron.

## 🔒 Security Classification: RESTRICTED

This application is designed for government and military use with maximum security controls.

## Features

### Core Functionality
- **Secure Authentication**: Government-grade multi-factor authentication
- **Audio Processing**: Real-time analysis, normalization, and format conversion
- **Batch Processing**: Queue-based processing for multiple files
- **Security Controls**: Role-based access control with clearance levels
- **Audit Logging**: Comprehensive activity monitoring and logging
- **System Monitoring**: Real-time system status and performance metrics

### Security Features
- **Multi-level Clearance**: UNCLASSIFIED → TOP SECRET access levels
- **Encrypted Communication**: All data transmission secured with AES-256
- **Session Management**: Secure token-based authentication with timeout
- **Audit Trail**: Complete logging of all user activities
- **Access Controls**: Permission-based feature access

### User Interface
- **Modern Design**: Material-UI components with government theme
- **Responsive Layout**: Works on desktop and tablet devices
- **Dark/Light Modes**: Government-approved color schemes
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
- **Material-UI 5**: Government-compliant design system
- **React Router**: Client-side routing
- **Recharts**: Data visualization and charts

### Desktop Integration
- **Electron 22**: Cross-platform desktop application
- **IPC Security**: Secure communication between processes
- **Context Isolation**: Maximum security with process separation
- **Auto-updater**: Secure application updates

### Backend Integration
- **Python Integration**: Seamless connection to audio processing backend
- **Authentication API**: Integration with government authentication system
- **File Processing**: Secure file handling and temporary storage
- **Audit API**: Real-time logging to government audit systems

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
- Government-approved dependencies only

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

### Government Deployment
- Code signing with government certificates
- Package verification and integrity checking
- Secure distribution through approved channels
- Installation validation and audit logging

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

**Classification**: RESTRICTED - Government Use Only
**Last Updated**: January 2025
**Document Control**: GUI-README-2025-001