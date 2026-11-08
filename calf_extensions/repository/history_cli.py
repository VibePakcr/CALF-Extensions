"""Local, on-demand CALF history index and module Markdown queries."""
import argparse
import json
from pathlib import Path
import sys
from .history_index import build, HistoryView
from .model import RepositoryError

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('build');p.add_argument('--history',type=Path,required=True);p.add_argument('--modules',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--calf',type=Path)
    for name in ['modules','module','search','record','status']:
        p=sub.add_parser(name);p.add_argument('--index',type=Path,required=True);p.add_argument('--verify-source',action='store_true')
        if name=='module':p.add_argument('--module',required=True);p.add_argument('--related',action='store_true');p.add_argument('--json',action='store_true')
        if name=='record':p.add_argument('--seq',required=True,type=int)
        if name=='search':p.add_argument('--module',required=True);p.add_argument('--query',default='');p.add_argument('--kind');p.add_argument('--before',type=int);p.add_argument('--limit',type=int,default=20)
        if name=='status':p.add_argument('--calf',type=Path,required=True);p.add_argument('--task',required=True)
    args=parser.parse_args(argv)
    try:
        if args.action=='build':result=build(args.history,args.modules,args.output,args.calf)
        else:
            view=HistoryView(args.index,args.verify_source)
            if args.action=='modules':result=view.listing()
            elif args.action=='module':result=view.module(args.module,args.related)
            elif args.action=='record':result=view.record(args.seq)
            elif args.action=='search':result=view.search(args.module,args.query,args.kind,args.before,args.limit)
            else:result=view.status(args.calf,args.task)
        if args.action=='module' and not args.json:
            print('\n'.join(d['markdown'] for d in result['documents']))
        else:print(json.dumps(result,ensure_ascii=False,allow_nan=False))
        return 0
    except RepositoryError as error:
        print(json.dumps({'state':'FAILED','error':error.code,'message':str(error)},ensure_ascii=False),file=sys.stderr);return 1
    except (OSError,ValueError,TypeError,KeyError,IndexError,RecursionError):
        print(json.dumps({'state':'FAILED','error':'HISTORY_VIEW_UNAVAILABLE','message':'Inspect the source and build a new index; existing data was not overwritten.'}),file=sys.stderr);return 1

if __name__=='__main__':raise SystemExit(main())
