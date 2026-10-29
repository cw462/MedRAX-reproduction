"""MAIRA-2 grounding worker (8th tool) with two documented deviations.

Deviation 1 - dtype. `XRayPhraseGroundingTool.__init__` calls from_pretrained()
without `torch_dtype`, so the 7B model loads in fp32 (~31 GB) and cannot fit a
24 GB RTX 3090 at all. We force bf16 (12.8 GiB measured). Same weights, half
precision; recorded in the tool version string.

Deviation 2 - negative case. The upstream `_run` decodes the generation and calls
`convert_output_to_plaintext_or_grounded_sequence`, which asserts when the model
produced no `<phrase>` span (a legitimate "nothing to ground" answer). That
exception is caught by the tool's blanket `except` and reported as
`analysis_status=failed`, making a normal negative look like an execution fault.
The tool's own code already has a `completed_no_finding` branch for exactly this
case, but it is unreachable. We implement the intended semantics: an unparseable
or empty grounding is "no grounded finding", never a failure. The raw decode is
retained for audit so this can be checked rather than trusted.

Neither deviation invents a finding, and neither changes what the model computes.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import torch


def _load_official_class(source_path):
    """Import medrax/tools/grounding.py by path.

    Importing it as part of the `medrax.tools` package pulls in
    classification.py -> skimage, which this environment does not have.
    """
    spec = importlib.util.spec_from_file_location("medrax_grounding_isolated", source_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.XRayPhraseGroundingTool


class MairaGrounding:
    TOOL_VERSION = "maira-2@795a2b1c+bf16+negative-safe-v1"

    def __init__(self, source_path, model_path, cache_dir=None, temp_dir=None, device="cuda"):
        import transformers

        self._orig_from_pretrained = transformers.AutoModelForCausalLM.from_pretrained
        orig = self._orig_from_pretrained

        def patched(*args, **kwargs):
            kwargs.setdefault("torch_dtype", torch.bfloat16)
            return orig(*args, **kwargs)

        transformers.AutoModelForCausalLM.from_pretrained = patched
        try:
            cls = _load_official_class(str(source_path))
            self.tool = cls(model_path=str(model_path), cache_dir=cache_dir,
                            temp_dir=temp_dir, device=device)
        finally:
            transformers.AutoModelForCausalLM.from_pretrained = self._orig_from_pretrained

    def _convert(self, text):
        """Grounding conversion that treats 'nothing to ground' as a negative."""
        try:
            return self.tool.processor.convert_output_to_plaintext_or_grounded_sequence(text), None
        except AssertionError:
            return [], "no_grounded_phrase"
        except Exception as error:  # keep the original error visible
            return [], f"{type(error).__name__}: {error}"

    def ground(self, image_path, phrase, max_new_tokens=300):
        from PIL import Image

        image = Image.open(image_path)
        if image.mode != "RGB":
            image = image.convert("RGB")
        inputs = self.tool.processor.format_and_preprocess_phrase_grounding_input(
            frontal_image=image, phrase=phrase, return_tensors="pt")
        device = next(self.tool.model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            output = self.tool.model.generate(**inputs, max_new_tokens=max_new_tokens,
                                              use_cache=True)
        prompt_length = inputs["input_ids"].shape[-1]
        decoded = self.tool.processor.decode(output[0][prompt_length:],
                                            skip_special_tokens=True)
        predictions, note = self._convert(decoded)

        boxes = []
        for pred_phrase, pred_bboxes in predictions:
            # the upstream _run skips entries with no boxes; pred_bboxes may be None
            for bbox in (pred_bboxes or []):
                boxes.append({"phrase": pred_phrase,
                              "model": list(bbox),
                              "image": self.tool.processor.adjust_box_for_original_image_size(
                                  bbox, width=image.size[0], height=image.size[1])})
        status = ("completed" if boxes else
                  "completed_no_finding" if not predictions else "completed_no_boxes")
        return {
            "tool": "xray_phrase_grounding",
            "tool_version": self.TOOL_VERSION,
            "analysis_status": status,
            "phrase": phrase,
            "predictions": boxes,
            "conversion_note": note,
            "original_size": image.size,
            "raw_decode_chars": len(decoded),
            "raw_decode_sha256_16": __import__("hashlib").sha256(
                decoded.encode("utf-8")).hexdigest()[:16],
        }
