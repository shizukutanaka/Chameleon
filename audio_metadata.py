#!/usr/bin/env python3
"""
Audio Metadata Manager
Handles WAV file metadata (LIST INFO chunks) and audio properties
"""

import struct
import wave
import json
import os
from typing import Dict, Optional, Any
from datetime import datetime

class AudioMetadata:
    """Manage audio file metadata and properties"""

    # Standard RIFF INFO tags
    INFO_TAGS = {
        'INAM': 'title',        # Name/Title
        'IART': 'artist',       # Artist
        'IPRD': 'album',        # Product/Album
        'ICRD': 'date',         # Creation date
        'IGNR': 'genre',        # Genre
        'ICMT': 'comment',      # Comment
        'ICOP': 'copyright',    # Copyright
        'IENG': 'engineer',     # Engineer
        'ISFT': 'software',     # Software
        'ISBJ': 'subject',      # Subject
        'ISRC': 'source',       # Source
        'IKEY': 'keywords',     # Keywords
        'ITCH': 'technician'    # Technician
    }

    def __init__(self):
        self.metadata = {}
        self.audio_properties = {}

    def read_wav_metadata(self, filepath: str) -> Dict[str, Any]:
        """Read metadata from WAV file including LIST INFO chunks"""
        try:
            with open(filepath, 'rb') as f:
                # Read RIFF header
                riff = f.read(4)
                if riff != b'RIFF':
                    return {}

                file_size = struct.unpack('<I', f.read(4))[0]
                wave_id = f.read(4)
                if wave_id != b'WAVE':
                    return {}

                metadata = {}
                audio_props = {}

                # Parse chunks
                while f.tell() < file_size + 8:
                    try:
                        chunk_id = f.read(4)
                        if not chunk_id:
                            break

                        chunk_size = struct.unpack('<I', f.read(4))[0]

                        if chunk_id == b'fmt ':
                            # Format chunk - audio properties
                            fmt_data = f.read(chunk_size)
                            if len(fmt_data) >= 16:
                                fmt = struct.unpack('<HHIIHH', fmt_data[:16])
                                audio_props['format'] = fmt[0]
                                audio_props['channels'] = fmt[1]
                                audio_props['sample_rate'] = fmt[2]
                                audio_props['byte_rate'] = fmt[3]
                                audio_props['block_align'] = fmt[4]
                                audio_props['bits_per_sample'] = fmt[5]

                        elif chunk_id == b'data':
                            # Data chunk - calculate duration
                            if audio_props.get('sample_rate') and audio_props.get('channels'):
                                bytes_per_sample = audio_props.get('bits_per_sample', 16) // 8
                                samples = chunk_size // (bytes_per_sample * audio_props['channels'])
                                audio_props['duration'] = samples / audio_props['sample_rate']
                                audio_props['total_samples'] = samples
                            f.seek(chunk_size, 1)

                        elif chunk_id == b'LIST':
                            # LIST chunk - may contain INFO
                            list_type = f.read(4)
                            if list_type == b'INFO':
                                # Parse INFO subchunks
                                info_size = chunk_size - 4
                                info_end = f.tell() + info_size

                                while f.tell() < info_end:
                                    info_id = f.read(4).decode('ascii', errors='ignore')
                                    info_chunk_size = struct.unpack('<I', f.read(4))[0]
                                    info_data = f.read(info_chunk_size)

                                    # Remove null terminators and decode
                                    info_text = info_data.rstrip(b'\x00').decode('utf-8', errors='ignore')

                                    if info_id in self.INFO_TAGS:
                                        metadata[self.INFO_TAGS[info_id]] = info_text

                                    # Align to word boundary
                                    if info_chunk_size % 2:
                                        f.read(1)
                            else:
                                f.seek(chunk_size - 4, 1)

                        else:
                            # Skip unknown chunks
                            f.seek(chunk_size, 1)

                        # Align to word boundary
                        if chunk_size % 2:
                            f.read(1)

                    except Exception:
                        break

                self.metadata = metadata
                self.audio_properties = audio_props

                return {
                    'metadata': metadata,
                    'properties': audio_props,
                    'file_info': {
                        'path': filepath,
                        'size': os.path.getsize(filepath),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    }
                }

        except Exception as e:
            return {'error': str(e)}

    def write_wav_metadata(self, input_file: str, output_file: str,
                          metadata: Dict[str, str]) -> bool:
        """Write metadata to WAV file (creates new file with LIST INFO chunk)"""
        try:
            # Read original WAV data
            with wave.open(input_file, 'rb') as wav_in:
                params = wav_in.getparams()
                frames = wav_in.readframes(params.nframes)

            # Create INFO chunk data
            info_data = b''
            for riff_tag, meta_key in self.INFO_TAGS.items():
                if meta_key in metadata:
                    value = metadata[meta_key].encode('utf-8')
                    # Ensure even length for alignment
                    if len(value) % 2:
                        value += b'\x00'

                    info_data += riff_tag.encode('ascii')
                    info_data += struct.pack('<I', len(value))
                    info_data += value

            # Only add LIST chunk if we have metadata
            if info_data:
                list_chunk = b'LIST'
                list_chunk += struct.pack('<I', 4 + len(info_data))  # Size
                list_chunk += b'INFO'
                list_chunk += info_data

                # Write new WAV with metadata
                with open(output_file, 'wb') as f:
                    # RIFF header
                    f.write(b'RIFF')

                    # Calculate total size
                    fmt_size = 16  # Standard PCM format chunk
                    data_size = len(frames)
                    list_size = len(list_chunk) if info_data else 0
                    total_size = 4 + 8 + fmt_size + 8 + data_size + list_size

                    f.write(struct.pack('<I', total_size))
                    f.write(b'WAVE')

                    # Format chunk
                    f.write(b'fmt ')
                    f.write(struct.pack('<I', 16))
                    f.write(struct.pack('<HHIIHH',
                                      1,  # PCM
                                      params.nchannels,
                                      params.framerate,
                                      params.framerate * params.nchannels * params.sampwidth,
                                      params.nchannels * params.sampwidth,
                                      params.sampwidth * 8))

                    # LIST INFO chunk (if metadata exists)
                    if info_data:
                        f.write(list_chunk)

                    # Data chunk
                    f.write(b'data')
                    f.write(struct.pack('<I', data_size))
                    f.write(frames)

                return True
            else:
                # No metadata, just copy the file
                import shutil
                shutil.copy2(input_file, output_file)
                return True

        except Exception as e:
            print(f"Error writing metadata: {e}")
            return False

    def extract_audio_fingerprint(self, samples: list, sample_rate: int) -> Dict[str, Any]:
        """Generate audio fingerprint for identification"""
        import hashlib

        # Calculate various audio characteristics
        fingerprint = {}

        # Basic hash of audio data
        if samples:
            # Sample first 5 seconds for fingerprint
            sample_count = min(len(samples), sample_rate * 5)
            sample_bytes = bytes(samples[:sample_count])
            fingerprint['hash'] = hashlib.sha256(sample_bytes).hexdigest()[:16]

            # Statistical properties
            avg_amplitude = sum(abs(s) for s in samples[:sample_count]) / sample_count
            max_amplitude = max(abs(s) for s in samples[:sample_count])

            fingerprint['avg_amplitude'] = round(avg_amplitude, 2)
            fingerprint['max_amplitude'] = max_amplitude
            fingerprint['duration'] = len(samples) / sample_rate
            fingerprint['sample_count'] = len(samples)

            # Zero crossing rate (rhythm indicator)
            zero_crossings = 0
            for i in range(1, min(len(samples), sample_rate)):
                if samples[i-1] * samples[i] < 0:
                    zero_crossings += 1
            fingerprint['zcr'] = zero_crossings / sample_rate

        return fingerprint

    def create_cue_points(self, duration: float, interval: float = 30.0) -> list:
        """Create cue points for navigation (every N seconds)"""
        cue_points = []
        time = 0
        index = 1

        while time < duration:
            cue_points.append({
                'index': index,
                'time': time,
                'label': f"Cue {index}",
                'type': 'navigation'
            })
            time += interval
            index += 1

        return cue_points

    def estimate_bitrate(self, filepath: str) -> int:
        """Estimate bitrate from file size and duration"""
        try:
            file_size = os.path.getsize(filepath)
            info = self.read_wav_metadata(filepath)

            if info and 'properties' in info:
                duration = info['properties'].get('duration', 0)
                if duration > 0:
                    # Calculate bitrate in kbps
                    bitrate = (file_size * 8) / (duration * 1000)
                    return int(bitrate)
        except:
            pass

        return 0

    def to_json(self, filepath: str, pretty: bool = True) -> str:
        """Export metadata as JSON"""
        data = self.read_wav_metadata(filepath)
        if pretty:
            return json.dumps(data, indent=2, ensure_ascii=False)
        return json.dumps(data, ensure_ascii=False)

    def from_json(self, json_str: str) -> Dict:
        """Import metadata from JSON"""
        try:
            return json.loads(json_str)
        except:
            return {}


def main():
    """Command-line interface for metadata operations"""
    import argparse

    parser = argparse.ArgumentParser(description='Audio Metadata Manager')
    parser.add_argument('command', choices=['read', 'write', 'fingerprint'],
                       help='Operation to perform')
    parser.add_argument('input', help='Input WAV file')
    parser.add_argument('--output', help='Output file for write operations')
    parser.add_argument('--title', help='Track title')
    parser.add_argument('--artist', help='Artist name')
    parser.add_argument('--album', help='Album name')
    parser.add_argument('--date', help='Creation date')
    parser.add_argument('--genre', help='Genre')
    parser.add_argument('--comment', help='Comment')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    metadata_mgr = AudioMetadata()

    if args.command == 'read':
        # Read and display metadata
        result = metadata_mgr.read_wav_metadata(args.input)

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if 'metadata' in result and result['metadata']:
                print("Metadata:")
                for key, value in result['metadata'].items():
                    print(f"  {key}: {value}")

            if 'properties' in result:
                print("\nAudio Properties:")
                props = result['properties']
                print(f"  Sample Rate: {props.get('sample_rate')} Hz")
                print(f"  Channels: {props.get('channels')}")
                print(f"  Bit Depth: {props.get('bits_per_sample')} bits")
                print(f"  Duration: {props.get('duration', 0):.2f} seconds")

            if 'file_info' in result:
                print("\nFile Information:")
                info = result['file_info']
                print(f"  Path: {info['path']}")
                print(f"  Size: {info['size']:,} bytes")
                print(f"  Modified: {info['modified']}")

    elif args.command == 'write':
        if not args.output:
            print("Error: --output required for write operation")
            return

        # Collect metadata from arguments
        metadata = {}
        if args.title:
            metadata['title'] = args.title
        if args.artist:
            metadata['artist'] = args.artist
        if args.album:
            metadata['album'] = args.album
        if args.date:
            metadata['date'] = args.date
        if args.genre:
            metadata['genre'] = args.genre
        if args.comment:
            metadata['comment'] = args.comment

        # Add software tag
        metadata['software'] = 'Chameleon Audio System'

        success = metadata_mgr.write_wav_metadata(args.input, args.output, metadata)
        if success:
            print(f"Metadata written to {args.output}")
        else:
            print("Failed to write metadata")

    elif args.command == 'fingerprint':
        # Generate audio fingerprint
        try:
            import wave
            import array

            with wave.open(args.input, 'rb') as w:
                params = w.getparams()
                frames = w.readframes(params.nframes)
                samples = array.array('h', frames)

                fingerprint = metadata_mgr.extract_audio_fingerprint(
                    samples, params.framerate
                )

                if args.json:
                    print(json.dumps(fingerprint, indent=2))
                else:
                    print("Audio Fingerprint:")
                    for key, value in fingerprint.items():
                        print(f"  {key}: {value}")
        except Exception as e:
            print(f"Error: {e}")


if __name__ == '__main__':
    main()