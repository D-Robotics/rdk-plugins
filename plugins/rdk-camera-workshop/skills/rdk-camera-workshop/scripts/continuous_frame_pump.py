"""One SDK frame owner, continuously drains/releases during CPU/disk processing.
Caller must stop and join before pausing/closing native context. No SDK setters.
"""
import queue,threading,time
class FramePump:
 def __init__(self,metadata,picture,last_frame=None):
  self.metadata=metadata;self.picture_callback=picture;self.last=last_frame;self.requests=queue.Queue();self.stopping=threading.Event();self.failure=None;self.count=0;self.pictures=0;self.owner_ident=None;self.started_ns=None;self.finished_ns=None
  self.thread=threading.Thread(target=self._run,name='imx415-single-frame-owner',daemon=True)
 def start(self):
  self.thread.start();return self
 def _check(self,info):
  if self.last is not None and (info['frame_id']<=self.last['frame_id'] or info['timestamp_ns']<=self.last['timestamp_ns']):raise ValueError('pump_frame_identity_not_new')
  self.last=dict(info);self.count+=1
 def _run(self):
  self.owner_ident=threading.get_ident();self.started_ns=time.monotonic_ns();request=None
  try:
   while not self.stopping.is_set():
    try:request=self.requests.get_nowait()
    except queue.Empty:request=None
    stage=request['stage'] if request else 'pump-background'
    if request and request['kind']=='picture':
     result=self.picture_callback(stage);self._check(result[1]);self.pictures+=1
    else:
     result=self.metadata(stage);self._check(result['frame'])
    if request:request['result']=result;request['event'].set();request=None
    # Native frame/get/set functions share the verified context mutex. Yield
    # after each release so a pending ISP getter/setter can acquire it.
    time.sleep(.001)
  except BaseException as exc:
   self.failure=exc
   if request:request['error']=exc;request['event'].set()
  finally:
   self.finished_ns=time.monotonic_ns()
   while True:
    try:r=self.requests.get_nowait()
    except queue.Empty:break
    r['error']=self.failure or RuntimeError('frame_pump_stopped');r['event'].set()
 def _request(self,kind,stage):
  if self.stopping.is_set():raise RuntimeError('frame_pump_stopping')
  if self.failure is not None:raise self.failure
  r={'kind':kind,'stage':stage,'event':threading.Event()};self.requests.put(r);deadline=time.monotonic()+6
  while not r['event'].wait(.05):
   if self.failure is not None:raise self.failure
   if not self.thread.is_alive():raise RuntimeError('frame_pump_owner_exited')
   if time.monotonic()>=deadline:raise TimeoutError('frame_pump_request_deadline')
  if 'error' in r:raise r['error']
  return r['result']
 def take(self,stage):return self._request('metadata',stage)
 def picture(self):return self._request('picture','pump-picture')
 def stop(self):
  self.stopping.set();self.thread.join(timeout=4)
  if self.thread.is_alive():raise RuntimeError('live_frame_pump_close_forbidden')
  return {'joined':True,'ownerThreadIdent':self.owner_ident,'frames':self.count,'pictures':self.pictures,'startedMonotonicNs':self.started_ns,'finishedMonotonicNs':self.finished_ns,'error':str(self.failure) if self.failure else None,'sdkCode':getattr(self.failure,'sdk_code',None),'scope':'single frame consumer and copied requested pictures; not an ISP setter or timing qualification'}
