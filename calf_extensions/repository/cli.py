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


def main(installation=None,manual_root=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    for action in ['probe','scan','open']:
        p=sub.add_parser(action);selection=p.add_mutually_exclusive_group(required=True);selection.add_argument('--repo',type=Path);
        selection.add_argument('--source')
        if action=='open':
            selection.add_argument('--view');selection.add_argument('--sources',action='store_true',help='open an empty manual source-selection workspace')
        if action in ['scan','open']:
            p.add_argument('--ref-kind',choices=['branch','tag','commit']);p.add_argument('--ref');p.add_argument('--left-kind',choices=['branch','tag','commit']);p.add_argument('--left-ref')
        p.add_argument('--git',type=Path);p.add_argument('--data-dir',type=Path);p.add_argument('--project-map',type=Path)
        if action=='open':p.add_argument('--no-browser',action='store_true')
    p=sub.add_parser('export');p.add_argument('--data-dir',type=Path,required=True);group=p.add_mutually_exclusive_group(required=True);group.add_argument('--capture');group.add_argument('--view');p.add_argument('--output',type=Path,required=True);p.add_argument('--include-source',action='store_true');p.add_argument('--include-origin',action='store_true')
    sources=sub.add_parser('sources');actions=sources.add_subparsers(dest='source_action',required=True)
    for action in ['add','list','remove','check']:
        p=actions.add_parser(action);p.add_argument('--data-dir',type=Path)
        if action=='add':p.add_argument('--provider',choices=['github','gitlab'],required=True);p.add_argument('--url',required=True);p.add_argument('--credential-env')
        if action in ['remove','check']:p.add_argument('source_id')
    args=parser.parse_args()
    try:
        if args.action=='sources' or args.action=='probe' and args.source:
            from .hosted import HostedServices
            services=HostedServices(args.data_dir or default_data())
            try:
                action=args.source_action if args.action=='sources' else 'check'
                if action=='add':result=services.registry.add(args.provider,args.url,args.credential_env).public()
                elif action=='list':result={'sources':[v.public() for v in services.registry.list()]}
                elif action=='remove':result=services.registry.remove(args.source_id).public()
                else:
                    identity=args.source_id if args.action=='sources' else args.source
                    job=services.probe(identity)
                    try:result=services.wait(job['id'])
                    except KeyboardInterrupt:
                        services.cancel(job['id']);services.wait(job['id'],12);raise
                    print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 0 if result['state']=='SUCCEEDED' else 130 if result['state'] in {'CANCELLED','SUPERSEDED'} else 1
                print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 0
            finally:services.close()
        if args.action=='export':
            if args.view:
                from .offline import export_view
                result=export_view(args.data_dir,args.view,args.output,args.include_source,args.include_origin)
            else:
                if args.include_origin:raise RepositoryError('INVALID_EXPORT_OPTIONS','Origin projection is a v2 view export option')
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
            if (args.ref_kind is None)!=(args.ref is None) or (args.left_kind is None)!=(args.left_ref is None):raise RepositoryError('INVALID_REF','Provide both typed ref kind and name')
            if not args.source and any([args.ref_kind,args.ref,args.left_kind,args.left_ref]):raise RepositoryError('INVALID_REF','Hosted ref options require --source')
            project=Project(args.repo,args.data_dir or default_data(),args.git,settings) if args.repo else None
            if args.action=='scan':
                if args.source:
                    from .navigation import NavigationHub
                    if args.ref_kind is None:raise RepositoryError('INVALID_REF','Scan --source requires an explicit typed ref')
                    hub=NavigationHub(args.data_dir or default_data(),settings=settings)
                    try:
                        job=hub.collect(args.source,args.ref_kind,args.ref,args.left_kind,args.left_ref)
                        try:job=hub.wait(job['id'])
                        except KeyboardInterrupt:hub.cancel(job['id']);hub.wait(job['id'],12);raise
                        if job['state'] not in {'SUCCEEDED','SAVED_PARTIAL'}:raise RepositoryError(job['error']['code'] if job.get('error') else 'CANCELLED','Hosted collection did not complete')
                        result=dict(job['result'],state='COMPLETE' if job['state']=='SUCCEEDED' else 'PARTIAL',job_state=job['state'])
                    finally:hub.close();hub.hosted.close()
                else:
                    graph=project.refresh();result={'state':project.capture['coverage']['state'],'capture_id':project.capture['capture_id'],'graph_nodes':len(graph['nodes']),'graph_edges':len(graph['edges']),'coverage':graph['coverage']}
            else:
                server=PortalServer(project,data_dir=args.data_dir or default_data(),settings=settings,installation=installation,manual_root=manual_root)
                try:
                    if args.view:server.navigation.select(context=args.view)
                    elif args.source:
                        server.navigation.select(source=args.source)
                        if args.ref_kind is not None:server.initial_job=server.navigation.collect(args.source,args.ref_kind,args.ref,args.left_kind,args.left_ref)['id']
                    print(json.dumps({'state':'READY','url':server.origin,'mode':'foreground'},ensure_ascii=True),flush=True)
                    if not args.no_browser:webbrowser.open(server.origin)
                    server.serve_forever(poll_interval=.1)
                except KeyboardInterrupt:pass
                finally:server.server_close()
                return 0
        print(json.dumps(result,ensure_ascii=True,allow_nan=False));return 3 if result.get('state')=='PARTIAL' else 0
    except KeyboardInterrupt:
        print(json.dumps({'state':'CANCELLED'}));return 130
    except RepositoryError as error:
        print(json.dumps({'state':'FAILED','error':error.code,'message':str(error)},ensure_ascii=True),file=sys.stderr);return error.exit_code
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps({'state':'FAILED','error':type(error).__name__,'message':'Unable to access the requested project or data'},ensure_ascii=True),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
