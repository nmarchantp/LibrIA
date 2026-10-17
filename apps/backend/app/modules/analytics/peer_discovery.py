"""Aggregated reader affinities; never expose another reader or private text."""
import json
from collections import defaultdict
from datetime import datetime,timezone
from sqlalchemy import text
from app.modules.analytics.etl import ZONE
from app.modules.analytics.insights import MIN_GROUP,MIN_CONTRIBUTORS


def candidate_affinities(owner,readers):
    positives={str(uid):({b['work_id'] for b in p['books'] if not b['archived'] and (b.get('rating') or 0)>=4}
                       if str(uid)==str(owner) else {r['work_id'] for r in p['reviews'] if (r.get('rating') or 0)>=4})
               for uid,p in readers}
    own=positives.get(str(owner),set())
    if not own or len([v for v in positives.values() if v])<MIN_GROUP:
        return []
    peers={uid:works for uid,works in positives.items() if uid!=str(owner) and own.intersection(works)}
    if len(peers)<MIN_CONTRIBUTORS:
        return []
    support=defaultdict(set)
    for uid,works in peers.items():
        for work in works-own:
            support[work].add(uid)
    return sorted(work for work,people in support.items() if len(people)>=MIN_CONTRIBUTORS)


def peer_candidates(db,owner):
    day=datetime.now(timezone.utc).astimezone(ZONE).date()
    params={'owner':owner,'day':day}
    cached=db.execute(text('SELECT payload FROM analytics.peer_releases WHERE owner_id=:owner AND release_date=:day'),params).scalar()
    if cached is not None:
        return cached
    rows=db.execute(text('''SELECT c.owner_id,r.payload FROM analytics.reader_current c
      JOIN analytics.projection_runs r ON r.id=c.run_id''')).all()
    payload=candidate_affinities(owner,rows)
    db.execute(text('''INSERT INTO analytics.peer_releases(owner_id,release_date,payload,source_run_ids)
      VALUES(:owner,:day,CAST(:payload AS jsonb),ARRAY(SELECT run_id FROM analytics.reader_current))
      ON CONFLICT DO NOTHING'''),{**params,'payload':json.dumps(payload)})
    return db.execute(text('SELECT payload FROM analytics.peer_releases WHERE owner_id=:owner AND release_date=:day'),params).scalar_one()
