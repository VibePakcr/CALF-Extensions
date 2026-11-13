'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),vm=require('node:vm');
const root=process.env.CALF_IDE_SOURCE,core=process.env.CALF_IDE_TEST_CORE;if(!root||!core)throw Error('Select the isolated source and core.');
const T=require(path.join(root,'vscode/transport.js'));
const temp=fs.mkdtempSync(path.join(os.tmpdir(),"calf-ide-'한글-"));test.after(()=>fs.rmSync(temp,{recursive:true,force:true}));
const home=path.join(temp,'records $(literal)');fs.mkdirSync(home);const c=T.configure(core,home,core);
test('one shared descriptor keeps caller paths literal and contains no execution-control flag',()=>{
 assert.deepEqual(T.request('attention',{home:"/literal/한글 ' $(text)"}),{args:['api'],input:{op:'attention',home:"/literal/한글 ' $(text)"}});
 assert.deepEqual(T.mcp(c),{command:core,args:['work-mcp',home]});assert.throws(()=>T.request('run',c));
});
test('new connection requires explicit absolute files and existing records',()=>{
 assert.throws(()=>T.configure('relative',home,core));assert.throws(()=>T.configure(core,path.join(temp,'missing'),core));assert.equal(fs.existsSync(path.join(temp,'missing')),false);
});
test('actual native attention stays a read-only projection and leaves the selected home empty',async()=>{
 const result=await T.call(c,'attention');assert.equal(result.schema,'calf.attention.v1');assert.equal(result.readOnly,true);assert.equal(result.completionEvaluated,false);assert.equal(result.coverage.wholeProject,false);assert.deepEqual(fs.readdirSync(home),[]);
});
test('changed executable identity is refused before another call; original binary stays unchanged',async()=>{
 const copy=path.join(temp,'copy');fs.copyFileSync(core,copy);fs.chmodSync(copy,0o700);const changed=T.configure(copy,home,core);fs.appendFileSync(copy,'changed');
 await assert.rejects(async()=>T.call(changed,'attention'),/identity changed/);assert.deepEqual(fs.readdirSync(home),[]);
});
test('activation registers four commands; an unconfigured read stops before native transport',async()=>{
 const commands=[],writes=[],calls=[],errors=[];const fakeTransport={configure(){calls.push('configure');},call(){calls.push('call');},open(){calls.push('open');},mcp(){calls.push('mcp');}};
 const vscode={window:{showErrorMessage(text){errors.push(text);},createOutputChannel(){return{dispose(){}};}},commands:{registerCommand(id,fn){commands.push({id,fn});return{dispose(){}};}},workspace:{isTrusted:true},env:{}};
 const module={exports:{}};const exports=module.exports;vm.runInNewContext(fs.readFileSync(path.join(root,'vscode/extension.js'),'utf8'),{require:n=>n==='vscode'?vscode:fakeTransport,module,exports});
 const api=exports.activate({subscriptions:[],workspaceState:{get(){calls.push('read');},update(){writes.push('write');}}});assert.equal(api.startupActions,0);assert.equal(commands.length,4);assert.deepEqual(calls,[]);assert.deepEqual(writes,[]);
 await commands.find(v=>v.id==='calfConnect.attention').fn();assert.deepEqual(calls,['read']);assert.equal(errors.length,1);assert.match(errors[0],/Configure this workspace connection first/);assert.deepEqual(writes,[]);
});
test('opening the Workbench uses an argument array and only a records-home override',async()=>{
 const cp=require('node:child_process'),old=cp.spawn;let invocation;cp.spawn=(exe,args,opts)=>{invocation={exe,args,opts};const events={once(name,fn){if(name==='spawn')queueMicrotask(fn);return events;},unref(){}};return events;};
 try{await T.open(c);assert.equal(invocation.exe,core);assert.deepEqual(invocation.args,[]);assert.equal(invocation.opts.env.CALF_WORK_HOME,home);assert.equal(invocation.opts.shell,undefined);}finally{cp.spawn=old;}
});
