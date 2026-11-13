'use strict';
const vscode=require('vscode'),transport=require('./transport');
function activate(context){
 const output=vscode.window.createOutputChannel('CALF connection');context.subscriptions.push(output);
 const connection=()=>{const c=context.workspaceState.get('calfConnect.connection');if(!c)throw Error('Run CALF: Configure this workspace connection first.');return c;};
 const register=(id,fn)=>context.subscriptions.push(vscode.commands.registerCommand(id,async()=>{try{if(!vscode.workspace.isTrusted)throw Error('Use a trusted workspace.');return await fn();}catch(e){vscode.window.showErrorMessage(String(e.message||e));}}));
 const pick=async(title,folder)=>{const result=await vscode.window.showOpenDialog({title,canSelectFiles:!folder,canSelectFolders:folder,canSelectMany:false});return result?.[0]?.fsPath;};
 register('calfConnect.configure',async()=>{
  if(!vscode.workspace.workspaceFolders?.length)throw Error('Open your project folder first.');
  const core=await pick('Choose the existing CALF native core',false);if(!core)return;
  const home=await pick('Choose the same records folder used by Workbench',true);if(!home)return;
  const workbench=await pick('Choose the Workbench executable (on macOS, inside the app Contents/MacOS folder)',false);if(!workbench)return;
  const c=transport.configure(core,home,workbench);await context.workspaceState.update('calfConnect.connection',c);vscode.window.showInformationMessage('CALF connection saved for this workspace. No task, model or tool was started.');
 });
 register('calfConnect.open',async()=>{await transport.open(connection());vscode.window.showInformationMessage('Workbench launch requested with this records folder.');});
 register('calfConnect.attention',async()=>{const value=await transport.call(connection(),'attention');output.clear();output.appendLine('Native CALF response; this connection does not decide completion or grant authority.');output.appendLine(JSON.stringify(value,null,2));output.show(true);});
 register('calfConnect.copyMcp',async()=>{await vscode.env.clipboard.writeText(JSON.stringify(transport.mcp(connection()),null,2));vscode.window.showInformationMessage('Copied a read-only stdio server entry. Add it through your client’s supported MCP setup; no client setting was changed.');});
 return {transportSchema:'calf.ide-connect.transport.v1',startupActions:0};
}
exports.activate=activate;exports.deactivate=()=>{};
