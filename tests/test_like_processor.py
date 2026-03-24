#!/usr/bin/env python3
"""
Unit tests for Like activity processing
"""
import unittest
import tempfile
import shutil
import os
import json
import sys

from tests.test_config import TestConfigMixin


class TestLikeProcessor(unittest.TestCase):
    """Test Like activity processing functionality"""

    def setUp(self):
        """Set up temporary directory with a test post for Like tests"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        self.config = {
            "server": {
                "domain": "test.example.com",
                "protocol": "https",
                "host": "0.0.0.0",
                "port": 5000,
                "debug": True
            },
            "activitypub": {
                "username": "test",
                "actor_name": "Test Actor",
                "actor_summary": "A test actor",
                "namespace": "activitypub",
                "auto_accept_follow_requests": True
            },
            "security": {
                "public_key_file": "test.pem",
                "private_key_file": "test.pem"
            },
            "directories": {
                "inbox": "static/tests/inbox",
                "inbox_queue": "static/tests/inbox/queue",
                "data_root": "static/tests",
                "outbox": "static/tests/outbox",
                "posts": "static/tests/posts",
                "followers": "static/tests"
            }
        }
        with open('config.json', 'w') as f:
            json.dump(self.config, f)
        with open('test.pem', 'w') as f:
            f.write('test key')

        # Create required directories
        os.makedirs(self.config['directories']['inbox'], exist_ok=True)
        os.makedirs(self.config['directories']['inbox_queue'], exist_ok=True)
        os.makedirs(self.config['directories']['outbox'], exist_ok=True)

        # Create a test post for Like targets
        post_dir = os.path.join(self.config['directories']['posts'], self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        test_post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "name": "Test Post",
            "content": "Hello world"
        }
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_like_activity_creates_likes_collection(self):
        """Test that a Like activity creates a likes.json for the post"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/like-123"
        }

        result = processor.process_inbox(like_activity, "like-test.json", self.config)
        self.assertTrue(result)

        # Verify likes.json was created in the post directory
        likes_path = os.path.join(
            self.config['directories']['posts'], self.post_uuid, 'likes.json'
        )
        self.assertTrue(os.path.exists(likes_path))

        with open(likes_path) as f:
            likes_data = json.load(f)

        self.assertEqual(likes_data['type'], 'Collection')
        self.assertEqual(likes_data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', likes_data['items'])

    def test_like_activity_missing_actor(self):
        """Test that a Like with no actor returns False"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/like-123"
        }

        result = processor.process_inbox(like_activity, "like-no-actor.json", self.config)
        self.assertFalse(result)

    def test_like_activity_missing_object(self):
        """Test that a Like with no object returns False"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "id": "https://mastodon.social/activities/like-123"
        }

        result = processor.process_inbox(like_activity, "like-no-object.json", self.config)
        self.assertFalse(result)

    def test_like_nonexistent_post(self):
        """Test that a Like targeting an unknown post returns False"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://test.example.com/activitypub/posts/nonexistent-uuid",
            "id": "https://mastodon.social/activities/like-123"
        }

        result = processor.process_inbox(like_activity, "like-bad-post.json", self.config)
        self.assertFalse(result)

    def test_like_non_local_object(self):
        """Test that a Like targeting a non-local URL returns False"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": "https://other-server.com/posts/123",
            "id": "https://mastodon.social/activities/like-123"
        }

        result = processor.process_inbox(like_activity, "like-non-local.json", self.config)
        self.assertFalse(result)

    def test_duplicate_like_ignored(self):
        """Test that the same actor liking the same post twice doesn't duplicate"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/like-123"
        }

        result1 = processor.process_inbox(like_activity, "like-1.json", self.config)
        result2 = processor.process_inbox(like_activity, "like-2.json", self.config)

        self.assertTrue(result1)
        self.assertTrue(result2)

        likes_path = os.path.join(
            self.config['directories']['posts'], self.post_uuid, 'likes.json'
        )
        with open(likes_path) as f:
            likes_data = json.load(f)

        self.assertEqual(likes_data['totalItems'], 1)
        self.assertEqual(len(likes_data['items']), 1)

    def test_multiple_actors_like_same_post(self):
        """Test that multiple actors can like the same post"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_alice = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/like-alice"
        }
        like_bob = {
            "type": "Like",
            "actor": "https://pixelfed.social/users/bob",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://pixelfed.social/activities/like-bob"
        }

        processor.process_inbox(like_alice, "like-alice.json", self.config)
        processor.process_inbox(like_bob, "like-bob.json", self.config)

        likes_path = os.path.join(
            self.config['directories']['posts'], self.post_uuid, 'likes.json'
        )
        with open(likes_path) as f:
            likes_data = json.load(f)

        self.assertEqual(likes_data['totalItems'], 2)
        self.assertIn('https://mastodon.social/users/alice', likes_data['items'])
        self.assertIn('https://pixelfed.social/users/bob', likes_data['items'])

    def test_like_adds_likes_field_to_post(self):
        """Test that processing a Like adds a 'likes' collection URL to post.json"""
        from activity_processor.like import LikeProcessor

        processor = LikeProcessor()

        like_activity = {
            "type": "Like",
            "actor": "https://mastodon.social/users/alice",
            "object": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "id": "https://mastodon.social/activities/like-123"
        }

        processor.process_inbox(like_activity, "like-test.json", self.config)

        # Load the post.json and verify it now has a likes field
        post_path = os.path.join(
            self.config['directories']['posts'], self.post_uuid, 'post.json'
        )
        with open(post_path) as f:
            post_data = json.load(f)

        self.assertIn('likes', post_data)
        self.assertEqual(
            post_data['likes'],
            f"https://test.example.com/activitypub/posts/{self.post_uuid}/likes"
        )


class TestLikesEndpoint(unittest.TestCase, TestConfigMixin):
    """Integration test: likes collection endpoint on posts"""

    def setUp(self):
        self.setup_test_environment("likes_endpoint",
                                    server={"domain": "test.example.com"},
                                    activitypub={"username": "test", "actor_name": "Test Actor"})

        self.post_uuid = "550e8400-e29b-41d4-a716-446655440000"

        # Create a test post
        post_dir = os.path.join(self.config['directories']['posts'], self.post_uuid)
        os.makedirs(post_dir, exist_ok=True)
        test_post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": f"https://test.example.com/activitypub/posts/{self.post_uuid}",
            "name": "Test Post",
            "content": "Hello world"
        }
        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(test_post, f)

        # Create a likes collection for that post
        likes_data = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Collection",
            "id": f"https://test.example.com/activitypub/posts/{self.post_uuid}/likes",
            "totalItems": 1,
            "items": ["https://mastodon.social/users/alice"]
        }
        with open(os.path.join(post_dir, 'likes.json'), 'w') as f:
            json.dump(likes_data, f)

        # Create a second post with no likes
        self.post_uuid_no_likes = "660e8400-e29b-41d4-a716-446655440000"
        post_dir_2 = os.path.join(self.config['directories']['posts'], self.post_uuid_no_likes)
        os.makedirs(post_dir_2, exist_ok=True)
        test_post_2 = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Article",
            "id": f"https://test.example.com/activitypub/posts/{self.post_uuid_no_likes}",
            "name": "Another Post",
            "content": "No likes yet"
        }
        with open(os.path.join(post_dir_2, 'post.json'), 'w') as f:
            json.dump(test_post_2, f)

        from app import app
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True

    def tearDown(self):
        self.teardown_test_environment()

    def test_likes_endpoint_returns_collection(self):
        """Test that /posts/{uuid}/likes returns the likes collection"""
        response = self.client.get(
            f'/activitypub/posts/{self.post_uuid}/likes',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'Collection')
        self.assertEqual(data['totalItems'], 1)
        self.assertIn('https://mastodon.social/users/alice', data['items'])

    def test_likes_endpoint_no_likes(self):
        """Test that /posts/{uuid}/likes returns 404 when no likes.json exists"""
        response = self.client.get(
            f'/activitypub/posts/{self.post_uuid_no_likes}/likes',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 404)

    def test_likes_endpoint_nonexistent_post(self):
        """Test that /posts/{uuid}/likes returns 404 for unknown post"""
        response = self.client.get(
            '/activitypub/posts/nonexistent-uuid/likes',
            headers={'Accept': 'application/activity+json'}
        )
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()
