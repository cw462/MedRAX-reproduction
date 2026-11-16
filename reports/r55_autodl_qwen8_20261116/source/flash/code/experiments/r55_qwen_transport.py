"""Bind R55 Qwen generations to the original Token Plan profile."""


MODEL = 'qwen3.7-plus'
BASE_URL = 'https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'


def token_plan_route(model, profile, key, credential_slot):
    if model not in (MODEL, 'qwen3.6-flash'):
        return {}
    if (credential_slot, profile.base_url) != ('token_plan', BASE_URL):
        raise ValueError('Qwen3.7-Plus requires the frozen Token Plan profile')
    if not key or key.startswith('sk-ws-'):
        raise ValueError('Qwen3.7-Plus requires the original Token Plan credential')
    return {'transport': 'token_plan', 'endpoint': BASE_URL}
