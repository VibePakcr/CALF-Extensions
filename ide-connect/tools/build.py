"""Build local unsigned connector artifacts using existing host tools only."""
from pathlib import Path
import json,os,re,shutil,subprocess,zipfile,hashlib
source=Path(__file__).resolve().parents[1];out=Path(os.environ['VIBEPACKR_T9_BUILD'])/('output/ide-connect-0.1.0-dev.1'+os.environ.get('CALF_IDE_BUILD_LABEL',''));out.mkdir(exist_ok=False)
core=Path(os.environ['CALF_IDE_TEST_CORE']).resolve(strict=True);report={'status':'FAIL','version':'0.1.0-dev.1','installed':False,'published':False,'modelCalls':0}
def call(args,env=None):
 p=subprocess.run(list(map(str,args)),capture_output=True,text=True,encoding='utf-8',env=env or os.environ)
 print(p.stdout);print(p.stderr);assert p.returncode==0,(list(map(str,args)),p.returncode);return p.stdout
try:
 descriptor=(source/'common/contract.json').read_bytes()
 assert descriptor==(source/'vscode/contract.json').read_bytes()==(source/'jetbrains/resources/calf-connect-contract.json').read_bytes()
 env=dict(os.environ,CALF_IDE_SOURCE=str(source),CALF_IDE_TEST_CORE=str(core))
 text=call(['node','--test',source/'tests/transport.test.cjs'],env);assert re.search(r'tests\s+6',text)and re.search(r'fail\s+0',text);report['nodeTransportTests']=6
 lib=Path('/Applications/PyCharm.app/Contents/lib');java=Path('/Applications/PyCharm.app/Contents/jbr/Contents/Home/bin');classes=out/'classes';classes.mkdir()
 jars=list(lib.glob('*.jar'));classpath=os.pathsep.join(map(str,jars))
 call([java/'javac','-encoding','UTF-8','--release','17','-classpath',classpath,'-d',classes,*sorted((source/'jetbrains/src').rglob('*.java'))])
 for path in(source/'jetbrains/resources').rglob('*'):
  if path.is_file():target=classes/path.relative_to(source/'jetbrains/resources');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
 testclasses=out/'test-classes';testclasses.mkdir()
 call([java/'javac','-encoding','UTF-8','--release','17','-classpath',str(classes)+os.pathsep+classpath,'-d',testclasses,source/'tests/TransportProbe.java'])
 text=call([java/'java','-classpath',os.pathsep.join([str(testclasses),str(classes),str(lib/'intellij.libraries.gson.jar')]),'com.vibepakcr.calf.TransportProbe',core,out/'java-records']);report['javaTransportProbe']=json.loads(text.strip())
 vsix=out/'CALF-Connect-0.1.0-dev.1.vsix'
 xml='<?xml version="1.0" encoding="utf-8"?><PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011"><Metadata><Identity Language="en-US" Id="calf-connect" Version="0.1.0-dev.1" Publisher="vibepakcr"/><DisplayName>CALF Connect</DisplayName><Description xml:space="preserve">Open CALF Workbench and read native attention.</Description><Tags>calf,workbench</Tags><Categories>Other</Categories><GalleryFlags>Preview</GalleryFlags><Properties><Property Id="Microsoft.VisualStudio.Code.Engine" Value="^1.90.0"/></Properties></Metadata><Installation><InstallationTarget Id="Microsoft.VisualStudio.Code"/></Installation><Dependencies/><Assets><Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/></Assets></PackageManifest>'
 with zipfile.ZipFile(vsix,'x',compression=zipfile.ZIP_DEFLATED)as z:
  z.writestr('extension.vsixmanifest',xml);z.writestr('[Content_Types].xml','<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="json" ContentType="application/json"/><Default Extension="js" ContentType="application/javascript"/><Default Extension="xml" ContentType="text/xml"/><Default Extension="md" ContentType="text/markdown"/><Default Extension="txt" ContentType="text/plain"/><Default Extension="png" ContentType="image/png"/></Types>')
  for path in[source/'README.md',source/'README_KR.md',source/'INSTALL.md',source/'INSTALL_KR.md',source/'MANUAL.md',source/'MANUAL_KR.md',source/'LICENSE.txt',source/'QUALIFICATION.json']:
   z.write(path,'extension/'+path.name)
  for path in(source/'docs').rglob('*'):
   if path.is_file():z.write(path,'extension/'+path.relative_to(source).as_posix())
  for path in(source/'vscode').iterdir():
   if path.is_file():z.write(path,'extension/'+path.name)
 pluginjar=out/'calf-connect.jar'
 with zipfile.ZipFile(pluginjar,'x',compression=zipfile.ZIP_DEFLATED)as z:
  for path in classes.rglob('*'):
   if path.is_file():z.write(path,path.relative_to(classes).as_posix())
 pluginzip=out/'CALF-Connect-0.1.0-dev.1-pycharm.zip'
 with zipfile.ZipFile(pluginzip,'x',compression=zipfile.ZIP_DEFLATED)as z:
  z.write(pluginjar,'calf-connect/lib/calf-connect.jar')
  for path in[source/'README.md',source/'README_KR.md',source/'INSTALL.md',source/'INSTALL_KR.md',source/'MANUAL.md',source/'MANUAL_KR.md',source/'LICENSE.txt',source/'QUALIFICATION.json']:z.write(path,'calf-connect/'+path.name)
  for path in(source/'docs').rglob('*'):
   if path.is_file():z.write(path,'calf-connect/'+path.relative_to(source).as_posix())
 report.update(status='PASS',sourcePins={p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()},sharedTransportSha256=hashlib.sha256(descriptor).hexdigest(),coreSha256=hashlib.sha256(core.read_bytes()).hexdigest(),artifacts={p.name:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size}for p in[vsix,pluginzip]},limits=['Local unsigned development artifacts; no marketplace publication or IDE installation','Java adapter compiled against installed PyCharm 2026.3 build 263.7307.206; other JetBrains products not runtime-qualified','VS Code, Cursor and Antigravity host activation requires separately recorded proof; compilation is not activation','Native protocol qualification is separate from GUI quality and human acceptance'])
finally:
 (out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
