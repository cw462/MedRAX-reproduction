"""Publish saved V11 observable checkpoints without inference or rescoring.

Image data URIs are decoded byte-for-byte into linked files. Existing published
images are reused when byte-identical. No hidden reasoning is requested or added.
"""
import argparse
import base64
import json
from pathlib import Path
import re

RUNS={'S1':'v11_selector60','S2':'v11_followup60','S3':'v11_blindread60'}
SECRET_KEYS={'api_key','authorization','password','access_token','refresh_token','private_key',
             'reservation_id','account_balance','balance_cny','committed_cny','reserved_cny','remaining_cny'}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--cache',type=Path,default=Path('local_assets/history_v11'))
    ap.add_argument('--image-manifest',type=Path,default=Path('local_assets/v11_public_sources/manifest.json'))
    ap.add_argument('--out',type=Path,default=Path('reports/v11'))
    args=ap.parse_args();out=args.out
    image_map=json.loads(args.image_manifest.read_text(encoding='utf-8'))['image_mapping']
    by_bytes={p.read_bytes():p.relative_to(out).as_posix() for p in (out/'images').rglob('*') if p.suffix.lower() in {'.jpg','.jpeg','.png'}}
    new_images=[]
    def clean(v):
        if isinstance(v,dict):return {k:clean(x) for k,x in v.items() if k.lower() not in SECRET_KEYS}
        if isinstance(v,list):return [clean(x) for x in v]
        if not isinstance(v,str):return v
        if v.startswith('data:image/'):
            mime,payload=v.split(';base64,',1);data=base64.b64decode(payload,validate=True)
            rel=by_bytes.get(data)
            if not rel:
                suffix={ 'data:image/png':'.png','data:image/jpeg':'.jpg','data:image/webp':'.webp'}.get(mime)
                if not suffix:raise ValueError('unsupported image MIME')
                rel=f'images/request_payloads/payload_{len(new_images)+1:03d}{suffix}'
                p=out/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
                by_bytes[data]=rel;new_images.append({'path':rel,'bytes':len(data),'mime':mime[5:]})
            return '../../'+rel
        for source,dest in sorted(image_map.items(),key=lambda x:-len(x[0])):v=v.replace(source,'../../'+dest)
        v=re.sub(r'/home/[^/\s]+/[^/\s]+/MedRAX_reproduction_\d+', '[runtime_root]', v)
        v=re.sub(r'(?i)(?:(?<![A-Za-z0-9])[a-z]:[\\/]|/(?:home|tmp|mnt|Users)/)[^\s\"\'<>\]\},]+','[private_path_omitted]',v)
        if re.search(r'(?i)\b(?:sk-[a-z0-9_-]{20,}|gh[pousr]_[a-z0-9]{25,})\b',v):raise ValueError('credential-like value')
        return v
    rows=[]
    for stage,run in RUNS.items():
        for folder in sorted((args.cache/run/'checkpoints').iterdir()):
            if not folder.is_dir():continue
            files={p.name:json.loads(p.read_text(encoding='utf-8')) for p in sorted(folder.glob('*.json'))}
            payload={'stage':stage,'question_id':folder.name,'source_run':run,'source_files':list(files),
                     'publication_transform':'Base64 images replaced by relative file references; runtime paths, reservation IDs and account-level balances removed. Observable messages and experiment-specific timing/usage/charges retained.',
                     'records':clean(files)}
            target=out/'traces'/stage/(folder.name+'.json');target.parent.mkdir(parents=True,exist_ok=True)
            target.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            msgs=[k for k in files if 'messages' in k]
            rows.append({'stage':stage,'question_id':folder.name,'path':target.relative_to(out).as_posix(),'source_files':len(files),'message_files':msgs,'route':files.get('terminal.json',{}).get('route')})
    manifest={'scope':'All saved JSON checkpoints of completed S1/S2/S3, including inherited-only terminals. Only disagreement cases made new selector calls.',
              'record_count':len(rows),'new_request_images':new_images,'records':rows}
    (out/'trace-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# V11 完整调用与终态记录','','[总索引](../README.md) · [机器清单](../trace-manifest.json)','','每阶段保留 60 题终态；只有实际触发新调用的题包含 messages。原始可观测请求、响应、解析结果、补充观察、调用计数与用量均来自保存的 checkpoint。完整原始 assistant 回复可核对解析器遗漏，不能把模型断言当作人工影像真值。','','图像 data URI 改为相对图片引用；若请求中的压缩/缩放图片与已公开原图字节不同，则单独保留实际请求图片。运行机器绝对路径被脱敏；记录本身未重生成、未重新评分。','','| 阶段 | 题目 | 路由 | 消息文件 |','|---|---|---|---|']
    for row in rows:lines.append(f"| {row['stage']} | [{row['question_id']}]({row['stage']}/{row['question_id']}.json) | {row['route']} | {', '.join(row['message_files']) or '无新增调用，仅终态'} |")
    (out/'traces'/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'terminal_records':len(rows),'source_json_files':sum(r['source_files'] for r in rows),'new_request_images':len(new_images)}))

if __name__=='__main__':main()
