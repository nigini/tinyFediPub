#!/usr/bin/env python3
"""
Tests for streams/followed endpoint content and pagination
"""
import unittest
import time
import sys

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin

C2S_TOKEN = 'test-followed-token'


class TestStreamsFollowed(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        self.setup_test_environment("streams_followed",
            server={"domain": "followed-test.example.com"},
            activitypub={"username": "testuser", "actor_name": "Test User",
                         "max_page_size": 20},
            security={"c2s_token": C2S_TOKEN})

        self.create_test_actor(actor_name="Test User")
        self.setup_webfinger()
        self.setup_test_client()

    def tearDown(self):
        self.teardown_test_environment()

    # --- Content tests ---

    def test_empty_followed(self):
        """Empty remote posts directory returns empty collection"""
        response = self.client.get('/activitypub/streams/followed',
                                   headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 0)
        self.assertEqual(len(data['orderedItems']), 0)

    def test_returns_objects_with_content(self):
        """Followed stream returns objects with their content"""
        self.create_remote_post(
            'mastodon.social', 'users/alice', '12345',
            'Note', 'Hello from the fediverse!'
        )

        response = self.client.get('/activitypub/streams/followed',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 1)
        item = data['orderedItems'][0]
        self.assertEqual(item['type'], 'Note')
        self.assertEqual(item['content'], 'Hello from the fediverse!')

    def test_returns_multiple_actors(self):
        """Followed stream mixes posts from different actors"""
        self.create_remote_post('mastodon.social', 'users/alice', '1', 'Note', 'Alice post')
        time.sleep(0.02)
        self.create_remote_post('social.coop', 'users/bob', '2', 'Article', 'Bob article', name='Bob\'s Article')

        response = self.client.get('/activitypub/streams/followed',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 2)
        types = {item['type'] for item in data['orderedItems']}
        self.assertEqual(types, {'Note', 'Article'})

    def test_ordered_by_mtime(self):
        """Posts are ordered by file modification time, most recent first"""
        self.create_remote_post('old.test', 'u/alice', '1', 'Note', 'Old post')
        time.sleep(0.05)
        self.create_remote_post('new.test', 'u/alice', '2', 'Note', 'New post')

        response = self.client.get('/activitypub/streams/followed',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(len(data['orderedItems']), 2)
        self.assertIn('New post', data['orderedItems'][0]['content'])
        self.assertIn('Old post', data['orderedItems'][1]['content'])

    # --- Pagination tests ---

    def test_pagination_next_link(self):
        """More posts than page size produces next link"""
        for i in range(3):
            self.create_remote_post('test.test', 'users/alice', str(i), 'Note', f'Post {i}')
            time.sleep(0.01)

        response = self.client.get('/activitypub/streams/followed?limit=2',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 2)
        self.assertIn('next', data)
        self.assertNotIn('prev', data)

    def test_pagination_second_page(self):
        """Second page has prev link and remaining items"""
        for i in range(3):
            self.create_remote_post('test.test', 'users/alice', str(i), 'Note', f'Post {i}')
            time.sleep(0.01)

        response = self.client.get('/activitypub/streams/followed?page=2&limit=2',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 1)
        self.assertNotIn('next', data)
        self.assertIn('prev', data)

    # --- Auth tests ---

    def test_requires_auth(self):
        """Unauthenticated request to streams/followed returns 401"""
        response = self.client.get('/activitypub/streams/followed',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 401)

    def test_wrong_token_rejected(self):
        """Request with wrong bearer token returns 401"""
        response = self.client.get('/activitypub/streams/followed',
                                   headers={'Authorization': 'Bearer wrong-token',
                                            'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 401)

    def test_requires_ap_content_type(self):
        """Request without proper Accept header returns 406"""
        response = self.client.get('/activitypub/streams/followed',
                                   headers={'Authorization': f'Bearer {C2S_TOKEN}',
                                            'Accept': 'text/html'})
        self.assertEqual(response.status_code, 406)


if __name__ == '__main__':
    unittest.main()