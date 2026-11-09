"""Resume experiments across source/hash updates while recording plan history."""
import json
from pathlib import Path

if __package__:
    from . import diagnostic_eval as diag
else:
    import diagnostic_eval as diag


class RecordedRunJournal(diag.RunJournal):
    """Hashes are records; question identities still prevent duplicate API work."""

    def __init__(self, output, plan, *, resume=False):
        if not resume:
            super().__init__(output, plan, resume=False)
            return
        self.output, self.plan = Path(output).resolve(), plan
        self.plan_hash = diag.hash_value(plan)
        self.starts, self.terminals = {}, {}
        self.allowed = {(r['question_id'], r['arm']) for r in plan['schedule']}
        self.manifest = json.loads((self.output / 'manifest.json').read_text(encoding='utf-8'))
        original = self.manifest['plan']
        original_schedule = {(r['question_id'], r['arm']) for r in original['schedule']}
        if self.allowed != original_schedule or len(plan['schedule']) != len(self.allowed):
            raise ValueError('Resume must retain the planned questions and arms')
        raw = (self.output / 'results.jsonl').read_text(encoding='utf-8')
        if raw and not raw.endswith('\n'):
            raise ValueError('Incomplete journal tail; finish recovery before resuming')
        for line in raw.splitlines():
            self._accept(json.loads(line))
        # Preserve the original manifest and outcomes; append the configuration
        # used for new work instead of forcing it to equal an older digest.
        with (self.output / 'plan_history.jsonl').open('a', encoding='utf-8') as handle:
            diag.durable_line(handle, {'recorded_utc': diag.utc_now(), 'hash_policy': 'record_only',
                'run_id': self.manifest['run_id'], 'plan_sha256': self.plan_hash, 'plan': plan})
        self.handle = (self.output / 'results.jsonl').open('a', encoding='utf-8')
        for key, start in self.starts.items():
            if key not in self.terminals:
                self.finish({'question_id': key[0], 'arm': key[1], 'thread_id': start['thread_id'],
                    'status': 'interrupted_no_retry', 'answer_letter': None,
                    'issue_tags': ['interrupted_started_arm'], 'actual_model_calls': None,
                    'actual_tool_attempts': None, 'validated_tool_returns': None,
                    'observed_usage_sum': None, 'usage_complete': False,
                    'final_finish_reason': None, 'stop_run': False})
