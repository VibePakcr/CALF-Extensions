"""Generate and explore a local project's structure, relationships and source evidence."""
import argparse
import json
import os
from pathlib import Path
import sys
import webbrowser
from .model import RepositoryError


def default_data():
    if os.environ.get('CALF_REPO_HOME'):return Path(os.environ['CALF_REPO_HOME'])
    if sys.platform=='darwin':return Path.home()/'Library/Application Support/CALF-Repository'
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'CALF-Repository'
    return Path(os.environ.get('XDG_DATA_HOME',str(Path.home()/'.local/share')))/'calf-repository'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ['probe','scan','open']:
        p=sub.add_parser(action);p.add_argument('--repo',type=Path,required=True);p.add_argument('--git',type=Path);p.add_argument('--data-dir',type=Path);p.add_argument('--project-map',type=Path)
        if action=='open':p.add_argument('--no-browser',action='store_true')
    p=sub.add_parser('export');p.add_argument('--data-dir',type=Path,required=True);p.add_argument('--capture',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--include-source',action='store_true')
    args=parser.parse_args()
    try:
        if args.action=='export':
            from .export import export_capture
            result=export_capture(args.data_dir,args.capture,args.output,args.include_source)
        elif args.action=='probe':
            from .git_reader import GitReader
            reader=GitReader(args.repo,args.git);result={'state':'COMPLETE','repository':reader.discover()}
        else:
            from .viewer import Project,PortalServer
            settings={}
            if args.project_map:
                if args.project_map.stat().st_size>65536:raise RepositoryError('MAPPING_LIMIT','Project map settings exceed 64 KiB')
                settings=json.loads(args.project_map.read_text(encoding='utf-8'))
                if not isinstance(settings,dict):raise RepositoryError('INVALID_MAPPING','Project settings must be a JSON object')
            project=Project(args.repo,args.data_dir or default_data(),args.git,settings)
            if args.action=='scan':
                graph=project.refresh();result={'state':project.capture['coverage']['state'],'capture_id':project.capture['capture_id'],'graph_nodes':len(graph['nodes']),'graph_edges':len(graph['edges']),'coverage':graph['coverage']}
            else:
                server=PortalServer(project)
                print(json.dumps({'state':'READY','url':server.origin,'mode':'foreground'},ensure_ascii=True),flush=True)
                try:
                    if not args.no_browser:webbrowser.open(server.origin)
                    server.serve_forever(poll_interval=.1)
                except KeyboardInterrupt:pass
                finally:server.server_close()
                return 0
        print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 3 if result.get('state')=='PARTIAL' else 0
    except RepositoryError as error:
        print(json.dumps({'state':'FAILED','error':error.code,'message':str(error)},ensure_ascii=True),file=sys.stderr);return error.exit_code
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps({'state':'FAILED','error':type(error).__name__,'message':'Unable to access the requested project or data'},ensure_ascii=True),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
