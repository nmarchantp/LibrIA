"""ETL-01 standalone Google Books ingestion; never returns raw external results."""
import argparse
from app.core.database import SessionLocal
from app.modules.books.router import google_request,store_volume,is_spanish
from app.modules.books.service import consolidate_equivalent_works
from app.modules.analytics.projections import refresh_catalog
from sqlalchemy import text


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--query',action='append',default=[],help='Google Books query; repeat for several queries')
    parser.add_argument('--refresh-known',action='store_true',help='Refresh searches previously registered in LibrIA')
    args=parser.parse_args()
    queries=list(args.query)
    if args.refresh_known:
        with SessionLocal() as db:
            # Stored keys include search mode and policy version.
            for key in db.execute(text('SELECT query FROM app.consultas_catalogo')).scalars():
                parts=key.split(':',2)
                if len(parts)==3:
                    mode,value=parts[1:]
                    queries.append({'author':'inauthor:','isbn':'isbn:'}.get(mode,'')+value)
    if not queries:
        parser.error('Provide --query or --refresh-known')
    total=0
    for query in dict.fromkeys(queries):
        result=google_request(query=query)
        with SessionLocal() as db:
            for item in result.get('items',[]):
                if is_spanish(item.get('volumeInfo',{}).get('language')):
                    store_volume(db,item);total+=1
            db.flush()
            for work in db.execute(text('SELECT work_id FROM analytics.dirty_catalog')).scalars().all():
                if db.execute(text('SELECT 1 FROM app.obras WHERE id=:id'),{'id':work}).first():
                    consolidate_equivalent_works(db,work)
            refresh_catalog(db);db.commit()
    print(f'Catalog ingestion completed: {total} volumes processed')


if __name__=='__main__':
    main()
