#!/usr/bin/env python3
"""
Tests for Flask ActivityPub server endpoints
"""
import unittest
import tempfile
import shutil
import os
import json
import sys
from unittest.mock import patch

# Add current directory to path for imports
sys.path.insert(0, '.')
from tests.test_config import TestConfigMixin

class TestFlaskApp(unittest.TestCase, TestConfigMixin):
    
    def setUp(self):
        """Set up test client and temporary files"""
        self.setup_test_environment("flask_app",
                                   server={"domain": "app-test.example.com"},
                                   activitypub={"username": "testuser", "actor_name": "Test User"})

        # Create test actor
        self.create_test_actor(actor_name="Test User")

        # Create webfinger.json
        webfinger = {
            "subject": "acct:testuser@app-test.example.com",
            "links": [{"rel": "self", "type": "application/activity+json", "href": "https://app-test.example.com/activitypub/actor"}]
        }
        webfinger_path = self.get_test_file_path('data_root', 'webfinger.json')
        with open(webfinger_path, 'w') as f:
            json.dump(webfinger, f)
        
        # Import app and set up test client
        from app import app
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True
        
        # Generate actor.json
        from app import write_actor_config
        with patch('builtins.print'):  # Suppress output
            write_actor_config()
    
    def tearDown(self):
        """Clean up test environment"""
        self.teardown_test_environment()
    
    def test_webfinger_endpoint(self):
        """Test WebFinger discovery endpoint"""
        response = self.client.get('/.well-known/webfinger?resource=acct:testuser@app-test.example.com')
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['subject'], 'acct:testuser@app-test.example.com')
        self.assertEqual(len(data['links']), 1)
        self.assertEqual(data['links'][0]['rel'], 'self')
    
    def test_webfinger_wrong_resource(self):
        """Test WebFinger with wrong resource"""
        response = self.client.get('/.well-known/webfinger?resource=acct:wrong@example.com')
        self.assertEqual(response.status_code, 404)
    
    def test_actor_endpoint(self):
        """Test actor profile endpoint"""
        response = self.client.get('/activitypub/actor', headers={'Accept': 'application/activity+json'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/activity+json')
        
        data = response.get_json()
        self.assertEqual(data['@context'], 'https://www.w3.org/ns/activitystreams')
        self.assertEqual(data['type'], 'Person')
        self.assertEqual(data['preferredUsername'], 'testuser')
        self.assertEqual(data['name'], 'Test User')
    
    def test_actor_wrong_content_type(self):
        """Test actor endpoint with wrong Accept header"""
        response = self.client.get('/activitypub/actor', headers={'Accept': 'text/html'})
        self.assertEqual(response.status_code, 406)
    
    def test_outbox_endpoint(self):
        """Test outbox endpoint returns dynamic paginated collection"""
        from post_utils import create_post, create_activity

        post_obj, post_id = create_post('article', "Test Post", "Test content", "https://example.com/test")
        activity_obj, activity_id = create_activity(post_obj, post_id)

        response = self.client.get('/activitypub/outbox', headers={'Accept': 'application/activity+json'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/activity+json')

        data = response.get_json()
        self.assertEqual(data['@context'], 'https://www.w3.org/ns/activitystreams')
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 1)
        self.assertEqual(len(data['orderedItems']), 1)
        self.assertEqual(data['orderedItems'][0]['type'], 'Create')

    def test_outbox_empty(self):
        """Test outbox endpoint with no activities"""
        response = self.client.get('/activitypub/outbox', headers={'Accept': 'application/activity+json'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['totalItems'], 0)
        self.assertEqual(len(data['orderedItems']), 0)
        self.assertNotIn('next', data)
        self.assertNotIn('prev', data)

    def test_outbox_pagination_next(self):
        """Test outbox pagination with more activities than page size"""
        from post_utils import create_post, create_activity

        # Create 3 activities (microsecond timestamps ensure uniqueness)
        for i in range(3):
            post_obj, _ = create_post('article', f"Post {i}", f"Content {i}", f"https://example.com/{i}")
            with patch('builtins.print'):
                create_activity(post_obj, _)

        # Request with limit=2 so we get pagination
        response = self.client.get('/activitypub/outbox?limit=2', headers={'Accept': 'application/activity+json'})
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 2)
        self.assertIn('next', data)
        self.assertNotIn('prev', data)

    def test_outbox_pagination_second_page(self):
        """Test outbox second page has prev link and correct items"""
        from post_utils import create_post, create_activity

        for i in range(3):
            post_obj, _ = create_post('article', f"Post {i}", f"Content {i}", f"https://example.com/{i}")
            with patch('builtins.print'):
                create_activity(post_obj, _)

        # Request page 2 with limit=2
        response = self.client.get('/activitypub/outbox?page=2&limit=2', headers={'Accept': 'application/activity+json'})
        data = response.get_json()

        self.assertEqual(data['totalItems'], 3)
        self.assertEqual(len(data['orderedItems']), 1)  # Only 1 remaining
        self.assertNotIn('next', data)
        self.assertIn('prev', data)

    def test_outbox_ordering(self):
        """Test that outbox returns activities in reverse chronological order"""
        from post_utils import create_post, create_activity

        activity_ids = []
        for i in range(3):
            post_obj, post_id = create_post('article', f"Post {i}", f"Content {i}", f"https://example.com/{i}")
            with patch('builtins.print'):
                _, activity_id = create_activity(post_obj, post_id)
            activity_ids.append(activity_id)

        response = self.client.get('/activitypub/outbox', headers={'Accept': 'application/activity+json'})
        data = response.get_json()

        # Most recent activity should be first (reverse filename order)
        returned_ids = [item['id'] for item in data['orderedItems']]
        for i in range(len(returned_ids) - 1):
            self.assertGreater(returned_ids[i], returned_ids[i + 1])

    def test_outbox_page_out_of_range(self):
        """Test requesting a page beyond available activities"""
        response = self.client.get('/activitypub/outbox?page=999', headers={'Accept': 'application/activity+json'})

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(len(data['orderedItems']), 0)
        self.assertNotIn('next', data)

    def test_outbox_limit_capped_at_max(self):
        """Test that client limit is capped at max_page_size from config"""
        from post_utils import create_post, create_activity

        for i in range(3):
            post_obj, _ = create_post('article', f"Post {i}", f"Content {i}", f"https://example.com/{i}")
            with patch('builtins.print'):
                create_activity(post_obj, _)

        # Request limit=1000, should be capped at config max (20)
        response = self.client.get('/activitypub/outbox?limit=1000', headers={'Accept': 'application/activity+json'})
        data = response.get_json()
        self.assertEqual(len(data['orderedItems']), 3)  # All 3 fit within max of 20

    def test_individual_post(self):
        """Test individual post endpoint"""
        # Create a test post
        from post_utils import create_post
        
        with patch('builtins.print'):  # Suppress output
            post_obj, post_id = create_post('article', "Test Post", "Test content", "https://example.com/test")
        
        response = self.client.get(f'/activitypub/posts/{post_id}', headers={'Accept': 'application/activity+json'})
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['name'], 'Test Post')
        self.assertEqual(data['content'], 'Test content')
        self.assertEqual(data['type'], 'Article')
    
    def test_individual_activity(self):
        """Test individual activity endpoint"""
        # Create a test post and activity
        from post_utils import create_post, create_activity
        
        with patch('builtins.print'):  # Suppress output
            post_obj, post_id = create_post('article', "Test Post", "Test content", "https://example.com/test")
            activity_obj, activity_id = create_activity(post_obj, post_id)
        
        response = self.client.get(f'/activitypub/activities/{activity_id}', headers={'Accept': 'application/activity+json'})
        
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data['type'], 'Create')
        self.assertEqual(data['object']['name'], 'Test Post')
    
    def test_nonexistent_post(self):
        """Test accessing nonexistent post"""
        response = self.client.get('/activitypub/posts/nonexistent', headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 404)
    
    def test_nonexistent_activity(self):
        """Test accessing nonexistent activity"""
        response = self.client.get('/activitypub/activities/nonexistent', headers={'Accept': 'application/activity+json'})
        self.assertEqual(response.status_code, 404)


if __name__ == '__main__':
    unittest.main()