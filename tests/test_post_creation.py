#!/usr/bin/env python3
"""
Unit tests for ActivityPub post creation workflow
"""
import unittest
import tempfile
import shutil
import os
import json
import sys
from unittest.mock import patch
from post_utils import (
    generate_post_id, create_post, create_activity, 
    regenerate_outbox, get_actor_info
)

class TestPostCreation(unittest.TestCase):
    
    def setUp(self):
        """Set up temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create test config
        self.test_config = {
            "server": {"domain": "test.example.com"},
            "activitypub": {"namespace": "activitypub"},
            "security": {
                "public_key_file": "test_public.pem",
                "private_key_file": "test_private.pem"
            }
        }
        
        with open('config.json', 'w') as f:
            json.dump(self.test_config, f)
        
        # Create test actor.json
        os.makedirs('static', exist_ok=True)
        self.test_actor = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Person",
            "id": "https://test.example.com/activitypub/actor",
            "preferredUsername": "testuser",
            "name": "Test User"
        }
        
        with open('static/actor.json', 'w') as f:
            json.dump(self.test_actor, f)
    
    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_generate_post_id_with_title(self):
        """Test post ID generation with title"""
        post_id = generate_post_id("My Awesome Post!")
        
        # Should start with timestamp format YYYYMMDD-HHMMSS
        self.assertRegex(post_id, r'^\d{8}-\d{6}-my-awesome-post$')
    
    def test_generate_post_id_without_title(self):
        """Test post ID generation without title"""
        post_id = generate_post_id()
        
        # Should be just timestamp format
        self.assertRegex(post_id, r'^\d{8}-\d{6}$')
    
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
        
        # Check file was created
        post_path = f'static/posts/{post_id}.json'
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

        # Check file was created
        post_path = f'static/posts/{post_id}.json'
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
        
        # Check activity ID
        expected_activity_id = f"create-{post_id}"
        self.assertEqual(activity_id, expected_activity_id)
        
        # Check file was created
        activity_path = f'static/activities/{activity_id}.json'
        self.assertTrue(os.path.exists(activity_path))
        
        # Verify file contents
        with open(activity_path, 'r') as f:
            saved_activity = json.load(f)
        self.assertEqual(saved_activity, activity_obj)
    
    def test_regenerate_outbox(self):
        """Test outbox regeneration from activities"""
        # Create a couple of posts and activities
        posts_and_ids = []
        for i in range(2):
            post_obj, post_id = create_post('article', f"Post {i}", f"Content {i}", f"https://example.com/post{i}")
            activity_obj, activity_id = create_activity(post_obj, post_id)
            posts_and_ids.append((post_obj, post_id, activity_obj, activity_id))
        
        # Regenerate outbox
        regenerate_outbox()
        
        # Check outbox file was created
        self.assertTrue(os.path.exists('static/outbox.json'))
        
        # Verify outbox contents
        with open('static/outbox.json', 'r') as f:
            outbox = json.load(f)
        
        self.assertEqual(outbox['@context'], "https://www.w3.org/ns/activitystreams")
        self.assertEqual(outbox['type'], "OrderedCollection")
        self.assertEqual(outbox['id'], "https://test.example.com/activitypub/outbox")
        self.assertEqual(outbox['totalItems'], 2)
        
        # Check activities are in reverse chronological order (most recent first)
        items = outbox['orderedItems']
        self.assertEqual(len(items), 2)
        
        # Verify activity references (not full objects)
        for i, item in enumerate(items):
            post_obj, post_id, activity_obj, activity_id = posts_and_ids[1-i]  # Reversed order
            self.assertEqual(item['type'], 'Create')
            self.assertEqual(item['id'], f"https://test.example.com/activitypub/activities/{activity_id}")
            self.assertEqual(item['actor'], "https://test.example.com/activitypub/actor")
            self.assertEqual(item['object'], f"https://test.example.com/activitypub/posts/{post_id}")
    
    def test_get_actor_info(self):
        """Test actor info retrieval"""
        actor = get_actor_info()
        self.assertEqual(actor, self.test_actor)
    
    def test_get_actor_info_missing_file(self):
        """Test actor info when file doesn't exist"""
        os.remove('static/actor.json')

        with patch('builtins.print'):  # Suppress warning print
            actor = get_actor_info()

        self.assertIsNone(actor)

    def test_regenerate_outbox_with_malformed_activities(self):
        """Test outbox generation skips malformed activity files gracefully"""
        # Create a valid activity first
        post_obj, post_id = create_post('article', "Good Post", "Valid content", "https://example.com/good")
        activity_obj, activity_id = create_activity(post_obj, post_id)

        # Verify we have exactly one valid activity file at this point
        activities_files = [f for f in os.listdir('static/activities') if f.endswith('.json')]
        self.assertEqual(len(activities_files), 1, f"Expected 1 activity file, found {len(activities_files)}: {activities_files}")

        # Create malformed JSON file
        malformed_json_path = 'static/activities/malformed.json'
        with open(malformed_json_path, 'w') as f:
            f.write('{ "invalid": json syntax here')

        # Create structurally invalid but well-formed JSON
        invalid_structure_path = 'static/activities/invalid-structure.json'
        invalid_activity = {
            "someField": "value",
            "missing": "required fields like type, id, actor",
            "notAnActivity": True
        }
        with open(invalid_structure_path, 'w') as f:
            json.dump(invalid_activity, f)

        # Should complete successfully, skipping bad files
        import io
        import sys
        from contextlib import redirect_stdout

        # Capture stdout to verify warnings are printed
        captured_output = io.StringIO()
        with redirect_stdout(captured_output):
            regenerate_outbox()

        # Verify warnings were printed
        output = captured_output.getvalue()
        self.assertIn('Warning: Skipping malformed activity file', output)
        self.assertIn('malformed.json', output)
        self.assertIn('invalid-structure.json', output)

        # Verify outbox was created successfully
        self.assertTrue(os.path.exists('static/outbox.json'))

        with open('static/outbox.json', 'r') as f:
            outbox = json.load(f)

        # Verify the correction worked: totalItems should match orderedItems length
        self.assertEqual(outbox['totalItems'], len(outbox['orderedItems']),
                        "totalItems should be corrected to match actual valid activities")

        # Should have exactly 1 valid activity (the one we created)
        self.assertEqual(len(outbox['orderedItems']), 1,
                        "Should contain exactly 1 valid activity after skipping malformed files")

        # All activities should be valid Create activities
        for item in outbox['orderedItems']:
            self.assertEqual(item['type'], 'Create')


class TestCLIIntegration(unittest.TestCase):
    """Integration tests for the CLI workflow"""
    
    def setUp(self):
        """Set up temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        # Create test config and actor as above
        test_config = {
            "server": {"domain": "cli-test.example.com"},
            "activitypub": {"namespace": "activitypub"},
            "security": {
                "public_key_file": "test_public.pem",
                "private_key_file": "test_private.pem"
            }
        }
        
        with open('config.json', 'w') as f:
            json.dump(test_config, f)
        
        os.makedirs('static', exist_ok=True)
        test_actor = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Person",
            "id": "https://cli-test.example.com/activitypub/actor"
        }
        
        with open('static/actor.json', 'w') as f:
            json.dump(test_actor, f)
    
    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)
    
    def test_cli_workflow(self):
        """Test the complete CLI workflow"""
        # Import and run the CLI functions
        sys.path.insert(0, self.original_cwd)
        from post_utils import create_post, create_activity, regenerate_outbox
        
        # Simulate CLI command
        title = "CLI Test Post"
        content = "Testing CLI workflow"
        url = "https://myblog.com/cli-test"
        
        # Run the workflow
        post_obj, post_id = create_post('article', title, content, url)
        activity_obj, activity_id = create_activity(post_obj, post_id)
        regenerate_outbox()
        
        # Verify all files were created
        self.assertTrue(os.path.exists(f'static/posts/{post_id}.json'))
        self.assertTrue(os.path.exists(f'static/activities/{activity_id}.json'))
        self.assertTrue(os.path.exists('static/outbox.json'))
        
        # Verify outbox contains the new post
        with open('static/outbox.json', 'r') as f:
            outbox = json.load(f)
        
        self.assertEqual(outbox['totalItems'], 1)
        self.assertEqual(outbox['orderedItems'][0]['object'], f"https://cli-test.example.com/activitypub/posts/{post_id}")

    def test_cli_note_workflow(self):
        """Test the complete CLI workflow for Note posts"""
        # Import and run the CLI functions
        sys.path.insert(0, self.original_cwd)
        from post_utils import create_post, create_activity, regenerate_outbox

        # Simulate CLI command for Note (no title required)
        content = "Just published a new blog post about ActivityPub federation!"
        url = "https://myblog.com/activitypub-post"

        # Run the workflow with Note type
        post_obj, post_id = create_post('note', None, content, url)
        activity_obj, activity_id = create_activity(post_obj, post_id)
        regenerate_outbox()

        # Verify all files were created
        self.assertTrue(os.path.exists(f'static/posts/{post_id}.json'))
        self.assertTrue(os.path.exists(f'static/activities/{activity_id}.json'))
        self.assertTrue(os.path.exists('static/outbox.json'))

        # Verify post is a Note type
        with open(f'static/posts/{post_id}.json', 'r') as f:
            post = json.load(f)
        self.assertEqual(post['type'], 'Note')
        self.assertEqual(post['content'], content)
        self.assertNotIn('name', post)  # No title for Note

        # Verify outbox contains the new post
        with open('static/outbox.json', 'r') as f:
            outbox = json.load(f)

        self.assertEqual(outbox['totalItems'], 1)
        self.assertEqual(outbox['orderedItems'][0]['object'], f"https://cli-test.example.com/activitypub/posts/{post_id}")


if __name__ == '__main__':
    # Add the current directory to Python path for imports
    sys.path.insert(0, '.')
    unittest.main()