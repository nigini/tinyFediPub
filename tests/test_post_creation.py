#!/usr/bin/env python3
"""
Unit tests for ActivityPub post creation workflow
"""
import unittest
import os
import json
import sys
from unittest.mock import patch
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin
from post_utils import (
    generate_post_id, create_post, create_activity,
    get_actor_info, generate_activity_id
)

class TestPostCreation(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("post_creation")
        # Create actor file for these tests
        self.create_test_actor()

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()
    
    def test_generate_post_id(self):
        """Test post ID generation returns UUID"""
        post_id = generate_post_id()

        # Should be a valid UUID4 format
        import uuid
        parsed = uuid.UUID(post_id)
        self.assertEqual(parsed.version, 4)
    
    def test_generate_post_id_uniqueness(self):
        """Test that each call generates a unique ID"""
        id1 = generate_post_id()
        id2 = generate_post_id()
        self.assertNotEqual(id1, id2)
    
    def test_create_post(self):
        """Test post creation and file saving"""
        title = "Test Post"
        content = "This is test content"
        url = "https://example.com/test"
        summary = "Test summary"
        
        post_obj, post_id = create_post('article', title, content, url, summary)
        
        # Check post object structure
        self.assertEqual(post_obj['@context'], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(post_obj['type'], "Article")
        self.assertEqual(post_obj['name'], title)
        self.assertEqual(post_obj['content'], content)
        self.assertEqual(post_obj['url'], url)
        self.assertEqual(post_obj['summary'], summary)
        self.assertEqual(post_obj['attributedTo'], "https://test.example.com/activitypub/actor")
        
        # Check ID format
        self.assertEqual(post_obj['id'], f"https://test.example.com/activitypub/posts/{post_id}")
        
        # Check file was created in directory structure
        self.assert_file_exists('posts', f'{post_id}/post.json')

        # Verify file contents
        post_path = self.get_test_file_path('posts', f'{post_id}/post.json')
        with open(post_path, 'r') as f:
            saved_post = json.load(f)
        self.assertEqual(saved_post, post_obj)

    def test_create_note(self):
        """Test Note creation and file saving"""
        content = "Just published a new blog post about ActivityPub!"
        url = "https://example.com/blog/activitypub"
        summary = "Blog post announcement"

        post_obj, post_id = create_post('note', None, content, url, summary)

        # Check post object structure
        self.assertEqual(post_obj['@context'], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(post_obj['type'], "Note")
        self.assertEqual(post_obj['content'], content)
        self.assertEqual(post_obj['url'], url)
        self.assertEqual(post_obj['summary'], summary)
        self.assertEqual(post_obj['attributedTo'], "https://test.example.com/activitypub/actor")

        # Note should not have a 'name' field (no title)
        self.assertNotIn('name', post_obj)

        # Check ID format
        self.assertEqual(post_obj['id'], f"https://test.example.com/activitypub/posts/{post_id}")

        # Check file was created in directory structure
        self.assert_file_exists('posts', f'{post_id}/post.json')

        # Verify file contents
        post_path = self.get_test_file_path('posts', f'{post_id}/post.json')
        with open(post_path, 'r') as f:
            saved_post = json.load(f)
        self.assertEqual(saved_post, post_obj)

    def test_note_vs_article_differences(self):
        """Test differences between Note and Article types"""
        # Create an Article (has title)
        article_obj, article_id = create_post('article', "My Blog Post", "Full article content here...", "https://example.com/blog/post")

        # Create a Note (no title, short content)
        note_obj, note_id = create_post('note', None, "Just shared something interesting! Check it out:", "https://example.com/shared-link")

        # Article should have name (title)
        self.assertEqual(article_obj['type'], "Article")
        self.assertEqual(article_obj['name'], "My Blog Post")
        self.assertEqual(article_obj['content'], "Full article content here...")

        # Note should NOT have name (no title), per ActivityStreams spec
        self.assertEqual(note_obj['type'], "Note")
        self.assertNotIn('name', note_obj)  # Notes typically don't have titles
        self.assertEqual(note_obj['content'], "Just shared something interesting! Check it out:")

    def test_create_activity(self):
        """Test activity creation and file saving"""
        # First create a post
        post_obj, post_id = create_post('article', "Test", "Content", "https://example.com/test")
        
        # Then create activity
        activity_obj, activity_id = create_activity(post_obj, post_id)
        
        # Check activity structure
        self.assertEqual(activity_obj['@context'], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(activity_obj['type'], "Create")
        self.assertEqual(activity_obj['actor'], "https://test.example.com/activitypub/actor")
        self.assertEqual(activity_obj['object'], post_obj)
        self.assertEqual(activity_obj['published'], post_obj['published'])
        
        # Check activity ID format (should start with 'create-' followed by timestamp)
        self.assertTrue(activity_id.startswith('create-'))
        self.assertRegex(activity_id, r'^create-\d{8}-\d{6}-\d{6}$')
        
        # Check file was created
        self.assert_file_exists('outbox', f'{activity_id}.json')

        # Verify file contents
        activity_path = self.get_test_file_path('outbox', f'{activity_id}.json')
        with open(activity_path, 'r') as f:
            saved_activity = json.load(f)
        self.assertEqual(saved_activity, activity_obj)
    
    def test_get_actor_info(self):
        """Test actor info retrieval"""
        actor = get_actor_info()
        # Verify actor has expected structure from the created test actor
        self.assertIsNotNone(actor)
        self.assertEqual(actor['type'], 'Person')
        self.assertEqual(actor['preferredUsername'], 'test')
        self.assertEqual(actor['name'], 'Test Actor')
    
    def test_get_actor_info_missing_file(self):
        """Test actor info when file doesn't exist"""
        actor_path = self.get_test_file_path('data_root', 'actor.json')
        os.remove(actor_path)

        with patch('builtins.print'):  # Suppress warning print
            actor = get_actor_info()

        self.assertIsNone(actor)

class TestCLIIntegration(unittest.TestCase, TestConfigMixin):
    """Integration tests for the CLI workflow"""

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("cli_integration",
                                   server={"domain": "cli-test.example.com"})

        # Create test actor for CLI tests
        self.create_test_actor(actor_name="CLI Test Actor")

        # Actor is already created by create_test_actor, no need to write again

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()
    
    def test_cli_workflow(self):
        """Test the complete CLI workflow"""
        from post_utils import create_post, create_activity

        title = "CLI Test Post"
        content = "Testing CLI workflow"
        url = "https://myblog.com/cli-test"

        post_obj, post_id = create_post('article', title, content, url)
        activity_obj, activity_id = create_activity(post_obj, post_id)

        # Verify all files were created
        self.assert_file_exists('posts', f'{post_id}/post.json')
        self.assert_file_exists('outbox', f'{activity_id}.json')

    def test_cli_note_workflow(self):
        """Test the complete CLI workflow for Note posts"""
        from post_utils import create_post, create_activity

        content = "Just published a new blog post about ActivityPub federation!"
        url = "https://myblog.com/activitypub-post"

        post_obj, post_id = create_post('note', None, content, url)
        activity_obj, activity_id = create_activity(post_obj, post_id)

        # Verify all files were created
        self.assert_file_exists('posts', f'{post_id}/post.json')
        self.assert_file_exists('outbox', f'{activity_id}.json')

        # Verify post is a Note type
        post_path = self.get_test_file_path('posts', f'{post_id}/post.json')
        with open(post_path, 'r') as f:
            post = json.load(f)
        self.assertEqual(post['type'], 'Note')
        self.assertEqual(post['content'], content)
        self.assertNotIn('name', post)  # No title for Note


class TestUtilityFunctions(unittest.TestCase):
    """Test new utility functions for activity management"""

    def test_generate_activity_id(self):
        """Test activity ID generation with timestamp"""
        from post_utils import generate_activity_id

        # Test different activity types
        create_id = generate_activity_id('create')
        accept_id = generate_activity_id('Accept')
        follow_id = generate_activity_id('FOLLOW')

        # Should include lowercased type and timestamp
        self.assertTrue(create_id.startswith('create-'))
        self.assertTrue(accept_id.startswith('accept-'))
        self.assertTrue(follow_id.startswith('follow-'))

        # Should include timestamp format YYYYMMDD-HHMMSS-ffffff (microseconds)
        import re
        timestamp_pattern = r'-\d{8}-\d{6}-\d{6}$'
        self.assertRegex(create_id, timestamp_pattern)
        self.assertRegex(accept_id, timestamp_pattern)
        self.assertRegex(follow_id, timestamp_pattern)

    def test_parse_actor_url(self):
        """Test actor URL parsing for domain and username extraction"""
        from post_utils import parse_actor_url

        # Test common ActivityPub URL patterns
        test_cases = [
            ('https://mastodon.social/users/alice', ('mastodon.social', 'alice')),
            ('https://pixelfed.social/@bob', ('pixelfed.social', 'bob')),
            ('https://lemmy.world/u/charlie', ('lemmy.world', 'charlie')),
            ('https://example.com/users/dave/profile', ('example.com', 'dave')),
            ('https://micro.blog/users/eve', ('micro.blog', 'eve')),
            ('not-a-url', ('unknown', None)),
            ('', ('unknown', None)),
            (None, ('unknown', None)),
        ]

        for actor_url, expected in test_cases:
            with self.subTest(actor_url=actor_url):
                domain, username = parse_actor_url(actor_url)
                self.assertEqual((domain, username), expected)

    def test_parse_actor_url_edge_cases(self):
        """Test edge cases for actor URL parsing"""
        from post_utils import parse_actor_url

        # URLs without recognizable username patterns
        domain, username = parse_actor_url('https://example.com/some/other/path')
        self.assertEqual(domain, 'example.com')
        self.assertIsNone(username)

        # URL with just domain
        domain, username = parse_actor_url('https://example.com/')
        self.assertEqual(domain, 'example.com')
        self.assertIsNone(username)

        # Malformed URL that might cause exceptions
        domain, username = parse_actor_url('https://')
        self.assertEqual(domain, 'unknown')
        self.assertIsNone(username)


if __name__ == '__main__':
    # Add the current directory to Python path for imports
    sys.path.insert(0, '.')
    unittest.main()