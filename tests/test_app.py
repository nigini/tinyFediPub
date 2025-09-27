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
        webfinger_path = self.get_test_file_path('outbox', 'webfinger.json')
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
        """Test outbox endpoint"""
        # Create a test post first
        from post_utils import create_post, create_activity, regenerate_outbox
        
        post_obj, post_id = create_post('article', "Test Post", "Test content", "https://example.com/test")
        activity_obj, activity_id = create_activity(post_obj, post_id)
        with patch('builtins.print'):  # Suppress output
            regenerate_outbox()
        
        response = self.client.get('/activitypub/outbox', headers={'Accept': 'application/activity+json'})
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['Content-Type'], 'application/activity+json')
        
        data = response.get_json()
        self.assertEqual(data['@context'], 'https://www.w3.org/ns/activitystreams')
        self.assertEqual(data['type'], 'OrderedCollection')
        self.assertEqual(data['totalItems'], 1)
        self.assertEqual(len(data['orderedItems']), 1)
    
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