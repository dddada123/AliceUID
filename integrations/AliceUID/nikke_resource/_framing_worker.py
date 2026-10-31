"""Short-lived local CV worker. No network, credentials, model or third-party service."""
import base64,json,sys,time
def locate_anchor(full_source,portrait_source):
    import cv2
    import numpy as np
    def gray(source):
        raw=base64.b64decode(source.split(';base64,',1)[1],validate=True)
        image=cv2.imdecode(np.frombuffer(raw,dtype=np.uint8),cv2.IMREAD_GRAYSCALE)
        if image is None or image.size>8_000_000:
            raise ValueError('invalid framing source')
        return image
    full=gray(full_source);portrait=gray(portrait_source)
    rgba=cv2.imdecode(np.frombuffer(base64.b64decode(portrait_source.split(';base64,',1)[1],validate=True),dtype=np.uint8),cv2.IMREAD_UNCHANGED)
    head_row=0
    if rgba is not None and rgba.ndim==3 and rgba.shape[2]==4:
        alpha=rgba[:max(1,round(rgba.shape[0]*.5)),round(rgba.shape[1]*.15):round(rgba.shape[1]*.85),3]
        visible=np.flatnonzero(np.count_nonzero(alpha>128,axis=1)>=max(3,round(rgba.shape[1]*.03)))
        if visible.size:head_row=int(visible[0])
    fh,fw=full.shape
    factor=min(1.,896/max(full.shape))
    reduced=cv2.resize(full,None,fx=factor,fy=factor,interpolation=cv2.INTER_AREA) if factor<1 else full
    # Only match the portrait's upper section, so armor/weapons cannot define the anchor.
    roi=portrait[:max(1,round(portrait.shape[0]*.60))]
    reduced=reduced[:max(1,round(reduced.shape[0]*.60))]
    detector=cv2.SIFT_create(nfeatures=1600,contrastThreshold=.015)
    q,qd=detector.detectAndCompute(roi,None);t,td=detector.detectAndCompute(reduced,None)
    if qd is None or td is None or len(q)<6 or len(t)<6:
        return dict(matched=False,reason='insufficient_features')
    pairs=cv2.BFMatcher().knnMatch(qd,td,k=2)
    good=[pair[0] for pair in pairs if len(pair)==2 and pair[0].distance<.75*pair[1].distance]
    if len(good)<8:
        return dict(matched=False,reason='insufficient_matches')
    a=np.float32([q[m.queryIdx].pt for m in good]);b=np.float32([t[m.trainIdx].pt for m in good])
    matrix,mask=cv2.estimateAffinePartial2D(a,b,method=cv2.RANSAC,ransacReprojThreshold=3,maxIters=1500)
    if matrix is None or mask is None:
        return dict(matched=False,reason='no_consensus')
    count=int(mask.sum());ratio=count/len(good)
    scale=float(np.hypot(matrix[0,0],matrix[1,0]));rotation=float(np.degrees(np.arctan2(matrix[1,0],matrix[0,0])))
    anchor=matrix@np.array([portrait.shape[1]*.5,portrait.shape[0]*.23,1.])
    x,y=float(anchor[0]/factor/fw),float(anchor[1]/factor/fh)
    spread=np.ptp(a[mask.ravel().astype(bool)],axis=0)
    if count<8 or ratio<.5 or abs(rotation)>12 or not .15<=scale<=12 or not .08<x<.92 or not -.05<y<.65 or min(spread)<18:
        return dict(matched=False,reason='low_confidence',inliers=count)
    head=float((matrix@np.array([portrait.shape[1]*.5,head_row,1.]))[1]/factor/fh)
    return dict(matched=True,x=x,y=y,head_top=max(0.,head) if -.1<head<y else None,inliers=count,match_ratio=round(ratio,3),method='SIFT+RANSAC')


if __name__=='__main__':
    import cv2
    cv2.setNumThreads(1)
    started=time.perf_counter()
    raw=sys.stdin.buffer.read(16*1024*1024+1)
    if len(raw)>16*1024*1024:
        raise ValueError('framing input too large')
    data=json.loads(raw)
    result=locate_anchor(data['full'],data['portrait'])
    result['worker_seconds']=round(time.perf_counter()-started,4)
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes
        class PMC(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in ('peak','working','qp','q','np','n','page','ppage')]
        ctypes.windll.kernel32.GetCurrentProcess.restype=wintypes.HANDLE
        ctypes.windll.psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
        p=PMC();p.cb=ctypes.sizeof(p)
        ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(p),p.cb)
        result['worker_peak_mb']=round(p.peak/1024**2,2)
    else:
        import resource
        # Linux ru_maxrss is KiB; macOS is bytes.
        value=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        result['worker_peak_mb']=round(value/(1024**2 if sys.platform=='darwin' else 1024),2)
    sys.stdout.write(json.dumps(result))
