#!/usr/bin/env python3
"""
Audio Scripting Engine - Advanced automation and scripting for audio processing
Supports custom scripts, templates, and complex processing chains
"""

import json
import time
import os
import re
from typing import List, Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from datetime import datetime
import subprocess
from pathlib import Path

@dataclass
class AudioTask:
    """Individual audio processing task"""
    id: str
    command: str
    input_files: List[str]
    output_file: str
    parameters: Dict[str, Any]
    depends_on: List[str] = None
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 2
    
    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = []

@dataclass 
class ScriptExecution:
    """Script execution status"""
    script_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    status: str = "running"  # running, completed, failed, cancelled
    
class AudioScriptEngine:
    """Advanced audio processing script engine"""
    
    def __init__(self):
        self.tasks: List[AudioTask] = []
        self.completed_tasks: List[str] = []
        self.failed_tasks: List[str] = []
        self.task_outputs: Dict[str, Any] = {}
        self.variables: Dict[str, Any] = {}
        self.templates: Dict[str, Dict] = {}
        self.execution: Optional[ScriptExecution] = None
        
        # Built-in functions
        self.functions = {
            'now': lambda: datetime.now().isoformat(),
            'timestamp': lambda: int(time.time()),
            'env': lambda key: os.environ.get(key, ''),
            'exists': lambda path: os.path.exists(path),
            'basename': lambda path: os.path.basename(path),
            'dirname': lambda path: os.path.dirname(path),
            'join': lambda *parts: os.path.join(*parts)
        }
        
        self._load_templates()
    
    def _load_templates(self):
        """Load built-in processing templates"""
        self.templates = {
            'podcast_processing': {
                'description': 'Complete podcast processing pipeline',
                'tasks': [
                    {
                        'id': 'denoise',
                        'command': 'denoise',
                        'parameters': {'noise-reduction': 0.6, 'clarity': 1.3}
                    },
                    {
                        'id': 'normalize',
                        'command': 'quality',
                        'parameters': {'target-quality': 85},
                        'depends_on': ['denoise']
                    },
                    {
                        'id': 'compress',
                        'command': 'effect',
                        'parameters': {'compressor': True},
                        'depends_on': ['normalize']
                    }
                ]
            },
            'voice_enhancement': {
                'description': 'Professional voice enhancement',
                'tasks': [
                    {
                        'id': 'remove_noise',
                        'command': 'denoise',
                        'parameters': {'noise-reduction': 0.5, 'clarity': 1.4}
                    },
                    {
                        'id': 'eq_boost',
                        'command': 'effect',
                        'parameters': {'eq-low': -2, 'eq-mid': 3, 'eq-high': 1},
                        'depends_on': ['remove_noise']
                    },
                    {
                        'id': 'final_limit',
                        'command': 'quality',
                        'parameters': {'target-quality': 90},
                        'depends_on': ['eq_boost']
                    }
                ]
            },
            'music_mastering': {
                'description': 'Basic music mastering chain',
                'tasks': [
                    {
                        'id': 'eq_master',
                        'command': 'effect',
                        'parameters': {'eq-low': 1, 'eq-mid': 0, 'eq-high': 2}
                    },
                    {
                        'id': 'compress_master',
                        'command': 'effect',
                        'parameters': {'compressor': True, 'ratio': 3.0},
                        'depends_on': ['eq_master']
                    },
                    {
                        'id': 'limit_master',
                        'command': 'quality',
                        'parameters': {'target-quality': 95},
                        'depends_on': ['compress_master']
                    }
                ]
            }
        }
    
    def load_script(self, script_file: str) -> bool:
        """Load script from JSON file"""
        try:
            with open(script_file, 'r', encoding='utf-8') as f:
                script_data = json.load(f)
            
            # Load variables
            self.variables = script_data.get('variables', {})
            
            # Load tasks
            self.tasks = []
            for task_data in script_data.get('tasks', []):
                task = AudioTask(
                    id=task_data['id'],
                    command=task_data['command'],
                    input_files=task_data.get('input_files', []),
                    output_file=task_data.get('output_file', ''),
                    parameters=task_data.get('parameters', {}),
                    depends_on=task_data.get('depends_on', []),
                    timeout=task_data.get('timeout', 300),
                    max_retries=task_data.get('max_retries', 2)
                )
                self.tasks.append(task)
            
            return True
            
        except Exception as e:
            print(f"Error loading script: {e}")
            return False
    
    def create_script_from_template(self, template_name: str, 
                                  input_file: str, output_file: str) -> bool:
        """Create script from template"""
        if template_name not in self.templates:
            print(f"Template '{template_name}' not found")
            return False
        
        template = self.templates[template_name]
        
        # Clear existing tasks
        self.tasks = []
        
        # Generate tasks from template
        for i, task_template in enumerate(template['tasks']):
            # Generate intermediate filenames
            if i == 0:
                task_input = input_file
            else:
                prev_task = template['tasks'][i-1]
                task_input = f"temp_{prev_task['id']}.wav"
            
            if i == len(template['tasks']) - 1:
                task_output = output_file
            else:
                task_output = f"temp_{task_template['id']}.wav"
            
            task = AudioTask(
                id=task_template['id'],
                command=task_template['command'],
                input_files=[task_input],
                output_file=task_output,
                parameters=task_template.get('parameters', {}),
                depends_on=task_template.get('depends_on', [])
            )
            
            self.tasks.append(task)
        
        return True
    
    def execute_script(self, script_name: str = "unnamed") -> bool:
        """Execute the loaded script"""
        if not self.tasks:
            print("No tasks to execute")
            return False
        
        # Initialize execution tracking
        self.execution = ScriptExecution(
            script_name=script_name,
            start_time=datetime.now(),
            total_tasks=len(self.tasks)
        )
        
        print(f"Starting script execution: {script_name}")
        print(f"Total tasks: {len(self.tasks)}")
        
        try:
            # Execute tasks in dependency order
            while len(self.completed_tasks) + len(self.failed_tasks) < len(self.tasks):
                executed_any = False
                
                for task in self.tasks:
                    if (task.id not in self.completed_tasks and 
                        task.id not in self.failed_tasks and
                        self._can_execute_task(task)):
                        
                        success = self._execute_task(task)
                        executed_any = True
                        
                        if success:
                            self.completed_tasks.append(task.id)
                            self.execution.completed_tasks += 1
                            print(f"✓ Task '{task.id}' completed")
                        else:
                            self.failed_tasks.append(task.id)
                            self.execution.failed_tasks += 1
                            print(f"✗ Task '{task.id}' failed")
                
                if not executed_any:
                    # Check for circular dependencies or all remaining tasks failed
                    remaining_tasks = [t for t in self.tasks 
                                     if t.id not in self.completed_tasks 
                                     and t.id not in self.failed_tasks]
                    if remaining_tasks:
                        print("Error: Circular dependencies or unresolvable tasks detected")
                        for task in remaining_tasks:
                            self.failed_tasks.append(task.id)
                            self.execution.failed_tasks += 1
                    break
            
            # Final status
            self.execution.end_time = datetime.now()
            
            if self.execution.failed_tasks == 0:
                self.execution.status = "completed"
                print(f"\n✓ Script execution completed successfully!")
                print(f"  Completed: {self.execution.completed_tasks}/{self.execution.total_tasks} tasks")
            else:
                self.execution.status = "failed"
                print(f"\n✗ Script execution completed with errors!")
                print(f"  Completed: {self.execution.completed_tasks}/{self.execution.total_tasks} tasks")
                print(f"  Failed: {self.execution.failed_tasks} tasks")
            
            duration = (self.execution.end_time - self.execution.start_time).total_seconds()
            print(f"  Duration: {duration:.1f} seconds")
            
            return self.execution.failed_tasks == 0
            
        except KeyboardInterrupt:
            self.execution.status = "cancelled"
            print("\n⚠ Script execution cancelled by user")
            return False
        except Exception as e:
            self.execution.status = "failed"
            print(f"\n✗ Script execution failed: {e}")
            return False
    
    def _can_execute_task(self, task: AudioTask) -> bool:
        """Check if task dependencies are satisfied"""
        return all(dep_id in self.completed_tasks for dep_id in task.depends_on)
    
    def _execute_task(self, task: AudioTask) -> bool:
        """Execute a single task"""
        try:
            # Substitute variables in parameters
            processed_params = self._substitute_variables(task.parameters)
            
            # Build command
            cmd_parts = ['python3', 'main.py', task.command]
            
            # Add input files
            for input_file in task.input_files:
                input_file = self._substitute_variables(input_file)
                cmd_parts.append(input_file)
            
            # Add output file
            if task.output_file:
                output_file = self._substitute_variables(task.output_file)
                cmd_parts.append(output_file)
            
            # Add parameters
            for key, value in processed_params.items():
                if isinstance(value, bool):
                    if value:
                        cmd_parts.append(f'--{key}')
                else:
                    cmd_parts.extend([f'--{key}', str(value)])
            
            # Execute command
            print(f"Executing: {' '.join(cmd_parts)}")
            
            result = subprocess.run(
                cmd_parts,
                capture_output=True,
                text=True,
                timeout=task.timeout,
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                # Store task output for potential use by other tasks
                self.task_outputs[task.id] = {
                    'stdout': result.stdout,
                    'stderr': result.stderr,
                    'returncode': result.returncode,
                    'output_file': task.output_file
                }
                return True
            else:
                print(f"Task failed with code {result.returncode}")
                if result.stderr:
                    print(f"Error: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"Task timed out after {task.timeout} seconds")
            return False
        except Exception as e:
            print(f"Task execution error: {e}")
            return False
    
    def _substitute_variables(self, obj: Any) -> Any:
        """Substitute variables in strings, recursively for dicts/lists"""
        if isinstance(obj, str):
            # Substitute variables like ${variable_name}
            def replace_var(match):
                var_name = match.group(1)
                if var_name in self.variables:
                    return str(self.variables[var_name])
                elif var_name in self.functions:
                    return str(self.functions[var_name]())
                else:
                    return match.group(0)  # Return original if not found
            
            return re.sub(r'\$\{([^}]+)\}', replace_var, obj)
            
        elif isinstance(obj, dict):
            return {k: self._substitute_variables(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._substitute_variables(item) for item in obj]
        else:
            return obj
    
    def save_script(self, filename: str) -> bool:
        """Save current script to JSON file"""
        try:
            script_data = {
                'variables': self.variables,
                'tasks': [asdict(task) for task in self.tasks]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(script_data, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"Error saving script: {e}")
            return False
    
    def add_task(self, task_id: str, command: str, input_files: List[str], 
                 output_file: str, parameters: Dict[str, Any] = None,
                 depends_on: List[str] = None) -> bool:
        """Add a task to the script"""
        if parameters is None:
            parameters = {}
        if depends_on is None:
            depends_on = []
        
        # Check for duplicate task IDs
        if any(task.id == task_id for task in self.tasks):
            print(f"Task ID '{task_id}' already exists")
            return False
        
        task = AudioTask(
            id=task_id,
            command=command,
            input_files=input_files,
            output_file=output_file,
            parameters=parameters,
            depends_on=depends_on
        )
        
        self.tasks.append(task)
        return True
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the script"""
        self.tasks = [task for task in self.tasks if task.id != task_id]
        return True
    
    def list_templates(self) -> List[str]:
        """List available templates"""
        return list(self.templates.keys())
    
    def get_template_info(self, template_name: str) -> Optional[Dict]:
        """Get information about a template"""
        return self.templates.get(template_name)
    
    def set_variable(self, name: str, value: Any):
        """Set a script variable"""
        self.variables[name] = value
    
    def get_execution_report(self) -> Optional[Dict]:
        """Get detailed execution report"""
        if not self.execution:
            return None
        
        return {
            'script_name': self.execution.script_name,
            'start_time': self.execution.start_time.isoformat(),
            'end_time': self.execution.end_time.isoformat() if self.execution.end_time else None,
            'duration': (self.execution.end_time - self.execution.start_time).total_seconds() 
                       if self.execution.end_time else None,
            'status': self.execution.status,
            'total_tasks': self.execution.total_tasks,
            'completed_tasks': self.execution.completed_tasks,
            'failed_tasks': self.execution.failed_tasks,
            'success_rate': self.execution.completed_tasks / self.execution.total_tasks * 100,
            'completed_task_ids': self.completed_tasks,
            'failed_task_ids': self.failed_tasks
        }


def create_processing_script(template: str, input_file: str, output_file: str) -> str:
    """Create and save a processing script from template"""
    engine = AudioScriptEngine()
    
    if not engine.create_script_from_template(template, input_file, output_file):
        return ""
    
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_filename = f"script_{template}_{timestamp}.json"
    
    # Add some variables
    engine.set_variable('input_file', input_file)
    engine.set_variable('output_file', output_file)
    engine.set_variable('timestamp', timestamp)
    
    if engine.save_script(script_filename):
        return script_filename
    
    return ""


def run_batch_processing(input_directory: str, output_directory: str, 
                        template: str = "podcast_processing") -> bool:
    """Run batch processing using template"""
    import glob
    
    # Find audio files
    audio_extensions = ['*.wav', '*.mp3', '*.flac', '*.ogg']
    audio_files = []
    
    for ext in audio_extensions:
        pattern = os.path.join(input_directory, ext)
        audio_files.extend(glob.glob(pattern))
    
    if not audio_files:
        print(f"No audio files found in {input_directory}")
        return False
    
    # Ensure output directory exists
    os.makedirs(output_directory, exist_ok=True)
    
    print(f"Processing {len(audio_files)} files with template '{template}'")
    
    successful = 0
    failed = 0
    
    for audio_file in audio_files:
        filename = os.path.basename(audio_file)
        name_without_ext = os.path.splitext(filename)[0]
        output_file = os.path.join(output_directory, f"{name_without_ext}_processed.wav")
        
        print(f"\nProcessing: {filename}")
        
        # Create engine for this file
        engine = AudioScriptEngine()
        
        if engine.create_script_from_template(template, audio_file, output_file):
            if engine.execute_script(f"batch_{template}_{filename}"):
                successful += 1
                print(f"✓ Successfully processed: {filename}")
            else:
                failed += 1
                print(f"✗ Failed to process: {filename}")
        else:
            failed += 1
            print(f"✗ Failed to create script for: {filename}")
    
    print(f"\nBatch processing complete:")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Total: {len(audio_files)}")
    
    return failed == 0


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python audio_scripting.py create <template> <input> <output>")
        print("  python audio_scripting.py execute <script.json>")
        print("  python audio_scripting.py batch <input_dir> <output_dir> [template]")
        print("  python audio_scripting.py templates")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "create":
        if len(sys.argv) != 5:
            print("Usage: python audio_scripting.py create <template> <input> <output>")
            sys.exit(1)
        
        template, input_file, output_file = sys.argv[2:5]
        script_file = create_processing_script(template, input_file, output_file)
        
        if script_file:
            print(f"Script created: {script_file}")
        else:
            print("Failed to create script")
    
    elif command == "execute":
        if len(sys.argv) != 3:
            print("Usage: python audio_scripting.py execute <script.json>")
            sys.exit(1)
        
        script_file = sys.argv[2]
        engine = AudioScriptEngine()
        
        if engine.load_script(script_file):
            success = engine.execute_script(os.path.basename(script_file))
            
            # Print report
            report = engine.get_execution_report()
            if report:
                print(f"\nExecution Report:")
                print(f"  Status: {report['status']}")
                print(f"  Success Rate: {report['success_rate']:.1f}%")
                if report['duration']:
                    print(f"  Duration: {report['duration']:.1f} seconds")
        else:
            print(f"Failed to load script: {script_file}")
    
    elif command == "batch":
        if len(sys.argv) < 4:
            print("Usage: python audio_scripting.py batch <input_dir> <output_dir> [template]")
            sys.exit(1)
        
        input_dir = sys.argv[2]
        output_dir = sys.argv[3]
        template = sys.argv[4] if len(sys.argv) > 4 else "podcast_processing"
        
        run_batch_processing(input_dir, output_dir, template)
    
    elif command == "templates":
        engine = AudioScriptEngine()
        templates = engine.list_templates()
        
        print("Available templates:")
        for template_name in templates:
            info = engine.get_template_info(template_name)
            print(f"  {template_name}: {info['description']}")
            print(f"    Tasks: {len(info['tasks'])}")
    
    else:
        print(f"Unknown command: {command}")