#!/usr/bin/env node
// Emit (do not save) an explicit native-Moss MCP configuration for this installed copy.
import { fileURLToPath, pathToFileURL } from 'node:url';
export function studioConfig(node=process.execPath){
 return {mcpServers:{'rdk-vision-workshop':{transport:'stdio',command:node,args:[fileURLToPath(new URL('./server.mjs',import.meta.url))],...(process.versions.electron?{env:{ELECTRON_RUN_AS_NODE:'1'}}:{}),requestTimeoutMs:30000,permissions:{default:'deny',tools:{vision_course_plan:'readonly',vision_course_stage:'readonly'}}}}};
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)console.log(JSON.stringify(studioConfig(),null,2));
