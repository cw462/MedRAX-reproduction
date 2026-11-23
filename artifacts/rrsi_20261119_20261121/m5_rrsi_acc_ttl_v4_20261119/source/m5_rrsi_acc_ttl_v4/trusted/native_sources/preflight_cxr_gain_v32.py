"""Real local tool probes on an isolated source image; no paid model API calls."""
import argparse
import json
from pathlib import Path

from run_cxr_vqa_toolsets import Tools, exclusive_lock, read, save


def main():
    parser=argparse.ArgumentParser()
    for name in ('config','image-map','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    cfg=read(args.config);runtime=read(cfg['runtime']);mapping=read(args.image_map)
    cid=next(iter(mapping));image=Path(mapping[cid][0]['path']);data=image.parent.parent
    row={'question_id':'isolated-source-'+cid,'images':[image.relative_to(data).as_posix()]}
    checks={'chest_xray_classifier':{},'chest_xray_report_generator':{},
            'chest_xray_segmentation':{'organs':['left lung','right lung','heart']},
            'chest_xray_expert':{'question':'Describe the visible lung field opacities, if any.'},
            'llava_med_qa':{'question':'Describe the visible lung field opacities, if any.'},
            'xray_phrase_grounding':{'phrase':'right lung'},'image_visualizer':{}}
    args.out.mkdir(parents=True,exist_ok=True)
    with exclusive_lock(args.out/'.preflight.lock'):
        backend=Tools(runtime,data,args.out)
        results={}
        for index,name in enumerate(runtime['arms']['M-S']['tools'],1):
            current=row
            if name=='dicom_processor':
                # Synthetic file-format fixture only, from the same isolated pixels.
                # It is not supplied as a native clinical DICOM or target image.
                from PIL import Image
                from pydicom.dataset import FileDataset,FileMetaDataset
                from pydicom.uid import ExplicitVRLittleEndian,SecondaryCaptureImageStorage,generate_uid
                import numpy as np
                fixture=data/'source_preflight_fixture.dcm'
                if not fixture.exists():
                    pixels=np.asarray(Image.open(image).convert('L'))
                    meta=FileMetaDataset();meta.TransferSyntaxUID=ExplicitVRLittleEndian
                    meta.MediaStorageSOPClassUID=SecondaryCaptureImageStorage;meta.MediaStorageSOPInstanceUID=generate_uid()
                    obj=FileDataset(str(fixture),{},file_meta=meta,preamble=b'\0'*128)
                    obj.SOPClassUID=meta.MediaStorageSOPClassUID;obj.SOPInstanceUID=meta.MediaStorageSOPInstanceUID
                    obj.Rows,obj.Columns=pixels.shape;obj.SamplesPerPixel=1;obj.PhotometricInterpretation='MONOCHROME2'
                    obj.BitsAllocated=8;obj.BitsStored=8;obj.HighBit=7;obj.PixelRepresentation=0
                    obj.PixelData=pixels.tobytes();obj.PatientName='SOURCE_PREFLIGHT';obj.PatientID='SOURCE_PREFLIGHT'
                    obj.save_as(str(fixture),enforce_file_format=True)
                current={**row,'images':[fixture.relative_to(data).as_posix()]}
                call_args={}
            else:call_args=checks[name]
            observed=backend.call(current,{'tool':name,'args':call_args},'preflight',index)
            results[name]={'status':observed['status'],'observation_present':observed.get('observation') is not None,
                           'cache_key':observed['cache_key'],'fixture':'synthetic_dicom_from_source_pixels' if name=='dicom_processor' else 'isolated_original_source_image'}
            save(args.out/f'probe_{index}.json',results[name])
            print(json.dumps({'tool':name,**results[name]}),flush=True)
        ready=all(v['status']=='completed' and v['observation_present'] for v in results.values())
        save(args.out/'summary.json',{'ready':ready,'source_case':cid,'paid_calls':0,'tools':results})
        if not ready:raise SystemExit('Tool environment not ready; preserve records and diagnose before targets.')


if __name__=='__main__':main()
