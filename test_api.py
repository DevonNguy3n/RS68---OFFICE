import os
import tempfile
import unittest
import json
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
import api


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        api.DB = Path(self.temp.name) / 'test.db'
        api.init_db()
        self.client = TestClient(api.app)
        response = self.client.post('/api/tasks', json={
            'title': 'Bản tin thử nghiệm', 'category': 'news',
            'assignee': 'writer', 'brief': 'Viết tin Facebook từ nguồn đã kiểm chứng',
        })
        self.assertEqual(response.status_code, 201)
        self.task_id = response.json()['id']

    def tearDown(self):
        self.client.close()
        self.temp.cleanup()

    def move(self, status, **kwargs):
        return self.client.post(f'/api/tasks/{self.task_id}/transition', json={'status': status, **kwargs})

    def test_news_requires_verified_source_for_generation(self):
        response = self.client.post(f'/api/tasks/{self.task_id}/generate', json={'mode': 'draft', 'demo': True})
        self.assertEqual(response.status_code, 422)
        self.client.post(f'/api/tasks/{self.task_id}/sources', json={
            'title': 'Nguồn chính thức', 'url': 'https://example.org/story', 'verified': True,
        })
        response = self.client.post(f'/api/tasks/{self.task_id}/generate', json={'mode': 'draft', 'demo': True})
        self.assertEqual(response.status_code, 200)
        self.assertIn('[BẢN MẪU]', response.json()['content'])

    def test_dashboard_uses_saved_records(self):
        initial = self.client.get('/api/dashboard').json()
        self.assertEqual(initial['total'], 1)
        self.assertEqual(initial['by_category']['news'], 1)
        self.assertEqual(initial['by_agent']['writer'], 1)
        self.assertEqual(initial['verified_sources'], 0)
        self.client.post(f'/api/tasks/{self.task_id}/sources', json={
            'title': 'Nguồn chính thức', 'url': 'https://example.org/story', 'verified': True,
        })
        self.assertEqual(self.client.get('/api/dashboard').json()['verified_sources'], 1)

    def test_agent_chat_local_reply_uses_assigned_task(self):
        old_key = os.environ.pop('OPENAI_API_KEY', None)
        try:
            response = self.client.post('/api/agent-chat', json={'agent_id': 'writer', 'message': 'Tiến độ?'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['mode'], 'local')
            self.assertIn('Bản tin thử nghiệm', response.json()['reply'])
        finally:
            if old_key is not None:
                os.environ['OPENAI_API_KEY'] = old_key

    def test_muse2api_routes_agent_chat_to_local_responses_api(self):
        class FakeResponse:
            def __enter__(self):
                return BytesIO(json.dumps({'output': [{'content': [{'type': 'output_text', 'text': 'Đang xử lý task.'}]}]}).encode())

            def __exit__(self, *_):
                return False

        with patch.dict(os.environ, {'AI_PROVIDER': 'muse2api', 'AI_API_KEY': 'test-local-key', 'AI_BASE_URL': 'http://127.0.0.1:18610/v1'}), patch.object(api, 'urlopen', return_value=FakeResponse()) as request_mock:
            response = self.client.post('/api/agent-chat', json={'agent_id': 'writer', 'message': 'Tiến độ?'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['reply'], 'Đang xử lý task.')
            request = request_mock.call_args.args[0]
            self.assertEqual(request.full_url, 'http://127.0.0.1:18610/v1/responses')
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-local-key')
            self.assertEqual(json.loads(request.data)['model'], 'muse-spark')

    def test_meeting_names_all_review_roles_without_claiming_unrecorded_work(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}):
            meeting = self.client.get('/api/agent-meeting')
        self.assertEqual(meeting.status_code, 200)
        messages = meeting.json()['messages']
        self.assertEqual([item['agent_id'] for item in messages],
                         ['director', 'research-lead', 'content-lead', 'manager', 'writer'])
        self.assertIn('Chưa có review', messages[1]['text'])

    def test_qc_requires_draft_and_independent_review(self):
        self.assertEqual(self.move('ASSIGNED').status_code, 200)
        self.assertEqual(self.move('IN_PROGRESS').status_code, 200)
        self.assertEqual(self.move('SUBMITTED', result='Bản nháp').status_code, 422)
        draft = self.client.post(f'/api/tasks/{self.task_id}/drafts', json={'body': 'Nội dung bản nháp thử nghiệm', 'author': 'writer'})
        self.assertEqual(draft.status_code, 201)
        self.assertEqual(self.move('SUBMITTED', result='Nội dung bản nháp thử nghiệm').status_code, 200)
        self.assertEqual(self.move('APPROVED').status_code, 422)
        checklist = {'brief': True, 'facts': True, 'originality': True, 'language': True}
        own = self.client.post(f'/api/tasks/{self.task_id}/reviews', json={'reviewer': 'writer', 'decision': 'pass', 'checklist': checklist})
        self.assertEqual(own.status_code, 403)
        for reviewer in api.REVIEW_CHAIN:
            good = self.client.post(f'/api/tasks/{self.task_id}/reviews', json={'reviewer': reviewer, 'decision': 'pass', 'checklist': checklist})
            self.assertEqual(good.status_code, 201)
            if reviewer != api.REVIEW_CHAIN[-1]:
                self.assertEqual(self.move('APPROVED').status_code, 422)
        self.assertEqual(self.move('APPROVED').status_code, 200)
        self.assertEqual(self.move('COMPLETED').status_code, 200)
        self.assertGreaterEqual(len(self.client.get(f'/api/tasks/{self.task_id}/events').json()), 6)

    def test_agent_loop_requires_source_and_cross_layer_reviews(self):
        self.assertEqual(self.move('ASSIGNED').status_code, 200)
        review_inputs = []
        def mock_review(_task, _draft, reviewer, previous, sources):
            review_inputs.append((reviewer['id'], [item['reviewer'] for item in previous], len(sources)))
            return api.ReviewCreate(reviewer=reviewer['id'], decision='pass', checklist={'brief': True, 'facts': True, 'originality': True, 'language': True})
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'}), patch.object(api, 'generate', side_effect=lambda _id, req: {'content': 'Nội dung nghiên cứu có nguồn' if req.mode == 'research' else 'Bản nháp tin tức có nguồn xác minh'}), patch.object(api, 'ai_review', side_effect=mock_review):
            waiting = self.client.post(f'/api/tasks/{self.task_id}/run')
            self.assertEqual(waiting.json()['action'], 'waiting_for_verified_source')
            self.client.post(f'/api/tasks/{self.task_id}/sources', json={'title': 'Nguồn chính thức', 'url': 'https://example.org/story', 'verified': True})
            actions = [self.client.post(f'/api/tasks/{self.task_id}/run').json()['action'] for _ in range(6)]
        self.assertEqual(actions, ['draft_submitted', 'review_passed', 'review_passed', 'review_passed', 'review_passed', 'approved'])
        reviewers = [review['reviewer'] for review in self.client.get(f'/api/tasks/{self.task_id}/reviews').json()][::-1]
        self.assertEqual(reviewers, list(api.REVIEW_CHAIN))
        self.assertEqual(review_inputs, [(role, list(api.REVIEW_CHAIN[:i]), 1) for i, role in enumerate(api.REVIEW_CHAIN)])
        self.assertEqual(self.client.get(f'/api/tasks/{self.task_id}/agent-steps').status_code, 200)
        self.assertEqual(self.client.get('/api/tasks').json()[0]['status'], 'APPROVED')


if __name__ == '__main__':
    unittest.main()
