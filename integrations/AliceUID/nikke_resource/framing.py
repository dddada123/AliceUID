"""Bounded CPU-only feature matching; public image hashes, never an AI service."""
import hashlib,json,threading,time
from .cache import atomic_write,read_metadata

VERSION='portrait-anchor-sift-3'
_gate=threading.Lock()


def locate_anchor(full_source,portrait_source):
    """Isolate OpenCV pyramids/threads; release all worker RAM after one match."""
    import subprocess,sys
    from pathlib import Path
    payload=json.dumps(dict(full=full_source,portrait=portrait_source)).encode()
    if len(payload)>16*1024*1024:
        return dict(matched=False,reason='input_too_large')
    result=subprocess.run([sys.executable,'-I','-B',str(Path(__file__).with_name('_framing_worker.py'))],
                          input=payload,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                          timeout=12,check=True,
                          creationflags=subprocess.CREATE_NO_WINDOW if sys.platform=='win32' else 0)
    value=json.loads(result.stdout)
    if not isinstance(value,dict) or type(value.get('matched')) is not bool:
        raise ValueError('invalid framing worker result')
    return value


def cached_anchor(root,full_source,portrait_source,full_hash,portrait_hash):
    key=hashlib.sha256(json.dumps([VERSION,full_hash,portrait_hash]).encode()).hexdigest()
    path=root/'rolemeta/framing'/(key+'.json')
    with _gate:
        cached=read_metadata(path)
        if cached.get('version')==VERSION and (cached.get('reason')!='unavailable' or cached.get('retry_after',0)>time.time()):
            return cached
        try:
            result=locate_anchor(full_source,portrait_source)
        except Exception:
            result=dict(matched=False,reason='unavailable',retry_after=time.time()+600)
        result.update(version=VERSION)
        atomic_write(path,json.dumps(result,sort_keys=True).encode())
        return result
