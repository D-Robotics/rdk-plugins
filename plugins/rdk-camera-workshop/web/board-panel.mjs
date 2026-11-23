import {normalizedModelHash,presetModelHash} from '/guide.mjs';

const phases={before:'调前',after:'调后',live:'本轮'};
const liveWindowMs=3500;
const errors={board_archive_unconfigured:'请用 Studio 在本工位运行课程检测入口并配置其结果目录。',
  board_receipt_pending:'板端尚未写出回执。请确认本组任务已启动，再刷新。',
  board_model_mismatch:'板上模型与本工位训练产物的哈希不一致，请核对实际 .bin。',
  board_receipt_changed:'板端已写出新的运行回执。请刷新板端结果后再对照或留证。',
  board_asset_integrity_failed:'文件字节或配置回读和板端回执不一致，请检查原始制品。',
  board_asset_missing:'这份证据还没有归档，请刷新或核对板端结果。'};

export function createBoardPanel({key,$,element,button,notify,getReport,save,attach,compare}) {
  let report;
  let lastModel;
  let lastPath;
  let issue='';
  let reading=false;
  let saving=false;
  let generation=0;
  let preview;
  let lastAdvance;
  let watchRequested=false;
  let pending=false;
  const refreshButton=button('读取板端检测',()=>refresh(),'primary');
  const gammaButton=button('看 Gamma 实拍前后',compareGamma,'ghost');
  const adoptButton=button('采用回执并留证',saveEvidence,'ghost');
  $('board-actions').append(refreshButton,gammaButton,adoptButton);
  async function fetchResult(part,timeout=15000) {
    const response=await fetch('/board/'+part,{headers:{'X-Workshop-Session':key},signal:AbortSignal.timeout(timeout)});
    if(!response.ok) {
      const {error}=await response.json().catch(()=>({}));
      throw new Error(errors[error]??'板端回执读取失败，请核对结果文件。');
    }
    return response;
  }
  function fetchArtifact(receipt,name) {
    return fetchResult('file/'+encodeURIComponent(name)+'?receipt='+encodeURIComponent(receipt.receiptSha256));
  }
  function activeModel(course) {
    if(course.routing.selected==='C') return;
    if(course.routing.selected==='B') return presetModelHash(course.resume.evidence.preset_model);
    const model=normalizedModelHash(course.resume.evidence.x5_model_hash);
    const run=course.resume.run;
    if(run?.source!=='robogo'||model===run.modelSha256) return model;
  }
  function syncModel() {
    const course=getReport();
    const model=activeModel(course);
    const path=course.routing.selected;
    if(lastModel===model&&lastPath===path) return;
    lastModel=model;lastPath=path;generation++;report=undefined;issue='';reading=false;
    watchRequested=false;pending=false;clearPreview();
  }
  function clearPreview() {
    if(preview) URL.revokeObjectURL(preview.url);
    preview=undefined;lastAdvance=undefined;
  }
  async function refresh(automatic=false) {
    if(reading) return;
    const current=++generation;
    reading=true;
    if(!automatic) {watchRequested=true;issue='';render();}
    try {
      const known=preview?.frame.sha256;
      const {view:next,imageBase64,previewPending}=await(await fetchResult('preview'+(known?'?known='+known:''),2800)).json();
      if(current!==generation) return;
      if(next.modelSha256!==lastModel) throw new Error(errors.board_model_mismatch);
      if(report&&next.runId!==report.runId&&imageBase64===undefined) clearPreview();
      const frame=next.latestDetection;
      const sameRun=Boolean(preview&&next.runId&&preview.runId===next.runId);
      if(sameRun&&frame&&BigInt(frame.sdkTimestampNs)<BigInt(preview.frame.sdkTimestampNs)) return;
      if(frame&&(imageBase64||known===frame.sha256&&preview)) {
        const advances=sameRun&&BigInt(frame.sdkTimestampNs)>BigInt(preview.frame.sdkTimestampNs);
        if(imageBase64) {
          const bytes=Uint8Array.from(atob(imageBase64),value=>value.charCodeAt(0));
          const url=URL.createObjectURL(new Blob([bytes],{type:'image/jpeg'}));
          if(preview) URL.revokeObjectURL(preview.url);
          preview={url,frame,runId:next.runId};
        } else {
          preview.frame=frame;preview.runId=next.runId;
        }
        if(advances) lastAdvance=Date.now();
        else if(!sameRun) lastAdvance=undefined;
      }
      report=next;pending=Boolean(previewPending);issue='';
    } catch(error) {
      if(current===generation) issue=error.name==='TimeoutError'?'检测画面读取超时。会继续尝试读取新帧。':error.message;
    }
    finally {if(current===generation) {reading=false;render();}}
  }
  async function compareGamma() {
    const current=report;
    try {
      const assets=['before','after'].map(kind=>current.assets.find(item=>item.kind===kind));
      const stills=await Promise.all(assets.map(async asset=>{
        const contents=await(await fetchArtifact(current,asset.file)).blob();
        return new File([contents],'板端-'+asset.file,{type:contents.type});
      }));
      const proof=current.gamma?.curveReadback;
      const matched=proof?.status==='verified'&&assets[1].tuningHash===current.readbackHash&&
        /^[a-f0-9]{64}$/.test(proof.actualCurrentCurveSha256);
      compare(stills,assets,matched?proof:undefined);
    } catch(error) {notify(error.message);}
  }
  async function saveEvidence() {
    if(saving) return;
    saving=true;render();
    const recorded=report;
    const receiptNames=['receipt.json',...recorded.snapshotNames];
    const initialPath=getReport().routing.selected;
    try {
      const names=[...receiptNames,...recorded.assets.map(item=>item.file)];
      const files=await Promise.all(names.map(async name=>{
        const blob=await(await fetchArtifact(recorded,name)).blob();
        return new File([blob],'板端-'+name,{type:blob.type});
      }));
      const course=getReport();
      if(course.routing.selected!==initialPath||activeModel(course)!==recorded.modelSha256) throw new Error('工位路径或模型已变化，请重新读取回执。');
      attach(files,recorded);
      const evidence={...course.resume.evidence};
      if(recorded.status==='completed'&&recorded.frameCount>0&&recorded.previewStopped&&recorded.staticBpu) {
        const frame=recorded.latestDetection??recorded.assets.findLast(asset=>asset.kind==='detection_after')??
          recorded.assets.findLast(asset=>asset.kind==='detection_live');
        if(frame&&frame.tuningHash===recorded.readbackHash) {
          const blockers={...course.resume.blockers};delete blockers.vision_device_transport_failed;
          const original=recorded.assets.find(asset=>asset.kind==='before');
          const candidate=recorded.assets.find(asset=>asset.kind==='after');
          if(recorded.cameraIdentity&&original&&recorded.restoration==='verified') {
            evidence.current_device_identity=[recorded.cameraIdentity.board,recorded.cameraIdentity.sensorModel,recorded.cameraIdentity.cameraMode].filter(Boolean).join(' · ');
            evidence.fresh_camera_image='SDK '+original.sdkTimestampNs+' · 板端-'+original.file;
            evidence.original_snapshot='板端-original-isp.json · '+original.tuningHash;
          }
          if(candidate&&candidate.tuningHash===recorded.readbackHash&&recorded.gamma?.curveReadback?.status==='verified'&&
              /^[a-f0-9]{64}$/.test(recorded.gamma.curveReadback.actualCurrentCurveSha256)) {
            evidence.gamma_readback='sha256:'+recorded.gamma.curveReadback.actualCurrentCurveSha256;
            evidence.gamma_fresh_frame='SDK '+candidate.sdkTimestampNs+' · 板端-'+candidate.file;
          }
          const previous=recorded.receiptSha256===course.resume.evidence[
            course.routing.selected==='A'?'board_detection_receipt':'preset_detection_receipt'];
          if(course.routing.selected==='A') {
            evidence.board_model_hash='sha256:'+recorded.modelSha256;
            evidence.actual_bpu_inference='板端静态 BPU 推理，板端-receipt.json';
            evidence.matching_pre_postprocess='板端运行确认 640 NV12、六个输出头、park/qrcode/obstacle';
            evidence.exclusive_camera_owner='单一路 SDK 相机流，板端-receipt.json';
            evidence.tuning_in_detection_pipeline='sha256:'+recorded.readbackHash;
            evidence.fresh_frames='SDK '+frame.sdkTimestampNs;
            evidence.inference_result='运行成功';
            evidence.board_detection_receipt=recorded.receiptSha256;
            if(!previous) evidence.target_result='未验证';
            evidence.live_detections='本轮持续采集推理，板端-'+frame.file+'；目标判定待学员核对';
          } else if(course.routing.selected==='B') {
            evidence.preset_board_model_hash='sha256:'+recorded.modelSha256;
            evidence.preset_bpu_inference='预置模型板端静态 BPU 推理，板端-receipt.json';
            evidence.preset_stream_isp='sha256:'+recorded.readbackHash;
            evidence.preset_live_frame='SDK '+frame.sdkTimestampNs;
            evidence.preset_inference_result='运行成功';
            evidence.preset_detection_receipt=recorded.receiptSha256;
            if(!previous) evidence.preset_target_result='未验证';
            evidence.preset_live_detections='预置模型实时帧 · 板端-'+frame.file;
          }
          if(course.routing.selected==='A'||course.routing.selected==='B') {
            if(recorded.restoration==='verified') evidence.restoration_and_release='已恢复及停止采流，板端-restored-isp.json';
            if(recorded.restoration==='no_write') evidence.restoration_and_release='未写入 ISP，已停流，见板端-receipt.json';
          }
          save({evidence,blockers},'已采用本轮设备回执，现场检出结果可单独复核。');
        }
      }
      notify('板端实拍、ISP 回读和检测回执已加入成果包。');
    } catch(error) {notify(error.message);}
    finally {saving=false;render();}
  }
  function render() {
    const course=getReport();const panel=$('board');
    panel.hidden=!activeModel(course);
    if(panel.hidden) return;
    $('board-title').textContent=course.routing.selected==='B'?'预置模型检测':'本组模型检测';
    const r=report;
    const streaming=r?.status==='started'&&Boolean(preview)&&!issue&&!pending&&
      lastAdvance!==undefined&&Date.now()-lastAdvance<=liveWindowMs;
    const done=r?.status==='completed'||r?.status==='failed';
    $('board-status').textContent=issue?'需要处理':streaming?'实时更新':r?.status==='failed'?'板端任务失败':
      pending?'同步新帧中':r?.status==='completed'?'运行结束 · 已归档':r||reading?'等待板端新帧':'等待读取';
    $('board-status').className='status-tag'+(issue||r?.status==='failed'?' blocked':streaming||r?.status==='completed'?' ok':'');
    $('board-help').textContent=issue||(preview?
      done?'查看本轮归档帧，按你选定的目标记录是否检出。':
      '移动课程目标，观察框和类别的变化。按你选择的目标记录是否检出。':
      '从本工位启动课程检测。收到与模型及 ISP 匹配的新帧后，这里会显示带框画面。');
    const figure=$('board-frame');
    const img=$('board-frame-image');
    figure.hidden=!preview;
    if(preview) {
      const {frame,url}=preview;
      if(img.getAttribute('src')!==url) img.src=url;
      $('board-frame-caption').textContent=phases[frame.phase]+' · '+(streaming?'新帧正在更新':done?'本轮归档帧':'最近已验证帧')+
        ' · SDK '+frame.sdkTimestampNs;
      const boxes=Object.entries(frame.counts).filter(([,count])=>count>0).map(([name,count])=>name+' ×'+count).join('、');
      $('board-frame-detail').textContent='此帧推理 '+frame.forwardMs.toFixed(1)+' ms · '+(boxes||'此帧无检测框');
    } else {
      img.removeAttribute('src');
      $('board-frame-detail').textContent='';
    }
    refreshButton.textContent=preview?'刷新板端画面':'读取板端检测';
    refreshButton.disabled=reading;
    gammaButton.hidden=!(r?.assets.some(asset=>asset.kind==='before')&&r.assets.some(asset=>asset.kind==='after'));
    adoptButton.hidden=r?.status!=='completed';
    adoptButton.textContent=saving?'正在保存':'采用回执并留证';
    adoptButton.disabled=saving;
    const display=$('board-evidence');
    const auditOpen=display.querySelector('details')?.open??false;
    display.replaceChildren();
    if(!r) return;
    const items=element('ol','','action-checklist');
    for(const [name,value] of [['核对板上模型',`${course.routing.selected==='B'?'预置模型':'本组模型'} SHA-256 已匹配 · ${r.modelSha256.slice(0,12)}…`],
      ['执行 BPU 推理',r.staticBpu?'静态前向已通过':'等待静态前向'],
      ['Gamma 与相机',r.assets.some(asset=>asset.kind==='after')?'原始和调整后实拍均已留证':r.cameraIdentity?'相机已出图，等待后续回读':'等待相机取流'],
      ['保存板端结果',r.frameCount?`已归档 ${r.frameCount} 张连续检测帧`:'等待真实 SDK 帧'],
      ['恢复原配置',r.restoration==='verified'&&r.previewStopped?'回读一致，已停止采流':r.restoration==='no_write'&&r.previewStopped?'未写入 ISP，已停止采流':r.restoration==='unconfirmed'?'恢复待复核':'等待恢复和停流']]) {
      const row=element('li');row.append(element('strong',name+' · '),element('span',value));items.append(row);
    }
    const audit=element('details','','proof-details');
    audit.open=auditOpen;
    audit.append(element('summary','查看上板、取流和恢复回执'),items);
    const counts=Object.entries(r.phases??{}).map(([phase,v])=>`${phase==='before'?'调整前':phase==='after'?'调整后':'实时采流'} ${v.frames} 帧，${v.boxes} 个检测框`);
    if(counts.length) display.append(element('p',counts.join(' ｜ '),'camera-run-state'));
    if(r.failure) display.append(element('p','板端提示 · '+r.failure,'camera-run-state'));
    display.append(audit);
  }
  function poll() {
    if(!lastModel||$('board').hidden||document.hidden) return;
    const current=getReport().nextStep?.stageId;
    if(!watchRequested&&!['deploy','live','preset_deploy'].includes(current)) return;
    if(report?.status==='failed'||report?.status==='completed'&&!pending||issue===errors.board_archive_unconfigured) return;
    void refresh(true);
  }
  return {syncModel,render,poll};
}
