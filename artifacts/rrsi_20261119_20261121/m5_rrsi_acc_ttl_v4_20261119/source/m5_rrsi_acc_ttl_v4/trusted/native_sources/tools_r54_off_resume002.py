"""Original eight-tool executor with an explicit, independently bound local recovery."""
from pathlib import Path
from toolsets_r54 import Tools as OriginalTools
from online_memory_r49 import save_once
from r54_off_resume_evidence import (QID, KEY, ORDINAL, TOOL, approved_recovery,
                                     require_resume, read)
from r54_resume_worker import await_gpu1


class Tools(OriginalTools):
    def __init__(self, runtime, data_root, out, **kwargs):
        super().__init__(runtime, data_root, out, **kwargs)
        self.resume = require_resume(Path(out).parent)

    def recovered_observation(self, row, call):
        recovered = approved_recovery(self.out.parent); request = recovered['request']
        index = call.get('image_index', 1)
        if (call.get('tool') != TOOL or call.get('args', {}) != request['args']
                or type(index) is not int or not 1 <= index <= len(row['images'])
                or str((self.data_root / row['images'][index - 1]).resolve()) != request['image']
                or self.runtime['backend_config'] != request['runtime']):
            raise ValueError('R54_replayed_action_differs_from_user_interrupted_tool')
        value = dict(recovered['result'], tool=TOOL, cache_key=KEY, cache_hit=True,
                     technical_user_stop_recovery=recovered['adoption'])
        if len(row['images']) > 1:
            value['image_index'] = index
        return value

    def call(self, row, call, arm, ordinal):
        if (self.resume['dataset'] == 'chexbench' and row['question_id'] == QID
                and arm == 'R49-AGENT' and ordinal == ORDINAL):
            value = self.recovered_observation(row, call)
            save_once(self.out / 'tool_selections' / arm / QID / (str(ordinal) + '.json'), value)
        else:
            value = super().call(row, call, arm, ordinal)
        if value.get('technical_user_stop_recovery'):
            recovered = approved_recovery(self.out.parent)
            if value['technical_user_stop_recovery'] != recovered['adoption']:
                raise ValueError('R54_recovery_selection_adoption_changed')
            save_once(self.out.parent / 'resume002_tool_deliveries' / row['question_id'] / (str(ordinal) + '.json'),
                      {'selection': value, 'adoption': recovered['adoption'], 'new_model_attempt': False})
        return value

    def observe(self, name, spec, args, image, identity, folder, saved):
        if folder.name == KEY and self.resume['dataset'] == 'chexbench':
            recovered = approved_recovery(self.out.parent)
            if identity != recovered['result']['identity']:
                raise ValueError('R54_recovery_identity_changed')
            return dict(recovered['result'], technical_user_stop_recovery=recovered['adoption']), True
        if not saved.exists() and not (folder / 'started.json').exists():
            cpu_roi = name == 'roi_crop' and spec.get('backend') == 'roi_crop' and spec.get('gpu') == ''
            if not cpu_roi and str(spec.get('gpu')) != '1':
                raise ValueError('R54_resume_tool_GPU_must_remain_1')
            folder.mkdir(parents=True, exist_ok=True)
            if not cpu_roi:
                await_gpu1(folder)
        return super().observe(name, spec, args, image, identity, folder, saved)
