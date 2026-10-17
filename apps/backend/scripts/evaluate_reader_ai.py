"""Optional local quality checks from the specification, never stored as user data.

Run: python -m scripts.evaluate_reader_ai
These labelled examples test behaviour, not the user's preferences or clinical traits.
"""
from app.modules.analytics.adaptive_ai import infer
import sys

CASES = [
    ('positive_review', 'finished', {'body':'Me encantó la historia y el desarrollo de sus personajes.', 'rating':5}, 'positivo'),
    ('sad_but_loved', 'finished', {'body':'Me hizo llorar de tristeza y aun así me encantó. Es una de mis mejores lecturas.', 'rating':5}, 'positivo'),
    ('abandoned_unknown', 'abandoned', None, 'indeterminado'),
    ('abandoned_external_reason', 'abandoned', {'reason':'No tengo tiempo para continuar por mi trabajo.'}, 'indeterminado'),
    ('reading_without_comments', 'reading', None, 'indeterminado'),
    ('mixed_opinion', 'finished', {'body':'Me gustaron mucho los personajes, pero el final me decepcionó. Mi opinión es mixta.', 'rating':3}, 'mixto'),
]


def main():
    passed = 0
    selected=[case for case in CASES if len(sys.argv)<2 or case[0]==sys.argv[1]]
    for key,state,opinion,expected in selected:
        sources = [{'key':'reading:00000000-0000-0000-0000-000000000001','id':'00000000-0000-0000-0000-000000000001',
                    'kind':'reading','at':'2026-10-16T12:00:00+00:00',
                    'data':{'state':state,'notebook':{},'abandonment_reason':opinion.get('reason') if opinion else None}}]
        if opinion and 'body' in opinion:
            sources.append({'key':'review:00000000-0000-0000-0000-000000000002:1','kind':'review',
                            'id':'00000000-0000-0000-0000-000000000002','at':'2026-10-16T12:00:00+00:00','data':opinion})
        try:
            result=infer({'title':'Caso de evaluación etiquetado','categories':[],'state':state,'sources':sources})
            ok=result['sentiment']==expected
            if key in ('abandoned_unknown','abandoned_external_reason','reading_without_comments'):
                ok=ok and not result['emotions']
            print(key, 'PASS' if ok else 'NEEDS_REVIEW', flush=True)
            if not ok:
                print('expected_sentiment',expected,'actual_sentiment',result['sentiment'],'emotions_count',len(result['emotions']),flush=True)
            passed+=int(ok)
        except Exception as error:
            print(key,'ERROR',type(error).__name__,flush=True)
    print(f'quality_cases_passed {passed}/{len(selected)}',flush=True)
    return bool(selected) and passed==len(selected)


if __name__=='__main__':
    raise SystemExit(0 if main() else 1)
