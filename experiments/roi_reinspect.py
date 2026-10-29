"""V4 D_roi: actually show the current case's full image and a region to the VLM.

The plan is explicit that writing a crop file and printing its path is *not* a
visual reinspection. So this module does two things separately:

  make_roi()     crops a region around a real grounded box, keeping context, and
                 writes it into the run's private directory (auditable artefact);
  review_region() sends BOTH the full image and the crop to the vision model in
                 one request and returns its observation as text.

A box may only come from the current case's own grounding result. There is no
branch that borrows a box from a training case, and no branch that invents one:
without a real box the caller must fall back to another action.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

from PIL import Image


def clamp_box(box, margin=0.15):
    """Normalised xyxy -> pixel box with a context margin, clamped to the image."""
    x1, y1, x2, y2 = (float(v) for v in box[:4])
    if not all(0.0 <= v <= 1.0 for v in (x1, y1, x2, y2)):
        raise ValueError("box coordinates must be normalised to [0, 1]")
    if x2 <= x1 or y2 <= y1:
        raise ValueError("box must have positive width and height")
    width, height = x2 - x1, y2 - y1
    mx, my = width * margin, height * margin
    return (max(0.0, x1 - mx), max(0.0, y1 - my), min(1.0, x2 + mx), min(1.0, y2 + my))


def make_roi(image_path, box, out_dir, margin=0.15, name="roi", min_side=224):
    """Crop the region plus context; returns (roi_path, pixel_box, original_size)."""
    image = Image.open(image_path)
    if image.mode != "RGB":
        image = image.convert("RGB")
    cx1, cy1, cx2, cy2 = clamp_box(box, margin=margin)
    left, upper = int(cx1 * image.width), int(cy1 * image.height)
    right, lower = int(cx2 * image.width), int(cy2 * image.height)
    crop = image.crop((left, upper, right, lower))
    # never upsample a tiny region into fake detail; keep a floor so the model can see it
    if crop.width < min_side or crop.height < min_side:
        scale = max(min_side / max(crop.width, 1), min_side / max(crop.height, 1))
        crop = crop.resize((max(1, int(crop.width * scale)), max(1, int(crop.height * scale))),
                           Image.BICUBIC)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    crop.save(path)
    return str(path), (left, upper, right, lower), image.size


def _data_url(image_path, max_side=1024):
    image = Image.open(image_path).convert("RGB")
    if max(image.size) > max_side:
        scale = max_side / max(image.size)
        image = image.resize((int(image.width * scale), int(image.height * scale)), Image.BICUBIC)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


PROMPT = (
    "You are shown two images of the same chest radiograph. The first is the full "
    "image; the second is a crop of the region of interest, from the normalised box "
    "{box} of the original. Describe only what is visible in the crop that is "
    "relevant to this question, and state when the crop does not settle it. "
    "Do not assume the cropping is correct and do not invent measurements."
)


def review_region(model, image_path, roi_path, box, question, max_tokens=None):
    """One multimodal request containing the full image *and* the ROI crop.

    The output bound comes from the model's own configuration; passing extra
    kwargs through LangChain's invoke is not reliable across versions.
    """
    content = [
        {"type": "text", "text": PROMPT.format(box=[round(float(v), 3) for v in box])},
        {"type": "text", "text": f"QUESTION: {question}"},
        {"type": "image_url", "image_url": {"url": _data_url(image_path)}},
        {"type": "image_url", "image_url": {"url": _data_url(roi_path)}},
    ]
    reply = model.invoke([{"role": "user", "content": content}])
    text = reply.content if isinstance(reply.content, str) else str(reply.content)
    return text.strip()
