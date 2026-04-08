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
    get_actor_info, generate_activity_id, get_local_posts_dir
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
        post_path = os.path.join(get_local_posts_dir(self.config), post_id, 'post.json')
        self.assertTrue(os.path.exists(post_path))

        # Verify file contents
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
        post_path = os.path.join(get_local_posts_dir(self.config), post_id, 'post.json')
        self.assertTrue(os.path.exists(post_path))

        # Verify file contents
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

    def test_post_has_reaction_collection_summaries(self):
        """Posts should include inline collection summaries for likes, shares, replies"""
        post_obj, post_id = create_post('article', "Test", "Content", "https://example.com/test")

        base_url = "https://test.example.com/activitypub/posts"

        for collection_name in ('likes', 'shares', 'replies'):
            coll = post_obj[collection_name]
            self.assertEqual(coll['type'], 'OrderedCollection')
            self.assertEqual(coll['id'], f"{base_url}/{post_id}/{collection_name}")
            self.assertEqual(coll['totalItems'], 0)

    def test_note_has_reaction_collection_summaries(self):
        """Notes should also include reaction collection summaries"""
        post_obj, post_id = create_post('note', None, "Hello!", "https://example.com/note")

        for collection_name in ('likes', 'shares', 'replies'):
            coll = post_obj[collection_name]
            self.assertEqual(coll['type'], 'OrderedCollection')
            self.assertEqual(coll['totalItems'], 0)

    def test_reaction_collection_files_created(self):
        """Post creation should create empty collection files on disk"""
        post_obj, post_id = create_post('article', "Test", "Content", "https://example.com/test")

        base_url = "https://test.example.com/activitypub/posts"

        for collection_name in ('likes', 'shares', 'replies'):
            filepath = os.path.join(get_local_posts_dir(self.config), post_id, f'{collection_name}.json')
            self.assertTrue(os.path.exists(filepath),
                            f"{collection_name}.json should exist in post directory")

            with open(filepath, 'r') as f:
                coll = json.load(f)
            self.assertEqual(coll['type'], 'OrderedCollection')
            self.assertEqual(coll['id'], f"{base_url}/{post_id}/{collection_name}")
            self.assertEqual(coll['totalItems'], 0)
            self.assertEqual(coll['orderedItems'], [])

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
        self.assertTrue(os.path.exists(os.path.join(get_local_posts_dir(self.config), post_id, 'post.json')))
        self.assert_file_exists('outbox', f'{activity_id}.json')

    def test_cli_note_workflow(self):
        """Test the complete CLI workflow for Note posts"""
        from post_utils import create_post, create_activity

        content = "Just published a new blog post about ActivityPub federation!"
        url = "https://myblog.com/activitypub-post"

        post_obj, post_id = create_post('note', None, content, url)
        activity_obj, activity_id = create_activity(post_obj, post_id)

        # Verify all files were created
        self.assertTrue(os.path.exists(os.path.join(get_local_posts_dir(self.config), post_id, 'post.json')))
        self.assert_file_exists('outbox', f'{activity_id}.json')

        # Verify post is a Note type
        post_path = os.path.join(get_local_posts_dir(self.config), post_id, 'post.json')
        with open(post_path, 'r') as f:
            post = json.load(f)
        self.assertEqual(post['type'], 'Note')
        self.assertEqual(post['content'], content)
        self.assertNotIn('name', post)  # No title for Note


if __name__ == '__main__':
    # Add the current directory to Python path for imports
    sys.path.insert(0, '.')
    unittest.main()