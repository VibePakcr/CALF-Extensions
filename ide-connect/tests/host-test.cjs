'use strict';
const assert=require('node:assert/strict');
exports.run=async()=>{
 const vscode=require('vscode'),extension=vscode.extensions.getExtension('vibepakcr.calf-connect');
 // Contributed commands may be registered lazily. Activate via the public
 // extension API or the actual contributed command before checking handlers.
 if(extension){const api=await extension.activate();assert.equal(api.transportSchema,'calf.ide-connect.transport.v1');}
 await vscode.commands.executeCommand('calfConnect.attention');
 const commands=await vscode.commands.getCommands();
 const expected=['configure','open','attention','copyMcp'].map(n=>'calfConnect.'+n);
 const available=commands.filter(n=>n.startsWith('calfConnect.'));
 console.log('CALF_IDE_COMMANDS '+JSON.stringify({app:vscode.env.appName,api:vscode.version,trusted:vscode.workspace.isTrusted,available}));
 for(const id of expected)assert(commands.includes(id),'Missing command '+id);
 console.log('CALF_IDE_ACTIVATION_PASS '+JSON.stringify({vscodeApi:vscode.version,commands:4,reflectionVisible:!!extension,activationRoute:'explicit-activation-then-command',nativeActionsInvoked:0}));
};
