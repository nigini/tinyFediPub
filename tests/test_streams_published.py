#!/usr/bin/env python3
"""
Tests for streams/published endpoint content and pagination
"""
import unittest
import sys
import time

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin

C2S_TOKEN = 'test-streams-token'


class TestStreamsPublished(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        self.setup_test_environment("streams_published",
            server={"domain": "streams-test.example.com"},
            activitypub={"username": "testuser", "actor_name": "Test User",
                         "max_page_size": 20},
            security={"c2s_token": C2S_TOKEN})

        self.create_test_actor(actor_name="Test User")
        self.setup_webfinger()
        self.setup_test_client()

    def tearDown(self):
        self.teardown_test_environment()

    # --- Content tests ---

    def test_empty_stream(self):
        """Empty posts directory returns empty collection"""
        response = self.client.get('/activitypub/streams/published',
                                   headers=self.auth_headers())
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 0)
        self.assertEqual(len(data['orderedItems']), 0)

    def test_returns_objects_not_activities(self):
        """Stream returns post objects directly, not Create activity wrappers"""
        self.create_local_post('uuid-1', 'Test Post', 'Hello')

        response = self.client.get('/activitypub/streams/published',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 1)
        item = data['orderedItems'][0]
        self.assertEqual(item['type'], 'Article')
        self.assertEqual(item['name'], 'Test Post')
        self.assertNotEqual(item['type'], 'Create')

    def test_post_with_likes_field(self):
        """Posts with likes include the likes collection URL"""
        self.create_local_post('uuid-liked', 'Liked Post', 'Content',
                               likes=f"https://streams-test.example.com/activitypub/posts/uuid-liked/likes")

        response = self.client.get('/activitypub/streams/published',
                                   headers=self.auth_headers())
        data = response.get_json()
        item = data['orderedItems'][0]

        self.assertIn('likes', item)
        self.assertIn('/posts/uuid-liked/likes', item['likes'])

    def test_post_without_likes_field(self):
        """Posts without likes don't have a likes field"""
        self.create_local_post('uuid-nolikes', 'No Likes', 'Content')

        response = self.client.get('/activitypub/streams/published',
                                   headers=self.auth_headers())
        data = response.get_json()
        item = data['orderedItems'][0]

        self.assertNotIn('likes', item)

    # --- Ordering tests ---

    def test_ordered_by_mtime(self):
        """Posts are ordered by file modification time, most recent first"""
        self.create_local_post('uuid-old', 'Old Post', 'Old')
        time.sleep(0.05)
        self.create_local_post('uuid-new', 'New Post', 'New')

        response = self.client.get('/activitypub/streams/published',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(len(data['orderedItems']), 2)
        self.assertEqual(data['orderedItems'][0]['name'], 'New Post')
        self.assertEqual(data['orderedItems'][1]['name'], 'Old Post')

    # --- Pagination tests ---

    def test_pagination_next_link(self):
        """More posts than page size produces next link"""
        for i in range(3):
            self.create_local_post(f'uuid-{i}', f'Post {i}', f'Content {i}')
            time.sleep(0.01)

        response = self.client.get('/activitypub/streams/published?limit=2',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 2)
        self.assertIn('next', data)
        self.assertNotIn('prev', data)

    def test_pagination_second_page(self):
        """Second page has prev link and remaining items"""
        for i in range(3):
            self.create_local_post(f'uuid-{i}', f'Post {i}', f'Content {i}')
            time.sleep(0.01)

        response = self.client.get('/activitypub/streams/published?page=2&limit=2',
                                   headers=self.auth_headers())
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 1)
        self.assertNotIn('next', data)
        self.assertIn('prev', data)


if __name__ == '__main__':
    unittest.main()
