#!/usr/bin/env python3
"""
Unit tests for ActivityPub post update workflow
"""
import unittest
import os
import json
import sys
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin
from post_utils import (
    create_post, update_post, create_update_activity
)


class TestPostUpdate(unittest.TestCase, TestConfigMixin):

    def setUp(self):
        """Set up test environment"""
        self.setup_test_environment("post_update")
        # Create actor file for these tests
        self.create_test_actor()

    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()

    def test_update_post_content(self):
        """Test updating post content"""
        # Create initial post
        post_obj, post_id = create_post(
            'article',
            'Original Title',
            'Original content',
            'https://example.com/post',
            'Original summary'
        )
        original_published = post_obj['published']

        # Update the post
        updated_post, _, was_modified = update_post(
            post_id,
            content='Updated content'
        )

        # Check modification flag
        self.assertTrue(was_modified)

        # Check content was updated
        self.assertEqual(updated_post['content'], 'Updated content')

        # Check other fields unchanged
        self.assertEqual(updated_post['name'], 'Original Title')
        self.assertEqual(updated_post['url'], 'https://example.com/post')
        self.assertEqual(updated_post['summary'], 'Original summary')

        # Check published timestamp preserved
        self.assertEqual(updated_post['published'], original_published)

        # Check updated timestamp added
        self.assertIn('updated', updated_post)
        self.assertIsNotNone(updated_post['updated'])

    def test_update_multiple_fields(self):
        """Test updating multiple fields at once"""
        # Create initial post
        post_obj, post_id = create_post(
            'article',
            'Original Title',
            'Original content',
            'https://example.com/post'
        )

        # Update multiple fields
        updated_post, _, was_modified = update_post(
            post_id,
            title='New Title',
            content='New content',
            url='https://example.com/new-post',
            summary='New summary'
        )

        # Check modification flag
        self.assertTrue(was_modified)

        # Check all fields updated
        self.assertEqual(updated_post['name'], 'New Title')
        self.assertEqual(updated_post['content'], 'New content')
        self.assertEqual(updated_post['url'], 'https://example.com/new-post')
        self.assertEqual(updated_post['summary'], 'New summary')
        self.assertIn('updated', updated_post)

    def test_create_update_activity(self):
        """Test Update activity creation"""
        # Create and update a post
        post_obj, post_id = create_post(
            'article',
            'Test Post',
            'Content',
            'https://example.com/post'
        )
        updated_post, _, was_modified = update_post(post_id, content='Updated content')
        self.assertTrue(was_modified)

        # Create Update activity
        activity_obj, activity_id = create_update_activity(updated_post, post_id)

        # Check activity structure
        self.assertEqual(activity_obj['@context'], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(activity_obj['type'], 'Update')
        self.assertEqual(activity_obj['actor'], 'https://test.example.com/activitypub/actor')

        # Check activity wraps the updated post
        self.assertEqual(activity_obj['object'], updated_post)

        # Check activity uses updated timestamp
        self.assertEqual(activity_obj['published'], updated_post['updated'])

        # Check activity file saved
        self.assert_file_exists('activities', f'{activity_id}.json')

    def test_update_nonexistent_post(self):
        """Test updating a non-existent post raises error"""
        with self.assertRaises(FileNotFoundError):
            update_post('nonexistent-post-id', content='New content')

    def test_update_with_no_changes(self):
        """Test updating post with no changes returns False flag"""
        # Create initial post
        post_obj, post_id = create_post(
            'article',
            'Test Title',
            'Test content',
            'https://example.com/post'
        )
        original_published = post_obj['published']

        # Update with no field changes (all None)
        updated_post, _, was_modified = update_post(post_id)

        # Check modification flag is False
        self.assertFalse(was_modified)

        # Check all fields unchanged
        self.assertEqual(updated_post['name'], 'Test Title')
        self.assertEqual(updated_post['content'], 'Test content')
        self.assertEqual(updated_post['url'], 'https://example.com/post')
        self.assertEqual(updated_post['published'], original_published)

        # Check updated timestamp was NOT added
        self.assertNotIn('updated', updated_post)


class TestLoadExistingPost(unittest.TestCase, TestConfigMixin):
    """Tests for client/edit_post.py load_existing_post()"""

    def setUp(self):
        self.setup_test_environment("load_existing_post")
        self.create_test_actor()

    def tearDown(self):
        self.teardown_test_environment()

    def test_load_existing_post(self):
        """Test loading a post that exists"""
        from client.edit_post import load_existing_post

        post_obj, post_id = create_post(
            'article', 'Test Title', 'Test content', 'https://example.com/post'
        )

        loaded = load_existing_post(post_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['name'], 'Test Title')

    def test_load_nonexistent_post(self):
        """Test loading a post that doesn't exist"""
        from client.edit_post import load_existing_post

        loaded = load_existing_post('nonexistent-id')
        self.assertIsNone(loaded)


if __name__ == '__main__':
    unittest.main()
