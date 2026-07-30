#!/usr/bin/env python3
"""
Shared test configuration utilities for tinyFedi ActivityPub server tests
"""
import os
import tempfile
import shutil
import json
import sys


class TestConfigMixin:
    """
    Mixin class providing standardized test configuration and setup for ActivityPub tests.

    This mixin ensures proper test isolation by:
    - Creating isolated temporary directories for each test
    - Generating test-specific configuration files with unique namespaces
    - Force-reloading the app module to clear cached global variables
    - Providing helper methods for file operations and assertions
    - Cleaning up resources after each test

    ## Test Isolation Strategy

    The key to proper test isolation is ensuring each test gets its own:
    1. **Temporary directory**: Created with tempfile.mkdtemp()
    2. **Config namespace**: Uses test name (e.g., "flask_app", "inbox_functionality")
    3. **Directory structure**: All paths under static/tests/{test_name}/
    4. **Fresh app module**: Forces Python to reload app.py and clear globals

    ## Module Reload Mechanism

    When setup_test_environment() runs, it:
    1. Changes to a fresh temporary directory
    2. Creates a new config.json with test-specific paths
    3. Forces importlib.reload(app) to clear cached global variables
    4. This ensures each test gets a fresh app configuration

    ## Usage Patterns

    ### Basic Usage:
        class MyTest(unittest.TestCase, TestConfigMixin):
            def setUp(self):
                self.setup_test_environment("my_test")

            def tearDown(self):
                self.teardown_test_environment()

    ### With Configuration Overrides:
        def setUp(self):
            self.setup_test_environment("my_test",
                server={"domain": "custom.example.com"},
                activitypub={"username": "customuser"})

    ### Import Order Requirement:
        def test_something(self):
            # IMPORTANT: Import app functions AFTER setUp() runs
            # This ensures you get the reloaded module with fresh config
            from app import save_inbox_activity

            # NOT like this (imports before setup):
            # from app import save_inbox_activity  # ❌ Gets old cached config
            # class MyTest...

    ## Helper Methods

    - get_test_file_path(directory_type, filename): Get full path to test file
    - assert_file_exists(directory_type, filename): Assert file exists in test dirs
    - assert_file_count(directory_type, expected_count): Assert number of files
    - create_test_actor(actor_name): Create actor.json for tests

    ## Directory Types

    Available directory types for helper methods:
    - "inbox": For incoming ActivityPub activities
    - "data_root": For actor.json, webfinger.json
    - "outbox": For outbox activity files
    - "posts": For Note/Article objects
    - "outbox": For outbox activity files (Create/Accept/Update)
    """

    def create_test_config(self, test_name="test", **overrides):
        """Create a standardized test configuration

        Args:
            test_name: Name for this test (used in paths)
            **overrides: Any config values to override

        Returns:
            dict: Test configuration
        """
        base_test_dir = f"static/tests/{test_name}"

        config = {
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
                "auto_accept_follow_requests": True,
                "max_page_size": 20
            },
            "security": {
                "public_key_file": "test.pem",
                "private_key_file": "test.pem"
            },
            "directories": {
                "inbox": f"{base_test_dir}/inbox",
                "data_root": f"{base_test_dir}",
                "outbox": f"{base_test_dir}/outbox",
                "posts_local": f"{base_test_dir}/posts/local",
                "posts_remote": f"{base_test_dir}/posts/remote"
            }
        }

        # Apply any overrides
        for key, value in overrides.items():
            if key in config:
                if isinstance(value, dict) and isinstance(config[key], dict):
                    config[key].update(value)
                else:
                    config[key] = value

        return config

    def setup_test_environment(self, test_name="test", **config_overrides):
        """Set up isolated test environment with proper cleanup

        Args:
            test_name: Name for this test (used in paths)
            **config_overrides: Any config values to override

        Returns:
            dict: Test configuration
        """
        # Create temporary directory and change to it
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        sys.path.insert(0, self.original_cwd)

        # Create test configuration
        self.config = self.create_test_config(test_name, **config_overrides)

        # Write config file
        with open('config.json', 'w') as f:
            json.dump(self.config, f, indent=2)

        # Force reload app module to pick up new config
        # This ensures test isolation by clearing cached global variables
        if 'app' in sys.modules:
            import importlib
            importlib.reload(sys.modules['app'])

        # Create test key files
        with open('test.pem', 'w') as f:
            f.write('test key content')

        # Create and clean test directories
        self.create_and_clean_directories()

        return self.config

    def create_and_clean_directories(self):
        """Remove data_root if it exists, then create all directories fresh"""
        data_root = self.config['directories']['data_root']
        if os.path.exists(data_root):
            shutil.rmtree(data_root)
        for dir_path in self.config['directories'].values():
            os.makedirs(dir_path, exist_ok=True)
        # Derived queue directory (not in config, lives inside inbox)
        os.makedirs(os.path.join(self.config['directories']['inbox'], 'queue'), exist_ok=True)

    def teardown_test_environment(self):
        """Clean up test environment"""
        if hasattr(self, 'original_cwd'):
            os.chdir(self.original_cwd)
        if hasattr(self, 'test_dir'):
            shutil.rmtree(self.test_dir)

    def create_test_actor(self, actor_name="Test Actor"):
        """Create a test actor.json file in the appropriate directory"""
        test_actor = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": "Person",
            "id": f"https://{self.config['server']['domain']}/{self.config['activitypub']['namespace']}/actor",
            "preferredUsername": self.config['activitypub']['username'],
            "name": actor_name
        }

        # Use the data_root directory (base dir for actor, webfinger, etc.)
        actor_file = os.path.join(self.config['directories']['data_root'], 'actor.json')
        with open(actor_file, 'w') as f:
            json.dump(test_actor, f, indent=2)

        return test_actor

    def get_test_file_path(self, directory_type, filename):
        """Get the full path for a test file in a configured directory

        Args:
            directory_type: Key from config['directories'] (e.g., 'posts', 'outbox')
            filename: Name of the file

        Returns:
            str: Full path to the file
        """
        return os.path.join(self.config['directories'][directory_type], filename)

    def assert_file_exists(self, directory_type, filename):
        """Assert that a file exists in the specified directory"""
        file_path = self.get_test_file_path(directory_type, filename)
        self.assertTrue(os.path.exists(file_path), f"File {filename} should exist in {directory_type} directory at {file_path}")

    def assert_file_count(self, directory_type, expected_count, file_pattern="*"):
        """Assert the number of files in a directory

        Args:
            directory_type: Key from config['directories']
            expected_count: Expected number of files
            file_pattern: Pattern to match (default: all files)
        """
        files = self.get_files_in_directory(directory_type, file_pattern)
        self.assertEqual(len(files), expected_count,
                        f"Expected {expected_count} files in {directory_type}, found {len(files)}: {files}")

    def get_files_in_directory(self, directory_type, file_pattern="*"):
        """Get list of files in a configured directory

        Args:
            directory_type: Key from config['directories']
            file_pattern: Pattern to match (default: all files)

        Returns:
            list: List of filenames (not full paths)
        """
        import glob
        dir_path = self.config['directories'][directory_type]
        if file_pattern == "*":
            # Get only files, not directories
            files = [f for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))]
        else:
            pattern_path = os.path.join(dir_path, file_pattern)
            files = glob.glob(pattern_path)
            files = [os.path.basename(f) for f in files if os.path.isfile(f)]

        return files

    def get_single_file_in_directory(self, directory_type, file_pattern="*"):
        """Get the single file in a directory (asserts there's exactly one)

        Args:
            directory_type: Key from config['directories']
            file_pattern: Pattern to match (default: all files)

        Returns:
            str: Filename of the single file
        """
        files = self.get_files_in_directory(directory_type, file_pattern)
        self.assertEqual(len(files), 1,
                        f"Expected exactly 1 file in {directory_type}, found {len(files)}: {files}")
        return files[0]

    def generate_test_rsa_keys(self):
        """Generate RSA key pair for HTTP signature testing

        Returns:
            tuple: (private_key_pem, public_key_pem) as strings
        """
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.backends import default_backend

        # Generate test keys
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()

        # Export to PEM format
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        public_key_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')

        return private_key_pem, public_key_pem

    # --- Test client helpers ---

    def setup_test_client(self):
        """Import app, create test client, and write actor config."""
        from unittest.mock import patch
        from app import app, write_actor_config
        self.app = app
        self.client = app.test_client()
        app.config['TESTING'] = True
        with patch('builtins.print'):
            write_actor_config()

    def setup_webfinger(self):
        """Create webfinger.json for the test actor."""
        import json
        domain = self.config['server']['domain']
        username = self.config['activitypub']['username']
        namespace = self.config['activitypub']['namespace']

        webfinger = {
            "subject": f"acct:{username}@{domain}",
            "links": [{
                "rel": "self",
                "type": "application/activity+json",
                "href": f"https://{domain}/{namespace}/actor"
            }]
        }
        path = self.get_test_file_path('data_root', 'webfinger.json')
        with open(path, 'w') as f:
            json.dump(webfinger, f)

    def auth_headers(self, token=None):
        """Return standard auth + Accept headers for C2S requests.

        Args:
            token: Bearer token (defaults to config['security']['c2s_token'])

        Returns:
            dict: Headers dict
        """
        if token is None:
            token = self.config['security'].get('c2s_token', '')
        return {
            'Authorization': f'Bearer {token}',
            'Accept': 'application/activity+json'
        }

    def create_local_post(self, uuid, title, content, obj_type='Article', **extra):
        """Create a local post file directly on disk for testing.

        Stores at posts_local/{uuid}/post.json, mirroring the CLI's create_post().

        Args:
            uuid: Post UUID
            title: Post title (used as 'name')
            content: Post content
            obj_type: AS2 type (default 'Article')
            **extra: Additional fields to include in the post object

        Returns:
            dict: The post object
        """
        import os
        posts_dir = self.config['directories']['posts_local']
        post_dir = os.path.join(posts_dir, uuid)
        os.makedirs(post_dir, exist_ok=True)

        post = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": obj_type,
            "id": f"https://{self.config['server']['domain']}/{self.config['activitypub']['namespace']}/posts/{uuid}",
            "name": title,
            "content": content,
            "published": "2026-03-20T10:00:00Z"
        }
        post.update(extra)

        with open(os.path.join(post_dir, 'post.json'), 'w') as f:
            json.dump(post, f)

        return post

    def create_remote_post(self, actor_domain, actor_path, object_id, obj_type, content,
                           name=None, tag=None, **extra):
        """Create a remote post file directly on disk for testing.

        Mirrors CreateProcessor._store_remote_post(): stores at
        posts_remote/{actor_domain}/{actor_path}/{object_id}/object.json + metadata.json.

        Args:
            actor_domain: Domain of the remote actor (e.g. 'mastodon.social')
            actor_path: Path of the remote actor (e.g. 'users/alice')
            object_id: ID of the object (e.g. '12345')
            obj_type: AS2 type (e.g. 'Note', 'Article')
            content: Object content
            name: Optional title (for Article type)
            tag: Optional list of tag objects
            **extra: Additional fields to include in the object

        Returns:
            dict: The object as stored
        """
        import os
        import json
        url_path = f"{actor_domain}/{actor_path}/{object_id}"
        remote_dir = os.path.join(self.config['directories']['posts_remote'], url_path)
        os.makedirs(remote_dir, exist_ok=True)

        obj = {
            "@context": "https://www.w3.org/ns/activitystreams",
            "type": obj_type,
            "id": f"https://{actor_domain}/{actor_path}/{object_id}",
            "attributedTo": f"https://{actor_domain}/{actor_path}",
            "content": content,
            "published": "2026-03-20T10:00:00Z",
            "to": ["https://www.w3.org/ns/activitystreams#Public"],
            "cc": [f"https://{actor_domain}/{actor_path}/followers"]
        }
        if name:
            obj["name"] = name
        if tag:
            obj["tag"] = tag
        obj.update(extra)

        with open(os.path.join(remote_dir, 'object.json'), 'w') as f:
            json.dump(obj, f)

        metadata = {
            "signed_by": f"https://{actor_domain}/{actor_path}#main-key",
            "received_at": obj["published"],
            "accepted_by_rule": "is_following"
        }
        with open(os.path.join(remote_dir, 'metadata.json'), 'w') as f:
            json.dump(metadata, f)

        return obj