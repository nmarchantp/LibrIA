"""ETL-04 indicators from analytics projections, with bounded daily releases."""
import json
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from sqlalchemy import text
from app.modules.analytics.insights import MIN_GROUP,MIN_CONTRIBUTORS,round_count
from app.modules.analytics.etl import ZONE

DEFINITIONS={
 'IND-001':('Obras más leídas','lectores únicos','Una finalización por lector y obra en el período.'),
 'IND-002':('Obras más abandonadas','lectores únicos','Un abandono por lector y obra en el período; no implica rechazo.'),
 'IND-003':('Tasa de abandono a 30 días','porcentaje','Inicios entre 60 y 30 días antes del corte; primer desenlace dentro de sus primeros 30 días. Abandonos / (finales + abandonos), un intento por lector y obra.'),
 'IND-004':('Géneros más leídos','porcentaje','Finalizaciones por lector y obra; peso 1/n entre sus n categorías normalizadas. Porcentajes sobre conteos ponderados redondeados de categorías publicables.'),
 'IND-005':('Géneros emergentes','puntos porcentuales','Cambio de participación ponderada frente a los 30 días anteriores; solo categorías publicables en ambos períodos.'),
 'IND-006':('Obras mejor valoradas','estrellas sobre 5','Última reseña pública vigente por lector y obra al corte, mínimo cinco lectores. Media redondeada a medio punto.'),
 'IND-007':('Autores con mayor seguimiento','seguidores únicos','Seguimientos vigentes a perfiles con capacidad de autor al corte; no implican gusto por sus libros.'),
 'IND-008':('Obras con mayor interacción','interacciones','Comentarios y reacciones del período asociados sin ambigüedad a una obra; máximo diez por lector y obra.'),
 'IND-009':('Actividad lectora','eventos','Inicios y finales del período; máximo diez eventos por lector y tipo.'),
 'IND-010':('Tendencias de la comunidad','variación de eventos','Diferencia de lecturas iniciadas, finalizadas, reseñas públicas y comentarios/reacciones entre dos períodos de 30 días, con límites por lector.'),
}


def instant(value):
    return datetime.fromisoformat(value.replace('Z','+00:00'))


def build_indicators(readers,catalog,cutoff):
    start=cutoff-timedelta(days=30);previous=start-timedelta(days=30)
    participants={owner for owner,p in readers if any(
        e.get('at') and previous<=instant(e['at'])<cutoff
        for e in p['events']+p['reviews']+p['social'])}
    base={'status':'ready' if len(participants)>=MIN_GROUP else 'insufficient_group',
          'period':{'start':start.isoformat(),'cutoff':cutoff.isoformat(),'previous_start':previous.isoformat()},
          'minimum_participants':MIN_GROUP,'minimum_contributors':MIN_CONTRIBUTORS,
          'limitations':['Conteos redondeados a múltiplos de cinco; se suprimen grupos pequeños.',
            'Las tendencias reflejan actividad registrada, no ventas ni gustos individuales.',
            'Las reseñas y los seguimientos reflejan el estado vigente al extraer; no reconstruyen eliminaciones pasadas.',
            'La distribución de géneros se limita a categorías publicables; no representa etiquetas suprimidas.'],
          'indicators':[]}
    if base['status']!='ready':
        return base
    finished=defaultdict(set);abandoned=defaultdict(set);ratings=defaultdict(dict)
    followers=defaultdict(set);profile_names={};interaction=defaultdict(lambda:defaultdict(int))
    genre=[defaultdict(float),defaultdict(float)];genre_people=[defaultdict(set),defaultdict(set)]
    activity=[defaultdict(lambda:defaultdict(int)),defaultdict(lambda:defaultdict(int))]
    cohorts=defaultdict(dict)
    def title(work):
        return catalog.get(work,{}).get('title','Obra sin metadatos disponibles')
    for owner,p in readers:
        events=p['events']
        completed=[set(),set()]
        for e in events:
            at=instant(e['at']);work=e['work_id'];kind=e['kind']
            index=0 if start<=at<cutoff else 1 if previous<=at<start else None
            if index is not None and kind in ('start','finish'):
                activity[index][kind][owner]+=1
            if index==0 and kind in ('finish','abandon'):
                (finished if kind=='finish' else abandoned)[work].add(owner)
            if index is not None and kind=='finish':
                completed[index].add(work)
            if kind=='start' and previous<=at<start:
                outcomes=[o for o in events if o['reading_id']==e['reading_id'] and o['kind'] in ('finish','abandon')
                          and at<=instant(o['at'])<min(at+timedelta(days=30),cutoff)]
                if outcomes and owner not in cohorts[work]:
                    cohorts[work][owner]=min(outcomes,key=lambda o:o['at'])['kind']
        for i in (0,1):
            for work in completed[i]:
                categories=list(dict.fromkeys(str(v).strip().casefold() for v in catalog.get(work,{}).get('categories',[]) if str(v).strip())) or ['sin categoría']
                for category in categories:
                    genre[i][category]+=1/len(categories);genre_people[i][category].add(owner)
        for r in p['reviews']:
            if r['at'] and instant(r['at'])<cutoff and r['rating'] is not None:
                ratings[r['work_id']][owner]=r['rating']
            if r['at']:
                at=instant(r['at']);index=0 if start<=at<cutoff else 1 if previous<=at<start else None
                if index is not None:
                    activity[index]['reviews'][owner]+=1
        for s in p['social']:
            at=instant(s['at'])
            if s['kind']=='follow' and s.get('is_author') and at<cutoff:
                followers[s['profile_id']].add(owner)
                profile_names[s['profile_id']]=s.get('display_name','Perfil de autor')
            if s['kind']!='follow':
                index=0 if start<=at<cutoff else 1 if previous<=at<start else None
                if index is not None:
                    activity[index]['interactions'][owner]+=1
                    if index==0 and s.get('work_id'):
                        interaction[s['work_id']][owner]+=1
    def ranked(groups):
        return sorted([{'work_id':w,'title':title(w),'value':round_count(len(people))} for w,people in groups.items()
                       if len(people)>=MIN_CONTRIBUTORS],key=lambda r:(-r['value'],r['title']))[:10]
    values={'IND-001':ranked(finished),'IND-002':ranked(abandoned)}
    values['IND-003']=[]
    for work,outcomes in cohorts.items():
        a=sum(v=='abandon' for v in outcomes.values());f=sum(v=='finish' for v in outcomes.values())
        if a>=MIN_CONTRIBUTORS and f>=MIN_CONTRIBUTORS:
            ar,fr=round_count(a),round_count(f)
            values['IND-003'].append({'work_id':work,'title':title(work),'value':round(100*ar/(ar+fr),1)})
    shares=[]
    for i in (0,1):
        public={g:round_count(v) for g,v in genre[i].items() if len(genre_people[i][g])>=MIN_CONTRIBUTORS and round_count(v)>0}
        total=sum(public.values())
        shares.append({g:round(100*v/total,1) for g,v in public.items()} if total else {})
    values['IND-004']=[{'title':g,'value':v} for g,v in sorted(shares[0].items(),key=lambda r:-r[1])]
    values['IND-005']=[{'title':g,'value':round(v-shares[1][g],1)} for g,v in shares[0].items() if g in shares[1]]
    values['IND-006']=sorted([{'work_id':w,'title':title(w),'value':int((sum(rs.values())/len(rs))*2+.5)/2,'contributors':round_count(len(rs))}
                            for w,rs in ratings.items() if len(rs)>=MIN_CONTRIBUTORS],key=lambda r:(-r['value'],r['title']))[:10]
    values['IND-007']=sorted([{'profile_id':p,'title':profile_names[p],'value':round_count(len(people))} for p,people in followers.items() if len(people)>=MIN_CONTRIBUTORS],key=lambda r:-r['value'])[:10]
    values['IND-008']=sorted([{'work_id':w,'title':title(w),'value':round_count(sum(min(v,10) for v in people.values()))} for w,people in interaction.items()
                            if len(people)>=MIN_CONTRIBUTORS],key=lambda r:-r['value'])[:10]
    names={'start':'Lecturas iniciadas','finish':'Lecturas terminadas','reviews':'Reseñas publicadas','interactions':'Comentarios y reacciones'}
    values['IND-009']=[];values['IND-010']=[]
    for kind,label in names.items():
        numbers=[]
        for period in activity:
            people=period[kind]
            numbers.append(round_count(sum(min(v,10) for v in people.values())) if len(people)>=MIN_CONTRIBUTORS else None)
        if kind in ('start','finish') and numbers[0] is not None:
            values['IND-009'].append({'title':label,'value':numbers[0]})
        if None not in numbers:
            values['IND-010'].append({'title':label,'value':numbers[0]-numbers[1],'current':numbers[0],'previous':numbers[1]})
    base['indicators']=[{'id':code,'label':label,'unit':unit,'definition':definition,'items':values[code],
                         'status':'ready' if values[code] else 'insufficient_data'} for code,(label,unit,definition) in DEFINITIONS.items()]
    return base


def community_release(db):
    day=datetime.now(timezone.utc).astimezone(ZONE).date()
    cached=db.execute(text('SELECT payload FROM analytics.community_releases WHERE release_date=:day'),{'day':day}).scalar()
    if cached is not None:
        return cached
    from app.modules.analytics.projections import refresh_pending
    refresh_pending(db)
    rows=db.execute(text('''SELECT c.owner_id,r.payload FROM analytics.reader_current c
      JOIN analytics.projection_runs r ON r.id=c.run_id''')).all()
    catalog={str(r['work_id']):{'title':r['payload']['editions'][0]['metadata']['title'],'categories':r['payload']['categories']}
             for r in db.execute(text('SELECT * FROM analytics.catalog_current')).mappings()}
    cutoff=datetime.combine(day,datetime.min.time(),ZONE).astimezone(timezone.utc)
    payload=build_indicators(rows,catalog,cutoff)
    # Do not cache an empty/small cohort; later ETL additions can make it eligible.
    if payload['status']=='ready':
        db.execute(text('''INSERT INTO analytics.community_releases(release_date,payload,source_run_ids)
          VALUES(:day,CAST(:payload AS jsonb),ARRAY(SELECT run_id FROM analytics.reader_current))
          ON CONFLICT DO NOTHING'''),{'day':day,'payload':json.dumps(payload)})
        payload=db.execute(text('SELECT payload FROM analytics.community_releases WHERE release_date=:day'),{'day':day}).scalar_one()
    db.commit()
    return payload
