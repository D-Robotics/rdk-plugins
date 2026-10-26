#!/usr/bin/env node
// Read-only course planner: no network, process execution, hardware or writes.
import { readFileSync } from 'node:fs';
import { createInterface } from 'node:readline';
import { pathToFileURL } from 'node:url';
const plan = JSON.parse(readFileSync(new URL('../skills/rdk-vision-workshop/assets/course-plan.json', import.meta.url), 'utf8'));
plan.guideMarkdown = readFileSync(new URL('../skills/rdk-vision-workshop/references/course-runbook.md', import.meta.url), 'utf8');
plan.tuningHandoffMarkdown = readFileSync(new URL('../skills/rdk-vision-workshop/references/tuning-handoff.md', import.meta.url), 'utf8');
const tools = [
  { name:'vision_course_plan', description:'读取四小时视觉Workshop时间、阶段与证据清单。只读课程资料，不探测设备或宣称执行通过。', inputSchema:{type:'object',properties:{},additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false}},
  { name:'vision_course_stage', description:'读取指定课程阶段的方法、时间预算与退出证据；不操作相机/GPU/BPU。',inputSchema:{type:'object',properties:{stageId:{type:'string',enum:plan.schedule.map(s=>s.id)}},required:['stageId'],additionalProperties:false},annotations:{readOnlyHint:true,destructiveHint:false,idempotentHint:true,openWorldHint:false}}
];
const result = data => ({content:[{type:'text',text:JSON.stringify(data)}],isError:false});
function args(value, keys) {
 if(!value || typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!keys.includes(k)))throw new Error('invalid_arguments');
 return value;
}
export function dispatch(req){
 if(!req || req.jsonrpc!=='2.0'||typeof req.method!=='string')return {jsonrpc:'2.0',id:req?.id??null,error:{code:-32600,message:'Invalid request'}};
 if(req.id===undefined)return null;
 try{
 let out;
 if(req.method==='initialize')out={protocolVersion:'2024-11-05',capabilities:{tools:{listChanged:false}},serverInfo:{name:'rdk-vision-workshop',version:'1.3.0'}};
 else if(req.method==='ping')out={};
 else if(req.method==='tools/list')out={tools};
 else if(req.method==='tools/call'){
 const a=args(req.params?.arguments??{},req.params?.name==='vision_course_stage'?['stageId']:[]);
 if(req.params?.name==='vision_course_plan')out=result(plan);
 else if(req.params?.name==='vision_course_stage'){
 const stage=plan.schedule.find(s=>s.id===a.stageId);if(!stage)throw new Error('unknown_stage');
 out=result({schema:plan.schema,executionStatus:'planning_only',stage,limitations:plan.limitations});
 }else throw new Error('unknown_tool');
 }else return {jsonrpc:'2.0',id:req.id,error:{code:-32601,message:'Method not found'}};
 return {jsonrpc:'2.0',id:req.id,result:out};
 }catch(e){return {jsonrpc:'2.0',id:req.id,result:{content:[{type:'text',text:JSON.stringify({error:e.message,executionStatus:'not_executed'})}],isError:true}};}
}
if(process.argv[1] && import.meta.url===pathToFileURL(process.argv[1]).href){
 const rl=createInterface({input:process.stdin,crlfDelay:Infinity});
 rl.on('line',line=>{let out;try{out=dispatch(JSON.parse(line))}catch{out={jsonrpc:'2.0',id:null,error:{code:-32700,message:'Parse error'}}}if(out)process.stdout.write(JSON.stringify(out)+'\n')});
}
