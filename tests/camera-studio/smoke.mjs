import assert from 'node:assert/strict';
import {spawn,spawnSync} from 'node:child_process';
import {readFileSync,existsSync,mkdirSync,mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const source=path.resolve(process.argv[2]);
const id='rdk-camera-workshop';
const manifest=JSON.parse(readFileSync(path.join(source,'plugin.json')));
const root=mkdtempSync(path.join(tmpdir(),'RDK 课堂 '));
const host=process.env.STUDIO_ASAR;
for(const name of ['HOME','USERPROFILE','RDK_STUDIO_HOME','RDK_DATA_DIR','RDK_VISION_COURSE_SESSION_DIR']){
  process.env[name]=path.join(root,name);mkdirSync(process.env[name],{recursive:true});
}
process.env.RDK_CAMERA_WORKSHOP_CONFIG=path.join(root,'unconfigured.json');
let installed=source, map;
if(host){
  const mod=async name=>import(pathToFileURL(path.join(host,'dist-server','server','plugins',name+'.js')).href);
  const registry=await mod('plugin-registry');
  const destination=registry.getUserPluginsDir();
  assert.ok(path.relative(root,destination).split(path.sep)[0]!=='..' && !path.isAbsolute(path.relative(root,destination)));
  const importer=await mod('plugin-import');
  assert.equal(importer.runPluginImport({path:source}).ok,true);
  installed=path.join(destination,id);
  assert.equal(registry.loadPluginRegistry().plugins[id+'@user'].version,manifest.version);
  const runtime=await mod('plugin-mcp-runtime');
  map=runtime.readPluginMcpSnapshot().file.mcpServers;
  console.log('Studio packaged import and tool resolution passed',JSON.parse(readFileSync(path.join(host,'package.json'))).version);
}else{
  map=JSON.parse(readFileSync(path.join(installed,'.mcp.json'))).mcpServers;
}
function rpc(server, requests){
  const cfg=map[server];assert.ok(cfg,server);
  const input=requests.map(([method,params],i)=>JSON.stringify({jsonrpc:'2.0',id:i+1,method,params})).join('\n')+'\n';
  const child=spawnSync(cfg.command,cfg.args,{input,timeout:25000,encoding:'utf8',cwd:cfg.cwd||installed,env:{...process.env,...cfg.env},windowsHide:true});
  assert.ifError(child.error);assert.equal(child.status,0,child.stderr);
  const messages=child.stdout.trim().split(/\r?\n/).map(x=>JSON.parse(x));
  return requests.map((_,i)=>{const msg=messages.find(m=>m.id===i+1);assert.ok(msg?.result && !msg.result.isError,JSON.stringify(msg?.error||msg?.result?.content));return msg.result;});
}
const value=x=>JSON.parse(x.content[0].text);
const call=(name,args={})=>['tools/call',{name,arguments:args}];
const [hello,available,version,status]=rpc(id,[['initialize',{protocolVersion:'2025-06-18'}],['tools/list',{}],call('vision_plugin_version'),call('vision_connection_status')]);
assert.equal(hello.serverInfo.version,manifest.version);
assert.equal(value(version).version,manifest.version);
assert.ok(available.tools.some(t=>t.name==='vision_connection_status'));
assert.equal(value(status).code,'camera_bridge_unconfigured');
const name='rdk-vision-workshop';
const [catalog,plan]=rpc(name,[['tools/list',{}],call('vision_course_plan')]);
assert.equal(catalog.tools.length,10);assert.equal(value(plan).totalMinutes,180);
const launch=()=>value(rpc(name,[call('vision_course_view')])[0]).url;
const url=launch();assert.equal(launch(),url);
const origin=new URL(url).origin,headers={'X-Workshop-Session':new URL(url).hash.slice(1)};
assert.equal(new URL(url).hostname,'127.0.0.1');
const get=async(p,h=headers)=>fetch(new URL(p,origin),{headers:h,signal:AbortSignal.timeout(5000)});
assert.equal((await get('/session',{})).ok,false);
const original=await (await get('/session')).json();assert.ok(original.resume);
assert.match(await (await get('/')).text(),/从相机出图到板端检测/);
if(process.env.TEST_CHROME){
  const browser=spawn(process.env.TEST_CHROME,['--headless=new','--no-first-run','--disable-gpu','--disable-sync','--disable-crash-reporter','--user-data-dir='+path.join(root,'chrome'),'--virtual-time-budget=5000','--dump-dom',url],{stdio:['ignore','pipe','ignore'],windowsHide:true});
  const chunks=[];for await(const chunk of browser.stdout) chunks.push(chunk);
  const doc=Buffer.concat(chunks).toString();assert.match(doc,/<h2 id="step-title">[^<]+<\/h2>/);
  assert.ok(!doc.includes('id="step-title">正在读取本工位进度'));
  console.log('Chrome rendered initialized classroom');
}
console.log('PASS',process.platform,process.arch,manifest.version,'both MCPs, isolated first use, 180-minute plan, workstation reopen');
