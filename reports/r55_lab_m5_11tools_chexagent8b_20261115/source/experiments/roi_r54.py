"""Deterministic original-pixel ROI extraction; never generative super-resolution."""
import math
from pathlib import Path

def crop(image,args,folder):
    from PIL import Image,ImageDraw
    if set(args)-{'box','zoom'}:raise ValueError('unknown_roi_arguments')
    b=args.get('box');zoom=args.get('zoom',2)
    if not isinstance(b,list) or len(b)!=4 or any(type(v) not in (int,float) or not math.isfinite(v) for v in b):raise ValueError('finite_normalized_box_required')
    if not (0<=b[0]<b[2]<=1 and 0<=b[1]<b[3]<=1):raise ValueError('invalid_box')
    if type(zoom) not in (int,float) or not math.isfinite(zoom) or not 1<=zoom<=4:raise ValueError('zoom_must_be_1_to_4')
    im=Image.open(image).convert('RGB');w,h=im.size
    pixel=[math.floor(b[0]*w),math.floor(b[1]*h),math.ceil(b[2]*w),math.ceil(b[3]*h)]
    roi=im.crop(pixel);target=(round(roi.width*zoom),round(roi.height*zoom))
    if max(target)>4096:raise ValueError('roi_output_exceeds_4096_pixels')
    enlarged=roi.resize(target,Image.Resampling.BICUBIC)
    marked=im.copy();d=ImageDraw.Draw(marked);d.rectangle(pixel,outline='red',width=max(1,round(min(w,h)/250)))
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    names=[folder/'original.png',folder/'roi_context.png',folder/'roi_zoom.png']
    for obj,p in zip((im,marked,enlarged),names):obj.save(p)
    return {'original_size':[w,h],'requested_box_normalized':b,'original_pixel_box':pixel,
            'actual_box_normalized':[pixel[0]/w,pixel[1]/h,pixel[2]/w,pixel[3]/h],
            'zoom':zoom,'crop_size':list(target),'derived_images':[str(p) for p in names],
            'coordinates':'original image, top-left origin; x right, y down; patient side not inferred',
            'limitations':'Interpolation adds no acquired detail. Do not infer patient laterality from screen position. Review original plus crop; crop can omit findings.'}
