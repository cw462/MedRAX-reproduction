"""Keep the M14 auxiliary model roles and share the AutoDL GPU tools."""

import os
from pathlib import Path

from gsem_memory import read
from skill_services_r55 import MODEL_SLOT, Services as FrozenServices, Tools
from toolsets_r54 import PaidCalls


class Services(FrozenServices):
    def __init__(self, cfg, protocol, runtime, out, key, embedding_model, embedding_base_url=None):
        super().__init__(cfg, protocol, runtime, out, key, embedding_model, embedding_base_url)
        original = read(Path(out).parent.parent / 'auxiliary.json')
        self.auxiliary = PaidCalls(original['config'], original['protocol'], self.out, key)

    def call(self, row, arm, ordinal, messages):
        if arm == MODEL_SLOT:
            return self.auxiliary.call(row, arm, ordinal, messages)
        return super().call(row, arm, ordinal, messages)

    def execute(self, row, policy, data, conditioning):
        if self.tools is None:
            self.tools = Tools(self.runtime, Path(data), self.out, self.call, self.verifier)
            self.tools.worker_gate = Path(os.environ['GSEM_AUTODL_GPU_LOCK'])
        return super().execute(row, policy, data, conditioning)
