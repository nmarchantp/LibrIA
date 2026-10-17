import unittest
from datetime import datetime,timedelta,timezone
from app.modules.analytics.community import build_indicators


class CommunityIndicatorsTest(unittest.TestCase):
    cutoff=datetime(2026,10,16,tzinfo=timezone.utc)

    def readers(self,n=10):
        rows=[]
        for i in range(n):
            def event(kind,days,reading):
                return {'source_id':f'{kind}-{i}-{days}','reading_id':reading,'work_id':'work','kind':kind,
                        'at':(self.cutoff-timedelta(days=days)).isoformat()}
            rows.append((str(i),{'events':[event('start',40,'cohort'),event('abandon' if i<5 else 'finish',20,'cohort'),
                event('start',10,'current'),event('finish',2,'current'),event('finish',3,'repeat')],
                'reviews':[{'work_id':'work','rating':4,'at':(self.cutoff-timedelta(days=2)).isoformat()}],
                'social':[{'kind':'follow','profile_id':'author','is_author':True,'display_name':'Actual author','at':(self.cutoff-timedelta(days=3)).isoformat()},
                          {'kind':'comment','work_id':'work','at':(self.cutoff-timedelta(days=1)).isoformat()}]}))
        return rows

    def test_small_cohort_never_releases_metrics(self):
        self.assertEqual(build_indicators(self.readers(9),{},self.cutoff)['indicators'],[])

    def test_unique_readers_cohort_rate_weighted_genres_and_all_definitions(self):
        result=build_indicators(self.readers(),{'work':{'title':'Actual work','categories':['Fantasy','Romance']}},self.cutoff)
        metrics={r['id']:r for r in result['indicators']}
        self.assertEqual(len(metrics),10)
        self.assertEqual(metrics['IND-001']['items'][0]['value'],10) # repeated finishes do not inflate readers
        self.assertEqual(metrics['IND-003']['items'][0]['value'],50)
        self.assertEqual(sum(i['value'] for i in metrics['IND-004']['items']),100)
        self.assertEqual(metrics['IND-006']['items'][0]['value'],4)
        self.assertEqual(metrics['IND-007']['items'][0]['title'],'Actual author')
        self.assertTrue(all(m['definition'] and m['unit'] for m in metrics.values()))

    def test_per_work_small_groups_are_suppressed_even_in_large_community(self):
        rows=self.readers()
        for _,p in rows[4:]:
            p['events']=[];p['reviews']=[]
        result=build_indicators(rows,{},self.cutoff)
        self.assertEqual(next(i for i in result['indicators'] if i['id']=='IND-001')['items'],[])

    def test_peer_discovery_requires_common_positive_ratings_and_never_uses_private_peer_reviews(self):
        from app.modules.analytics.peer_discovery import candidate_affinities
        rows=[('owner',{'books':[{'work_id':'shared','archived':False,'rating':5}],'reviews':[]})]
        for i in range(9):
            rows.append((str(i),{'books':[{'work_id':'private','archived':False,'rating':5}],
                'reviews':[{'work_id':'shared','rating':4},{'work_id':'candidate','rating':5}]}))
        self.assertEqual(candidate_affinities('owner',rows),['candidate'])
        self.assertEqual(candidate_affinities('owner',rows[:5]),[])
