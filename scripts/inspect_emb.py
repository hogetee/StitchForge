"""Read-only EMB container inspection. Does not decode Wilcom stitch objects.

Install optional reference tools: pip install -e '.[reference]'. Outputs stay local.
"""
import argparse,hashlib,io,json,zlib
from pathlib import Path
from PIL import Image
import olefile


def inspect(path,out):
    out.mkdir(parents=True,exist_ok=True)
    report={'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
            'bytes':path.stat().st_size,'streams':[],
            'limitation':'Property IDs are raw, unverified values. Native objects, sewing order and underlay are NOT decoded.'}
    with olefile.OleFileIO(path) as archive:
        for name in archive.listdir():
            data=archive.openstream(name).read()
            entry={'name':'/'.join(name),'bytes':len(data)}
            if name[-1].startswith('\x05'):
                props=archive.getproperties(name)
                entry['raw_properties']={str(k):v if isinstance(v,(str,int,float,type(None))) else
                    {'bytes':len(v),'hex_prefix':v[:48].hex()} for k,v in props.items()}
            report['streams'].append(entry)
            if name==['DESIGN_ICON']:
                decoded=zlib.decompressobj().decompress(data[4:],2_000_000)
                with Image.open(io.BytesIO(decoded)) as image:
                    image.convert('RGB').save(out/'embedded-thumbnail.png')
    (out/'container-report.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('file',type=Path); parser.add_argument('output',type=Path)
    args=parser.parse_args(); result=inspect(args.file,args.output)
    print(json.dumps({'bytes':result['bytes'],'streams':len(result['streams']),'output':str(args.output)}))
