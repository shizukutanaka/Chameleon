#!/usr/bin/env python3
"""
UX Improvements Module for Chameleon Audio System
Provides progress indicators, better error messages, and user-friendly output
"""

import sys
import time
import shutil
from typing import Optional, List, Dict, Any
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ProgressConfig:
    """Configuration for progress display"""
    show_percentage: bool = True
    show_eta: bool = True
    show_speed: bool = True
    bar_width: int = 40
    update_interval: float = 0.1


class ProgressBar:
    """Terminal progress bar with ETA and speed"""

    def __init__(self, total: int, description: str = "", config: Optional[ProgressConfig] = None):
        self.total = total
        self.description = description
        self.config = config or ProgressConfig()

        self.current = 0
        self.start_time = time.time()
        self.last_update = 0

    def update(self, amount: int = 1) -> None:
        """Update progress"""
        self.current += amount
        current_time = time.time()

        if current_time - self.last_update < self.config.update_interval:
            return

        self.last_update = current_time
        self._render()

    def set_progress(self, current: int) -> None:
        """Set absolute progress"""
        self.current = current
        self._render()

    def _render(self) -> None:
        """Render progress bar"""
        if self.total == 0:
            return

        # Calculate metrics
        percentage = (self.current / self.total) * 100
        elapsed = time.time() - self.start_time
        speed = self.current / elapsed if elapsed > 0 else 0
        eta = (self.total - self.current) / speed if speed > 0 else 0

        # Build progress bar
        filled = int(self.config.bar_width * self.current / self.total)
        bar = '█' * filled + '░' * (self.config.bar_width - filled)

        # Build status line
        parts = [f"{self.description}" if self.description else "Progress"]

        if self.config.show_percentage:
            parts.append(f"{percentage:5.1f}%")

        parts.append(f"[{bar}]")
        parts.append(f"{self.current}/{self.total}")

        if self.config.show_speed and speed > 0:
            parts.append(f"{speed:.1f} items/s")

        if self.config.show_eta and eta > 0:
            parts.append(f"ETA: {self._format_time(eta)}")

        status = " ".join(parts)

        # Print with carriage return
        terminal_width = shutil.get_terminal_size((80, 20)).columns
        status = status[:terminal_width - 1]
        sys.stdout.write(f"\r{status}")
        sys.stdout.flush()

    def finish(self) -> None:
        """Complete progress bar"""
        self.current = self.total
        self._render()
        sys.stdout.write("\n")
        sys.stdout.flush()

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds as human-readable time"""
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            return f"{seconds/60:.0f}m {seconds%60:.0f}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"


class SpinnerAnimation:
    """Simple spinner for indeterminate progress"""

    FRAMES = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def __init__(self, description: str = "Processing"):
        self.description = description
        self.frame_index = 0
        self.running = False
        self.start_time = time.time()

    def spin(self) -> None:
        """Advance spinner animation"""
        if not self.running:
            self.running = True

        elapsed = time.time() - self.start_time
        frame = self.FRAMES[self.frame_index % len(self.FRAMES)]

        sys.stdout.write(f"\r{frame} {self.description} ({elapsed:.1f}s)")
        sys.stdout.flush()

        self.frame_index += 1

    def stop(self, message: str = "Done") -> None:
        """Stop spinner and show final message"""
        elapsed = time.time() - self.start_time
        sys.stdout.write(f"\r✓ {message} ({elapsed:.1f}s)\n")
        sys.stdout.flush()


class ErrorFormatter:
    """Format error messages with helpful context"""

    @staticmethod
    def format_error(
        error: Exception,
        context: Optional[Dict[str, Any]] = None,
        suggestions: Optional[List[str]] = None
    ) -> str:
        """Format error with context and suggestions"""
        lines = []

        # Error header
        lines.append(f"ERROR: {type(error).__name__}")
        lines.append(f"  {str(error)}")

        # Context
        if context:
            lines.append("\nContext:")
            for key, value in context.items():
                lines.append(f"  {key}: {value}")

        # Suggestions
        if suggestions:
            lines.append("\nSuggestions:")
            for i, suggestion in enumerate(suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        return "\n".join(lines)

    @staticmethod
    def get_file_error_suggestions(error: Exception, file_path: Path) -> List[str]:
        """Get suggestions for file-related errors"""
        suggestions = []

        if isinstance(error, FileNotFoundError):
            suggestions.append(f"Check that the file exists: {file_path}")
            suggestions.append("Verify the path is absolute, not relative")
            if file_path.parent.exists():
                suggestions.append(f"Directory exists, check filename spelling")

        elif isinstance(error, PermissionError):
            suggestions.append(f"Check file permissions: chmod 644 {file_path}")
            suggestions.append("Ensure you have read/write access to the directory")

        elif isinstance(error, IsADirectoryError):
            suggestions.append(f"Path is a directory, expected a file")
            suggestions.append("Specify a filename within the directory")

        return suggestions


class TableFormatter:
    """Format data as aligned tables"""

    @staticmethod
    def format_table(
        headers: List[str],
        rows: List[List[Any]],
        align: Optional[List[str]] = None
    ) -> str:
        """Format data as table

        Args:
            headers: Column headers
            rows: Table rows
            align: Alignment for each column ('left', 'right', 'center')
        """
        if not rows:
            return ""

        align = align or ['left'] * len(headers)

        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                widths[i] = max(widths[i], len(str(cell)))

        # Build format strings
        formats = []
        for i, (width, alignment) in enumerate(zip(widths, align)):
            if alignment == 'right':
                formats.append(f"{{:>{width}}}")
            elif alignment == 'center':
                formats.append(f"{{:^{width}}}")
            else:
                formats.append(f"{{:<{width}}}")

        # Format header
        lines = []
        header_line = " | ".join(
            fmt.format(header)
            for fmt, header in zip(formats, headers)
        )
        lines.append(header_line)
        lines.append("-" * len(header_line))

        # Format rows
        for row in rows:
            row_line = " | ".join(
                fmt.format(str(cell))
                for fmt, cell in zip(formats, row)
            )
            lines.append(row_line)

        return "\n".join(lines)


class ColorText:
    """ANSI color codes for terminal output"""

    # Colors
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'

    # Styles
    BOLD = '\033[1m'
    DIM = '\033[2m'
    UNDERLINE = '\033[4m'
    BLINK = '\033[5m'
    REVERSE = '\033[7m'
    RESET = '\033[0m'

    @classmethod
    def enabled(cls) -> bool:
        """Check if terminal supports colors"""
        return sys.stdout.isatty() and sys.platform != 'win32'

    @classmethod
    def colorize(cls, text: str, color: str, style: Optional[str] = None) -> str:
        """Apply color and style to text"""
        if not cls.enabled():
            return text

        codes = [color]
        if style:
            codes.append(style)

        return f"{''.join(codes)}{text}{cls.RESET}"

    @classmethod
    def success(cls, text: str) -> str:
        """Format success message"""
        return cls.colorize(f"✓ {text}", cls.GREEN, cls.BOLD)

    @classmethod
    def error(cls, text: str) -> str:
        """Format error message"""
        return cls.colorize(f"✗ {text}", cls.RED, cls.BOLD)

    @classmethod
    def warning(cls, text: str) -> str:
        """Format warning message"""
        return cls.colorize(f"⚠ {text}", cls.YELLOW)

    @classmethod
    def info(cls, text: str) -> str:
        """Format info message"""
        return cls.colorize(f"ℹ {text}", cls.BLUE)


def format_file_size(bytes: int) -> str:
    """Format bytes as human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes < 1024:
            return f"{bytes:.1f} {unit}"
        bytes /= 1024
    return f"{bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration"""
    if seconds < 1:
        return f"{seconds*1000:.0f}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"


if __name__ == "__main__":
    print("Testing UX Improvements...")

    # Test progress bar
    print("\nProgress Bar Test:")
    progress = ProgressBar(total=100, description="Processing files")
    for i in range(100):
        time.sleep(0.02)
        progress.update(1)
    progress.finish()

    # Test spinner
    print("\nSpinner Test:")
    spinner = SpinnerAnimation("Loading data")
    for i in range(20):
        time.sleep(0.1)
        spinner.spin()
    spinner.stop("Complete")

    # Test error formatter
    print("\nError Formatting Test:")
    try:
        raise FileNotFoundError("audio.wav not found")
    except Exception as e:
        suggestions = ErrorFormatter.get_file_error_suggestions(e, Path("audio.wav"))
        formatted = ErrorFormatter.format_error(
            e,
            context={"file": "audio.wav", "operation": "read"},
            suggestions=suggestions
        )
        print(formatted)

    # Test table formatter
    print("\nTable Formatting Test:")
    headers = ["File", "Size", "Duration", "Status"]
    rows = [
        ["audio1.wav", "1.2 MB", "2.5s", "OK"],
        ["audio2.wav", "850 KB", "1.8s", "OK"],
        ["audio3.wav", "3.4 MB", "7.2s", "Processing"]
    ]
    table = TableFormatter.format_table(headers, rows, align=['left', 'right', 'right', 'center'])
    print(table)

    # Test color output
    print("\nColor Output Test:")
    print(ColorText.success("Operation successful"))
    print(ColorText.error("An error occurred"))
    print(ColorText.warning("Low disk space"))
    print(ColorText.info("Processing 10 files"))

    # Test formatters
    print("\nFormat Tests:")
    print(f"File size: {format_file_size(1536000)}")
    print(f"Duration: {format_duration(125.7)}")

    print("\nUX improvements tests completed")
