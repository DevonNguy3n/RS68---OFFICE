import os
import tempfile
import unittest
from pathlib import Path

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
        good = self.client.post(f'/api/tasks/{self.task_id}/reviews', json={'reviewer': 'content-lead', 'decision': 'pass', 'checklist': checklist})
        self.assertEqual(good.status_code, 201)
        self.assertEqual(self.move('APPROVED').status_code, 200)
        self.assertEqual(self.move('COMPLETED').status_code, 200)
        self.assertGreaterEqual(len(self.client.get(f'/api/tasks/{self.task_id}/events').json()), 6)


if __name__ == '__main__':
    unittest.main()
