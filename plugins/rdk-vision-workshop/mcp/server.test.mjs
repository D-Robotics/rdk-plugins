import test from 'node:test';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { dispatch } from './server.mjs';
let id=0;
const rpc=(name,a={})=>dispatch({jsonrpc:'2.0',id:++id,method:'tools/call',params:{name,arguments:a}});
test('course is contiguous 240 minutes with break included and no execution claim',()=>{
 const p=JSON.parse(rpc('vision_course_plan').result.content[0].text);
 assert.equal(p.executionStatus,'planning_only');assert.equal(p.schedule[0].start,0);assert.equal(p.schedule.at(-1).end,240);
 assert.equal(p.schedule.reduce((n,s)=>n+s.minutes,0),240);
 p.schedule.forEach((s,i)=>{if(i)assert.equal(s.start,p.schedule[i-1].end);assert.equal(s.executionStatus,'not_executed');assert.ok(s.requiredEvidence.length)});
 assert.equal(p.break.endMinute-p.break.startMinute,10);assert.equal(p.break.includedInTrainingBlock,true);
});
test('reject unrecognized stage, extra fields and supplied success flags',()=>{
 for(const [name,a] of [['vision_course_stage',{stageId:'unknown'}],['vision_course_plan',{passed:true}],['vision_course_stage',{stageId:'live',executionStatus:'passed'}],['vision_course_stage',[]]])assert.equal(rpc(name,a).result.isError,true);
 const s=JSON.parse(rpc('vision_course_stage',{stageId:'live'}).result.content[0].text);assert.ok(s.stage.requiredEvidence.includes('tuning_in_detection_pipeline'));
});
test('real stdio start from a directory with spaces, list/call and notification',async()=>{
 const c=spawn(process.execPath,[fileURLToPath(new URL('./server.mjs',import.meta.url))],{stdio:['pipe','pipe','pipe']});
 let out='',err='';c.stdout.on('data',x=>out+=x);c.stderr.on('data',x=>err+=x);
 c.stdin.end([{jsonrpc:'2.0',id:1,method:'initialize',params:{}},{jsonrpc:'2.0',method:'notifications/initialized'},{jsonrpc:'2.0',id:2,method:'tools/list'},{jsonrpc:'2.0',id:3,method:'tools/call',params:{name:'vision_course_plan',arguments:{}}}].map(JSON.stringify).join('\n')+'\n');
 const code=await new Promise(resolve=>c.on('close',resolve));assert.equal(code,0,err);const rows=out.trim().split('\n').map(JSON.parse);assert.equal(rows.length,3);assert.equal(rows[1].result.tools.length,2);assert.equal(JSON.parse(rows[2].result.content[0].text).totalMinutes,240);
});
