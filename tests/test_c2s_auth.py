#!/usr/bin/env python3
"""
Tests for C2S bearer token authentication
"""
import unittest
import os
import json
import sys
from unittest.mock import patch

sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin

C2S_TEST_TOKEN = 'test-c2s-token-abc123'


class TestC2SAuth(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        self.setup_test_environment("c2s_auth",
            server={"domain": "c2s-test.example.com"},
            activitypub={"username": "testuser", "actor_name": "Test User"},
            security={"c2s_token": C2S_TEST_TOKEN})

        self.create_test_actor(actor_name="Test User")

        # Create webfinger.json
        webfinger = {
            "subject": "acct:testuser@c2s-test.example.com",
            "links": [{"rel": "self", "type": "application/activity+json",
                        "href": "https://c2s-test.example.com/activitypub/actor"}]
        }
        webfinger_path = self.get_test_file_path('data_root', 'webfinger.json')
        with open(webfinger_path, 'w') as f:
            json.dump(webfinger, f)

        from app import app, write_actor_config
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True

        with patch('builtins.print'):
            write_actor_config()

        # Create a test post so streams/posts has content
        from post_utils import create_post
        with patch('builtins.print'):
            self.post_obj, self.post_id = create_post(
                'article', "Auth Test Post", "Content", "https://example.com/test")

    def tearDown(self):
        self.teardown_test_environment()

    def _auth_header(self, token=C2S_TEST_TOKEN):
        return {'Authorization': f'Bearer {token}',
                'Accept': 'application/activity+json'}

    # --- streams/posts auth tests ---

    def test_streams_posts_with_valid_token(self):
        """Authenticated request to streams/posts should succeed"""
        response = self.client.get('/activitypub/streams/posts',
                                   headers=self._auth_header())
        self.assertEqual(response.status_code, 200)

    def test_streams_posts_without_token(self):
        """Unauthenticated request to streams/posts should return 401"""
        response = self.client.get('/activitypub/streams/posts',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 401)

    def test_streams_posts_with_wrong_token(self):
        """Request with wrong token should return 401"""
        response = self.client.get('/activitypub/streams/posts',
                                   headers=self._auth_header('wrong-token'))
        self.assertEqual(response.status_code, 401)

    def test_streams_posts_with_malformed_auth(self):
        """Request with malformed Authorization header should return 401"""
        response = self.client.get('/activitypub/streams/posts',
                                   headers={'Authorization': 'Basic abc123',
                                            'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 401)

    # --- Public endpoints remain open ---

    def test_actor_still_public(self):
        """Actor endpoint should NOT require auth"""
        response = self.client.get('/activitypub/actor',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 200)

    def test_outbox_get_still_public(self):
        """Outbox GET should NOT require auth (S2S federation needs it)"""
        response = self.client.get('/activitypub/outbox',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 200)

    def test_followers_still_public(self):
        """Followers endpoint should NOT require auth"""
        response = self.client.get('/activitypub/followers',
                                   headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 200)

    def test_webfinger_still_public(self):
        """WebFinger endpoint should NOT require auth"""
        response = self.client.get(
            '/.well-known/webfinger?resource=acct:testuser@c2s-test.example.com')
        self.assertEqual(response.status_code, 200)

    # --- Unconfigured token ---

    def test_unconfigured_token_returns_500(self):
        """If c2s_token is still REPLACE_ME, return 500"""
        import app as app_module
        original = app_module.config['security']['c2s_token']
        app_module.config['security']['c2s_token'] = 'REPLACE_ME'
        try:
            response = self.client.get('/activitypub/streams/posts',
                                       headers=self._auth_header('REPLACE_ME'))
            self.assertEqual(response.status_code, 500)
        finally:
            app_module.config['security']['c2s_token'] = original


if __name__ == '__main__':
    unittest.main()
