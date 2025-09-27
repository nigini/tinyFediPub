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
    - "outbox": For actor.json, outbox.json, webfinger.json
    - "posts": For Note/Article objects
    - "activities": For Create/Accept/Follow activities
    - "followers": For followers.json
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
                "auto_accept_follow_requests": True
            },
            "security": {
                "public_key_file": "test.pem",
                "private_key_file": "test.pem"
            },
            "directories": {
                "inbox": f"{base_test_dir}/inbox",
                "inbox_queue": f"{base_test_dir}/inbox/queue",
                "outbox": f"{base_test_dir}",
                "posts": f"{base_test_dir}/posts",
                "activities": f"{base_test_dir}/activities",
                "followers": f"{base_test_dir}"
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
        """Create all configured directories and clean any existing files"""
        for dir_path in self.config['directories'].values():
            os.makedirs(dir_path, exist_ok=True)
            # Clean any existing files
            if os.path.exists(dir_path):
                for f in os.listdir(dir_path):
                    file_path = os.path.join(dir_path, f)
                    if os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isfile(file_path):
                        os.remove(file_path)
                    elif os.path.isdir(file_path):
                        # Only remove if it's empty (avoid removing nested test dirs)
                        try:
                            os.rmdir(file_path)
                        except OSError:
                            pass  # Directory not empty, leave it

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

        # Use the outbox directory (which is the base static dir for actors)
        actor_file = os.path.join(self.config['directories']['outbox'], 'actor.json')
        with open(actor_file, 'w') as f:
            json.dump(test_actor, f, indent=2)

        return test_actor

    def get_test_file_path(self, directory_type, filename):
        """Get the full path for a test file in a configured directory

        Args:
            directory_type: Key from config['directories'] (e.g., 'posts', 'activities')
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