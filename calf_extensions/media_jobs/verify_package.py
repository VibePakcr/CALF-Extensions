"""Check the declared portable payload bytes. Does not execute CALF or install tools."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re


def check(root):
    root=Path(root)
    if not root.is_absolute() or root.is_symlink() or root.resolve(strict=True)!=root:
        raise ValueError('physical_absolute_package_root_required')
    inventory=root/'FILES.sha256'
    if inventory.is_symlink() or inventory.stat().st_size>1048576:raise ValueError('inventory_limit_or_link')
    rows=inventory.read_text(encoding='utf-8').splitlines()
    if not 1<=len(rows)<=1024:raise ValueError('inventory_count')
    wanted={};folded=set()
    for row in rows:
        match=re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*)',row)
        if not match:raise ValueError('inventory_format')
        digest,name=match.groups();parts=PurePosixPath(name).parts
        if any(part in ['.','..'] for part in parts) or name.casefold() in folded or name=='FILES.sha256':
            raise ValueError('inventory_path_or_duplicate')
        folded.add(name.casefold());wanted[name]=digest
    total=0
    for name,digest in wanted.items():
        path=root.joinpath(*PurePosixPath(name).parts)
        if path.is_symlink() or path.resolve(strict=True)!=path or not path.is_file():raise ValueError('payload_path_changed: '+name)
        total+=path.stat().st_size
        if total>32*1024*1024:raise ValueError('payload_size_limit')
        h=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(32768),b''):h.update(chunk)
        if h.hexdigest()!=digest:raise ValueError('payload_hash_mismatch: '+name)
    for path in root.rglob('*'):
        if path.is_symlink():raise ValueError('unlisted_link')
        if path.is_file():
            name=path.relative_to(root).as_posix()
            # Finder can add this metadata while users inspect the folder.
            if name not in wanted and name!='FILES.sha256' and path.name!='.DS_Store':
                raise ValueError('unlisted_payload_file: '+name)
    return {'schema':'calf.pack.payload-check.v1','status':'PASS','files':len(wanted),'bytes':total,
            'scope':'Payload identity only; not a publisher signature or a native work verdict.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,default=Path(__file__).resolve().parent)
    args=p.parse_args()
    try:value=check(args.root)
    except (ValueError,OSError,UnicodeError) as error:
        print(json.dumps({'status':'FAIL','error':str(error)},ensure_ascii=False));return 1
    print(json.dumps(value,ensure_ascii=False,indent=2));return 0

if __name__=='__main__':raise SystemExit(main())
