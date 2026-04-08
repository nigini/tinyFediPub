#!/usr/bin/env python3
"""
Tests for C2S outbox POST — client submits AS2 objects, server wraps in Create
"""
import unittest
import os
import json
import sys
from unittest.mock import patch

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin
from post_utils import get_local_posts_dir

C2S_TOKEN = 'test-outbox-token'


class TestC2SOutboxPost(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        self.setup_test_environment("c2s_outbox",
            server={"domain": "c2s-test.example.com"},
            activitypub={"username": "testuser", "actor_name": "Test User"},
            security={"c2s_token": C2S_TOKEN})

        self.create_test_actor(actor_name="Test User")

        webfinger = {
            "subject": "acct:testuser@c2s-test.example.com",
            "links": [{"rel": "self", "type": "application/activity+json",
                        "href": "https://c2s-test.example.com/activitypub/actor"}]
        }
        with open(self.get_test_file_path('data_root', 'webfinger.json'), 'w') as f:
            json.dump(webfinger, f)

        from app import app, write_actor_config
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True
        with patch('builtins.print'):
            write_actor_config()

    def tearDown(self):
        self.teardown_test_environment()

    def _post_to_outbox(self, data, token=C2S_TOKEN):
        headers = {
            'Content-Type': 'application/activity+json',
            'Authorization': f'Bearer {token}'
        }
        return self.client.post('/activitypub/outbox',
                                data=json.dumps(data),
                                headers=headers)

    # --- Auth ---

    def test_outbox_post_requires_auth(self):
        """POST to outbox without token returns 401"""
        response = self.client.post('/activitypub/outbox',
            data=json.dumps({"type": "Note", "content": "Hello"}),
            headers={'Content-Type': 'application/activity+json'})
        self.assertEqual(response.status_code, 401)

    def test_outbox_post_wrong_token(self):
        """POST to outbox with wrong token returns 401"""
        response = self._post_to_outbox(
            {"type": "Note", "content": "Hello"}, token='wrong')
        self.assertEqual(response.status_code, 401)

    def test_outbox_get_still_works(self):
        """GET outbox should still return activities (not blocked by POST auth)"""
        response = self.client.get('/activitypub/outbox',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 200)

    # --- Object submission ---

    def test_post_note_returns_201(self):
        """Submitting a Note object returns 201 with Location header"""
        response = self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "content": "<p>Hello world</p>"
        })
        self.assertEqual(response.status_code, 201)
        self.assertIn('Location', response.headers)

    def test_post_note_creates_files(self):
        """Submitting a Note creates post.json, activity, and reaction collections"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "content": "<p>Hello world</p>"
        })

        # One post directory with post.json + reaction files
        posts_dir = get_local_posts_dir(self.config)
        post_dirs = [d for d in os.listdir(posts_dir)
                     if os.path.isdir(os.path.join(posts_dir, d))]
        self.assertEqual(len(post_dirs), 1)

        post_dir = os.path.join(posts_dir, post_dirs[0])
        self.assertTrue(os.path.exists(os.path.join(post_dir, 'post.json')))
        self.assertTrue(os.path.exists(os.path.join(post_dir, 'likes.json')))
        self.assertTrue(os.path.exists(os.path.join(post_dir, 'shares.json')))
        self.assertTrue(os.path.exists(os.path.join(post_dir, 'replies.json')))

        # One activity in outbox
        outbox_dir = self.config['directories']['outbox']
        activity_files = [f for f in os.listdir(outbox_dir) if f.endswith('.json')]
        self.assertEqual(len(activity_files), 1)

    def test_post_article(self):
        """Submitting an Article creates an Article post with name"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "name": "My Blog Post",
            "content": "<p>Full article</p>",
            "url": "https://myblog.com/post-1"
        })

        posts_dir = get_local_posts_dir(self.config)
        post_dirs = [d for d in os.listdir(posts_dir)
                     if os.path.isdir(os.path.join(posts_dir, d))]
        with open(os.path.join(posts_dir, post_dirs[0], 'post.json')) as f:
            post = json.load(f)
        self.assertEqual(post['type'], 'Article')
        self.assertEqual(post['name'], 'My Blog Post')

    def test_server_assigns_id(self):
        """Server assigns its own id, ignoring client-supplied id"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "id": "https://evil.com/fake-id",
            "content": "<p>Hello</p>"
        })

        posts_dir = get_local_posts_dir(self.config)
        post_dirs = [d for d in os.listdir(posts_dir)
                     if os.path.isdir(os.path.join(posts_dir, d))]
        with open(os.path.join(posts_dir, post_dirs[0], 'post.json')) as f:
            post = json.load(f)
        self.assertIn('c2s-test.example.com', post['id'])
        self.assertNotIn('evil.com', post['id'])

    def test_server_sets_published_and_attributed_to(self):
        """Server sets published and attributedTo"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "content": "<p>Hello</p>"
        })

        posts_dir = get_local_posts_dir(self.config)
        post_dirs = [d for d in os.listdir(posts_dir)
                     if os.path.isdir(os.path.join(posts_dir, d))]
        with open(os.path.join(posts_dir, post_dirs[0], 'post.json')) as f:
            post = json.load(f)
        self.assertIn('published', post)
        self.assertEqual(post['attributedTo'],
                         'https://c2s-test.example.com/activitypub/actor')

    def test_activity_wraps_object(self):
        """The created activity wraps the post object"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "content": "<p>Wrapped</p>"
        })

        outbox_dir = self.config['directories']['outbox']
        activity_files = [f for f in os.listdir(outbox_dir) if f.endswith('.json')]
        with open(os.path.join(outbox_dir, activity_files[0])) as f:
            activity = json.load(f)
        self.assertEqual(activity['type'], 'Create')
        self.assertEqual(activity['object']['content'], '<p>Wrapped</p>')

    def test_post_appears_in_streams(self):
        """A posted object should appear in streams/posts"""
        self._post_to_outbox({
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Note",
            "content": "<p>Stream test</p>"
        })

        response = self.client.get('/activitypub/streams/posts',
            headers={'Accept': 'application/activity+json',
                     'Authorization': f'Bearer {C2S_TOKEN}'})
        data = response.get_json()
        self.assertEqual(data['totalItems'], 1)
        self.assertEqual(data['orderedItems'][0]['content'], '<p>Stream test</p>')

    # --- Validation ---

    def test_reject_empty_body(self):
        """Empty POST body returns 400"""
        response = self.client.post('/activitypub/outbox',
            headers={'Content-Type': 'application/activity+json',
                     'Authorization': f'Bearer {C2S_TOKEN}'})
        self.assertEqual(response.status_code, 400)

    def test_reject_missing_type(self):
        """Object without type returns 400"""
        response = self._post_to_outbox({"content": "no type"})
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
