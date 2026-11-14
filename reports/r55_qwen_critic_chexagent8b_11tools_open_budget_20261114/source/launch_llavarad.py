"""Load the pinned LLaVA-Rad Llama backend with the deployed Transformers."""

import importlib.abc
import importlib.machinery
import sys
from unittest.mock import patch

from transformers import AutoConfig

from r55_baseline_vqa import main


class LlamaOnly(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'llava.model':
            spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
            spec.loader = self
            return spec

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        from llava.model.language_model.llava_llama import LlavaLlamaForCausalLM, LlavaConfig

        module.LlavaLlamaForCausalLM = LlavaLlamaForCausalLM
        module.LlavaConfig = LlavaConfig


def run():
    original = AutoConfig.register

    def register(name, config, exist_ok=False):
        return original(name, config, exist_ok=exist_ok or (name == 'llava' and config.__name__ == 'LlavaConfig'))

    with patch.object(AutoConfig, 'register', side_effect=register), patch.object(sys, 'meta_path', [LlamaOnly(), *sys.meta_path]):
        main()


if __name__ == '__main__':
    run()
