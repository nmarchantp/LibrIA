"""The total deadline includes model queue wait and streaming, not only idle reads."""
import asyncio
import json
import time
import unittest
import httpx
from unittest.mock import AsyncMock, patch
from app.modules.analytics.fast_profile import request_json,generate_profile


class DeadlineTransportTest(unittest.TestCase):
    def test_book_waits_without_calling_model_when_profile_has_priority(self):
        from app.modules.analytics.book_transport import request_book, ProfilePriority
        with patch('app.modules.analytics.book_transport.profile_waiting',return_value=True), patch('app.modules.analytics.book_transport.request_json',new_callable=AsyncMock) as transport:
            with self.assertRaises(ProfilePriority):
                asyncio.run(request_book({}))
        transport.assert_not_awaited()

    def test_running_book_is_cancelled_when_profile_arrives(self):
        from app.modules.analytics.book_transport import request_book, ProfilePriority
        cancelled=[]
        async def slow(*args):
            try:
                await asyncio.sleep(10)
            finally:
                cancelled.append(True)
        with patch('app.modules.analytics.book_transport.profile_waiting',side_effect=[False,True]), patch('app.modules.analytics.book_transport.request_json',side_effect=slow):
            with self.assertRaises(ProfilePriority):
                asyncio.run(request_book({}))
        self.assertEqual(cancelled,[True])

    def test_one_compact_call_preserves_every_book_and_maps_real_references(self):
        context={'library_summary':{'rated':2,'total':2},'sources':[
            {'key':f'experience:{i}','kind':'experience','data':{'title':f'Book {i}','contributions':[{'kind':'review','at':'2026-10-16','data':{'body':f'Personal opinion {i}'}}]}}
            for i in range(2)]}
        context['sources'][0]['data']['cached_analysis']={'interpretation':'An individual book summary'}
        response={'identity':'Intereses expresados en diferentes obras.','synthesis':'Una síntesis global de tus experiencias de lectura.',
                  'basis':['s0','s1'],'findings':[
                      {'category':'historical_affinities','text':'Intereses expresados en diferentes obras.','sources':['s0','s1']},
                      {'category':'recent_affinities','text':'Intereses expresados en diferentes obras.','sources':['s0','s1']}],
                  'limitation':'Las preferencias reflejan tus aportes disponibles.'}
        with patch('app.modules.analytics.fast_profile.request_json',new_callable=AsyncMock,return_value=response) as transport:
            result=generate_profile(context,20)
        self.assertEqual(result['identity_evidence_ids'],['experience:0','experience:1'])
        self.assertEqual(len(result['historical_affinities']),1)
        self.assertEqual(result['recent_affinities'],[])
        body=json.loads(transport.call_args.args[0]['messages'][1]['content'])
        self.assertEqual(len(body['sources']),2)
        for i,source in enumerate(body['sources']):
            self.assertEqual(source['data']['contributions'][0]['data']['body'],f'Personal opinion {i}')
            self.assertNotIn('cached_analysis',source['data'])
        transport.assert_awaited_once()
    def test_waiting_for_headers_cannot_exceed_total_budget(self):
        async def slow(request):
            await asyncio.sleep(5)
            return httpx.Response(200,json={})
        started=time.monotonic()
        with self.assertRaises(TimeoutError):
            asyncio.run(request_json({},0.03,transport=httpx.MockTransport(slow)))
        self.assertLess(time.monotonic()-started,1)

    def test_tokens_do_not_restart_deadline_and_stream_is_closed(self):
        closed=[]
        class Endless(httpx.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    await asyncio.sleep(0.005)
                    yield (json.dumps({'message':{'content':' '}})+'\n').encode()
            async def aclose(self):
                closed.append(True)
        started=time.monotonic()
        with self.assertRaises(TimeoutError):
            asyncio.run(request_json({},0.04,transport=httpx.MockTransport(lambda request:httpx.Response(200,stream=Endless()))))
        self.assertLess(time.monotonic()-started,1)
        self.assertTrue(closed)
