#!/usr/bin/env python3
"""
Audio Recorder - Cross-platform audio recording without heavy dependencies
Uses built-in wave module and system audio capabilities
"""

import wave
import array
import threading
import queue
import time
import struct
import os
from typing import Optional, Callable, Dict, Any
from datetime import datetime

class AudioRecorder:
    """Simple audio recorder using wave module"""
    
    def __init__(self, sample_rate: int = 44100, channels: int = 1, 
                 chunk_size: int = 1024):
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.sample_width = 2  # 16-bit audio
        
        # Recording state
        self.is_recording = False
        self.recording_thread = None
        self.audio_queue = queue.Queue()
        
        # Recording data
        self.recorded_frames = []
        self.recording_start_time = None
        self.recording_duration = 0
        
        # Callbacks
        self.on_level_update = None  # Callback for level monitoring
        self.on_recording_complete = None
        
    def start_recording(self, duration: Optional[float] = None,
                       filename: Optional[str] = None) -> bool:
        """
        Start recording audio
        duration: Optional recording duration in seconds (None = manual stop)
        filename: Optional filename to save automatically
        """
        if self.is_recording:
            print("Already recording")
            return False
        
        self.is_recording = True
        self.recorded_frames = []
        self.recording_start_time = time.time()
        
        # Start recording thread
        self.recording_thread = threading.Thread(
            target=self._recording_loop,
            args=(duration, filename)
        )
        self.recording_thread.daemon = True
        self.recording_thread.start()
        
        return True
    
    def stop_recording(self) -> bytes:
        """Stop recording and return audio data"""
        if not self.is_recording:
            return b''
        
        self.is_recording = False
        
        if self.recording_thread:
            self.recording_thread.join(timeout=2.0)
        
        # Combine all recorded frames
        audio_data = b''.join(self.recorded_frames)
        
        if self.on_recording_complete:
            self.on_recording_complete(audio_data)
        
        return audio_data
    
    def _recording_loop(self, duration: Optional[float], 
                        filename: Optional[str]):
        """Main recording loop"""
        try:
            # Try to use system audio input
            audio_input = self._get_audio_input()
            
            if audio_input is None:
                # Fallback to simulated recording (for testing)
                self._simulated_recording(duration)
            else:
                # Real recording
                self._real_recording(audio_input, duration)
            
            # Auto-save if filename provided
            if filename and self.recorded_frames:
                audio_data = b''.join(self.recorded_frames)
                self.save_recording(audio_data, filename)
                print(f"Recording saved to {filename}")
                
        except Exception as e:
            print(f"Recording error: {e}")
        finally:
            self.is_recording = False
            self.recording_duration = time.time() - self.recording_start_time
    
    def _get_audio_input(self):
        """Try to get system audio input"""
        try:
            # Try pyaudio if available
            import pyaudio
            
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                frames_per_buffer=self.chunk_size
            )
            
            return ('pyaudio', p, stream)
            
        except ImportError:
            pass
        
        try:
            # Try sounddevice if available
            import sounddevice as sd
            
            stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16',
                blocksize=self.chunk_size
            )
            stream.start()
            
            return ('sounddevice', stream)
            
        except ImportError:
            pass
        
        # No audio library available
        return None
    
    def _real_recording(self, audio_input, duration: Optional[float]):
        """Record using real audio input"""
        input_type = audio_input[0]
        start_time = time.time()
        
        if input_type == 'pyaudio':
            _, p, stream = audio_input
            
            try:
                while self.is_recording:
                    if duration and (time.time() - start_time) > duration:
                        break
                    
                    # Read audio chunk
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    self.recorded_frames.append(data)
                    
                    # Calculate and report level
                    if self.on_level_update:
                        level = self._calculate_level(data)
                        self.on_level_update(level)
                    
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()
        
        elif input_type == 'sounddevice':
            stream = audio_input[1]
            
            try:
                while self.is_recording:
                    if duration and (time.time() - start_time) > duration:
                        break
                    
                    # Read audio chunk
                    data, _ = stream.read(self.chunk_size)
                    audio_bytes = data.astype('int16').tobytes()
                    self.recorded_frames.append(audio_bytes)
                    
                    # Calculate and report level
                    if self.on_level_update:
                        level = self._calculate_level(audio_bytes)
                        self.on_level_update(level)
                    
            finally:
                stream.stop()
                stream.close()
    
    def _simulated_recording(self, duration: Optional[float]):
        """Simulated recording for testing (generates silence or test tone)"""
        print("Note: Using simulated recording (no audio input available)")
        
        start_time = time.time()
        sample_count = 0
        
        while self.is_recording:
            if duration and (time.time() - start_time) > duration:
                break
            
            # Generate silent audio or test tone
            samples = []
            for i in range(self.chunk_size):
                # Generate silence (or uncomment for test tone)
                sample = 0
                # Test tone (440 Hz)
                # t = (sample_count + i) / self.sample_rate
                # sample = int(32767 * 0.3 * math.sin(2 * math.pi * 440 * t))
                
                samples.append(sample)
            
            # Convert to bytes
            audio_bytes = struct.pack('<' + 'h' * len(samples), *samples)
            self.recorded_frames.append(audio_bytes)
            
            sample_count += self.chunk_size
            
            # Simulate real-time recording
            time.sleep(self.chunk_size / self.sample_rate)
            
            # Report level
            if self.on_level_update:
                level = self._calculate_level(audio_bytes)
                self.on_level_update(level)
    
    def _calculate_level(self, audio_data: bytes) -> float:
        """Calculate audio level (0.0 to 1.0)"""
        if not audio_data:
            return 0.0
        
        # Convert bytes to samples
        samples = array.array('h', audio_data)
        
        # Calculate RMS
        if samples:
            rms = (sum(s ** 2 for s in samples) / len(samples)) ** 0.5
            # Normalize to 0.0-1.0 range
            level = min(1.0, rms / 32768.0)
            return level
        
        return 0.0
    
    def save_recording(self, audio_data: bytes, filename: str) -> bool:
        """Save recorded audio to WAV file"""
        try:
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(self.sample_width)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data)
            
            return True
            
        except Exception as e:
            print(f"Error saving recording: {e}")
            return False
    
    def get_recording_info(self) -> Dict[str, Any]:
        """Get information about current/last recording"""
        if self.recorded_frames:
            total_frames = sum(len(f) // self.sample_width for f in self.recorded_frames)
            duration = total_frames / self.sample_rate
        else:
            duration = 0
        
        return {
            'is_recording': self.is_recording,
            'duration': duration,
            'sample_rate': self.sample_rate,
            'channels': self.channels,
            'frames_recorded': len(self.recorded_frames),
            'size_bytes': sum(len(f) for f in self.recorded_frames)
        }


class VoiceActivityDetector:
    """Simple Voice Activity Detection (VAD)"""
    
    def __init__(self, threshold: float = 0.01, 
                 silence_duration: float = 1.0):
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.silence_start = None
        
    def is_speech(self, audio_level: float) -> bool:
        """Check if audio level indicates speech"""
        return audio_level > self.threshold
    
    def should_stop_recording(self, audio_level: float) -> bool:
        """Check if recording should stop due to silence"""
        if self.is_speech(audio_level):
            self.silence_start = None
            return False
        else:
            if self.silence_start is None:
                self.silence_start = time.time()
            elif time.time() - self.silence_start > self.silence_duration:
                return True
        
        return False


def record_audio(duration: Optional[float] = None, 
                 filename: Optional[str] = None,
                 auto_stop_silence: bool = False) -> Optional[str]:
    """
    High-level function to record audio
    """
    recorder = AudioRecorder()
    vad = VoiceActivityDetector() if auto_stop_silence else None
    
    # Generate filename if not provided
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recording_{timestamp}.wav"
    
    print(f"Recording started... {'(auto-stop on silence)' if auto_stop_silence else ''}")
    if duration:
        print(f"Recording for {duration} seconds")
    else:
        print("Press Ctrl+C to stop")
    
    # Level monitoring callback
    def on_level(level):
        # Visual level meter
        bar_length = int(level * 50)
        bar = '█' * bar_length + '░' * (50 - bar_length)
        print(f"\rLevel: [{bar}] {level:.2%}", end='', flush=True)
        
        # Check for silence-based stop
        if vad and vad.should_stop_recording(level):
            recorder.stop_recording()
    
    recorder.on_level_update = on_level if not duration else None
    
    # Start recording
    recorder.start_recording(duration, filename)
    
    try:
        # Wait for recording to complete
        while recorder.is_recording:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n\nStopping recording...")
    
    # Stop and save
    audio_data = recorder.stop_recording()
    
    if audio_data:
        if not recorder.save_recording(audio_data, filename):
            return None
        
        info = recorder.get_recording_info()
        print(f"\n\nRecording saved: {filename}")
        print(f"Duration: {info['duration']:.2f} seconds")
        print(f"Size: {info['size_bytes'] / 1024:.1f} KB")
        
        return filename
    
    return None


if __name__ == '__main__':
    import sys
    
    # Parse arguments
    duration = None
    filename = None
    auto_stop = False
    
    for arg in sys.argv[1:]:
        if arg.startswith('--duration='):
            duration = float(arg.split('=')[1])
        elif arg.startswith('--output='):
            filename = arg.split('=')[1]
        elif arg == '--auto-stop':
            auto_stop = True
        elif arg == '--help':
            print("Usage: python audio_recorder.py [options]")
            print("Options:")
            print("  --duration=SECONDS  Recording duration")
            print("  --output=FILENAME   Output filename")
            print("  --auto-stop        Auto-stop on silence")
            sys.exit(0)
    
    # Record audio
    result = record_audio(duration, filename, auto_stop)
    
    if result:
        print(f"Success! Recording saved to: {result}")
    else:
        print("Recording failed")