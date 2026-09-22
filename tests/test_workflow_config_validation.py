"""Guards for workflow-config input validation (audit 70).

``WorkflowBuilder.from_dict`` fed YAML values straight into fields with no
type checking: ``timeout: "30"`` crashed inside ``future.result`` with an
opaque TypeError, ``timeout: true`` (YAML bool) silently meant ~1 second,
``timeout: -1`` "timed out" instantly, ``max_parallel: "4"`` TypeError'd
inside the ThreadPoolExecutor, and a non-list ``tasks`` or a task missing
``id``/``function`` raised bare AttributeError/KeyError. All are config
errors and must surface as ValueError naming the field.

Also covered: the terminal renderers' stale-tail fix -- ``\r`` rewinds the
cursor without erasing, so a shorter line left characters of the previous
frame visible. ``SpinnerAnimation.stop`` and ``ProgressBar._render`` now pad
to the longest line emitted.
"""

import io
import sys
import time

import pytest

from batch_automation import WorkflowBuilder, TaskExecutor, BatchTask
from ux_improvements import SpinnerAnimation, ProgressBar, ProgressConfig


def _lambda_cfg(**over):
    cfg = {
        'id': 'w',
        'tasks': [{'id': 't', 'function': {'type': 'lambda', 'expression': '1'}}],
    }
    cfg.update(over)
    return cfg


class TestTimeoutValidation:
    @pytest.mark.parametrize("bad", ["abc", True, -5, 0, {"x": 1}])
    def test_bad_timeout_rejected(self, bad):
        cfg = _lambda_cfg()
        cfg['tasks'][0]['timeout'] = bad
        with pytest.raises(ValueError, match="timeout"):
            WorkflowBuilder().from_dict(cfg)

    def test_numeric_string_timeout_coerced(self):
        cfg = _lambda_cfg()
        cfg['tasks'][0]['timeout'] = '0.5'
        task = WorkflowBuilder().from_dict(cfg).tasks[0]
        assert task.timeout == 0.5

    def test_none_and_float_timeout_unchanged(self):
        assert BatchTask(id='t', name='t', function=lambda: 1,
                         inputs={}).timeout is None
        assert BatchTask(id='t', name='t', function=lambda: 1,
                         inputs={}, timeout=0.05).timeout == 0.05


class TestMaxParallelValidation:
    @pytest.mark.parametrize("bad", ["x", 0, -2, True, {"x": 1}])
    def test_bad_max_parallel_rejected(self, bad):
        cfg = _lambda_cfg(max_parallel=bad, type='parallel')
        with pytest.raises(ValueError, match="max_parallel"):
            WorkflowBuilder().from_dict(cfg)

    def test_numeric_string_max_parallel_coerced(self):
        cfg = _lambda_cfg(max_parallel='2', type='parallel')
        assert WorkflowBuilder().from_dict(cfg).max_parallel == 2


class TestTaskStructureValidation:
    def test_tasks_must_be_a_list(self):
        with pytest.raises(ValueError, match="tasks.*list"):
            WorkflowBuilder().from_dict({'id': 'w', 'tasks': 'abc'})

    def test_task_entry_must_be_a_mapping(self):
        with pytest.raises(ValueError, match="mapping"):
            WorkflowBuilder().from_dict({'id': 'w', 'tasks': ['x']})

    def test_task_requires_id(self):
        with pytest.raises(ValueError, match="'id'"):
            WorkflowBuilder().from_dict(
                {'id': 'w', 'tasks': [{'function': {'type': 'lambda',
                                                  'expression': '1'}}]})

    def test_task_requires_function(self):
        with pytest.raises(ValueError, match="'function'"):
            WorkflowBuilder().from_dict({'id': 'w', 'tasks': [{'id': 't'}]})

    def test_function_config_must_be_mapping(self):
        with pytest.raises(ValueError, match="'function'.*mapping"):
            WorkflowBuilder().from_dict(
                {'id': 'w', 'tasks': [{'id': 't', 'function': 'x'}]})


class _CaptureStdout:
    def __init__(self):
        self.buf = io.StringIO()
        self._old = None

    def __enter__(self):
        self._old = sys.stdout
        sys.stdout = self.buf
        return self.buf

    def __exit__(self, *a):
        sys.stdout = self._old


class TestTerminalLineOverwrite:
    def test_spinner_stop_overwrites_last_frame(self):
        with _CaptureStdout() as buf:
            s = SpinnerAnimation('Loading audio data for analysis')
            s.spin()
            s.spin()
            s.stop('Done')
        segments = [seg for seg in buf.getvalue().split('\r') if seg]
        last_frame = segments[-2]
        stop_line = segments[-1].rstrip('\n')
        # The stop line must reach the previous frame's length or it leaves
        # stale characters on a real terminal.
        assert len(stop_line) >= len(last_frame.rstrip())
        assert stop_line.startswith('✓ Done')

    def test_progress_shorter_render_padded(self):
        # At 100% the ETA segment disappears, so the final render is shorter
        # than the 50% line that included "ETA: ...".
        with _CaptureStdout() as buf:
            p = ProgressBar(total=10, description='P',
                            config=ProgressConfig(update_interval=0,
                                                  bar_width=20,
                                                  show_speed=False))
            p.update(5)
            time.sleep(0.01)
            p.update(5)
            p.finish()
        segments = [seg for seg in buf.getvalue().split('\r') if seg]
        assert 'ETA' in segments[-3]
        assert 'ETA' not in segments[-2]
        assert len(segments[-2].rstrip('\n')) >= len(segments[-3].rstrip())
