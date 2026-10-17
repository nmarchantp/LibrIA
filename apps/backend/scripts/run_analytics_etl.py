"""Run incremental projections or explicitly reconstruct them from current sources."""
import argparse
import time
from app.core.database import SessionLocal
from app.modules.analytics.projections import refresh_pending


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--rebuild',action='store_true',help='Reconstruct current analytical projections, preserving historical runs')
    parser.add_argument('--watch',action='store_true',help='Process affected readers/catalog every five seconds')
    args=parser.parse_args()
    rebuild=args.rebuild
    while True:
        with SessionLocal() as db:
            count=refresh_pending(db,rebuild=rebuild)
            db.commit()
        print(f'ETL completed: {count} reader projections checked',flush=True)
        rebuild=False
        if not args.watch:
            break
        time.sleep(5)


if __name__=='__main__':
    main()
