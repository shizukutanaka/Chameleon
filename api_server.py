#!/usr/bin/env python3
"""
REST API Server for Chameleon Audio System
Provides HTTP endpoints for audio processing
"""

import os
import json
import array
import tempfile
import hashlib
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import mimetypes

from chameleon import AudioProcessor
from audio_effects import AudioEffects
from audio_analyzer import AudioAnalyzer
from audio_converter import AudioConverter

class AudioAPIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for audio API"""

    processor = AudioProcessor()
    effects = AudioEffects()
    analyzer = AudioAnalyzer()
    converter = AudioConverter()

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)

        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'name': 'Chameleon Audio API',
                'version': '2.0.0',
                'endpoints': {
                    'GET /': 'API information',
                    'GET /health': 'Health check',
                    'POST /process': 'Process audio file',
                    'POST /analyze': 'Analyze audio file',
                    'POST /convert': 'Convert audio format',
                    'GET /effects': 'List available effects'
                }
            }
            self.wfile.write(json.dumps(response, indent=2).encode())

        elif parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'ready': True}
            self.wfile.write(json.dumps(response).encode())

        elif parsed_path.path == '/effects':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'effects': [
                    'echo', 'chorus', 'distortion', 'low_pass', 'high_pass',
                    'compressor', 'tremolo', 'pitch_shift', 'noise_gate', 'auto_gain'
                ],
                'operations': [
                    'normalize', 'amplify', 'fade', 'trim', 'reverse', 'speed'
                ]
            }
            self.wfile.write(json.dumps(response, indent=2).encode())

        else:
            self.send_error(404, 'Endpoint not found')

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        content_length = int(self.headers.get('Content-Length', 0))

        if parsed_path.path == '/process':
            self.handle_process(content_length)
        elif parsed_path.path == '/analyze':
            self.handle_analyze(content_length)
        elif parsed_path.path == '/convert':
            self.handle_convert(content_length)
        else:
            self.send_error(404, 'Endpoint not found')

    def handle_process(self, content_length):
        """Process audio with specified operations"""
        try:
            # Read request body
            body = self.rfile.read(content_length)
            request = json.loads(body)

            # Validate request
            if 'audio_data' not in request or 'operation' not in request:
                self.send_error(400, 'Missing required fields: audio_data, operation')
                return

            # Decode audio data (base64 or raw bytes)
            audio_data = request['audio_data']
            if isinstance(audio_data, str):
                import base64
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = bytes(audio_data)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Load audio
            samples, info = self.processor.load_wav(tmp_path)

            # Apply operation
            operation = request['operation']
            params = request.get('params', {})

            if operation == 'normalize':
                result = self.processor.normalize(samples, params.get('peak', 0.95))
            elif operation == 'amplify':
                result = self.processor.amplify(samples, params.get('gain', 0))
            elif operation == 'fade':
                result = self.processor.fade(
                    samples, info['sample_rate'],
                    params.get('fade_in', 0), params.get('fade_out', 0)
                )
            elif operation == 'echo':
                result = self.effects.echo(
                    samples, info['sample_rate'],
                    params.get('delay_ms', 300), params.get('decay', 0.5)
                )
            elif operation == 'compressor':
                result = self.effects.compressor(
                    samples, params.get('threshold', 0.7), params.get('ratio', 0.5)
                )
            else:
                self.send_error(400, f'Unknown operation: {operation}')
                os.unlink(tmp_path)
                return

            # Save result
            out_path = tmp_path.replace('.wav', '_out.wav')
            self.processor.save_wav(out_path, result, info['sample_rate'])

            # Read and encode result
            with open(out_path, 'rb') as f:
                import base64
                result_data = base64.b64encode(f.read()).decode()

            # Clean up
            os.unlink(tmp_path)
            os.unlink(out_path)

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'success': True,
                'operation': operation,
                'audio_data': result_data,
                'sample_rate': info['sample_rate'],
                'duration': len(result) / info['sample_rate']
            }
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_error(500, f'Processing error: {str(e)}')

    def handle_analyze(self, content_length):
        """Analyze audio and return metrics"""
        try:
            # Read request body
            body = self.rfile.read(content_length)
            request = json.loads(body)

            # Decode audio data
            audio_data = request['audio_data']
            if isinstance(audio_data, str):
                import base64
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = bytes(audio_data)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Load and analyze
            samples, info = self.processor.load_wav(tmp_path)

            # Compute metrics
            analysis = {
                'rms': float(self.analyzer.get_rms(samples)),
                'peak': float(self.analyzer.get_peak_amplitude(samples)),
                'dynamic_range': float(self.analyzer.get_dynamic_range(samples)),
                'zero_crossing_rate': float(
                    self.analyzer.get_zero_crossing_rate(samples, info['sample_rate'])
                ),
                'dominant_frequency': float(
                    self.analyzer.find_dominant_frequency(samples, info['sample_rate'])
                ),
                'spectral_centroid': float(
                    self.analyzer.get_spectral_centroid(samples, info['sample_rate'])
                ),
                'sample_rate': info['sample_rate'],
                'duration': len(samples) / info['sample_rate'],
                'channels': info['channels']
            }

            # Clean up
            os.unlink(tmp_path)

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(analysis, indent=2).encode())

        except Exception as e:
            self.send_error(500, f'Analysis error: {str(e)}')

    def handle_convert(self, content_length):
        """Convert audio format"""
        try:
            # Read request body
            body = self.rfile.read(content_length)
            request = json.loads(body)

            # Decode audio data
            audio_data = request['audio_data']
            if isinstance(audio_data, str):
                import base64
                audio_bytes = base64.b64decode(audio_data)
            else:
                audio_bytes = bytes(audio_data)

            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp.write(audio_bytes)
                tmp_path = tmp.name

            # Load audio
            samples, info = self.processor.load_wav(tmp_path)

            # Apply conversions
            result = samples
            target_sr = request.get('sample_rate', info['sample_rate'])
            target_channels = request.get('channels', info['channels'])

            # Resample if needed
            if target_sr != info['sample_rate']:
                result = self.converter.resample(result, info['sample_rate'], target_sr)

            # Convert channels if needed
            if target_channels != info['channels']:
                if target_channels == 2 and info['channels'] == 1:
                    result = self.converter.mono_to_stereo(result)
                elif target_channels == 1 and info['channels'] == 2:
                    result = self.converter.stereo_to_mono(result)

            # Save result
            out_path = tmp_path.replace('.wav', '_converted.wav')
            self.processor.save_wav(out_path, result, target_sr, channels=target_channels)

            # Read and encode result
            with open(out_path, 'rb') as f:
                import base64
                result_data = base64.b64encode(f.read()).decode()

            # Clean up
            os.unlink(tmp_path)
            os.unlink(out_path)

            # Send response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'success': True,
                'audio_data': result_data,
                'sample_rate': target_sr,
                'channels': target_channels,
                'duration': len(result) / target_sr
            }
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            self.send_error(500, f'Conversion error: {str(e)}')

    def log_message(self, format, *args):
        """Custom log format"""
        print(f"[{self.log_date_time_string()}] {format%args}")

def main():
    """Start API server"""
    host = os.environ.get('API_HOST', 'localhost')
    port = int(os.environ.get('API_PORT', 8000))

    server = HTTPServer((host, port), AudioAPIHandler)
    print(f"Chameleon Audio API Server")
    print(f"Listening on http://{host}:{port}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        server.shutdown()

if __name__ == '__main__':
    main()