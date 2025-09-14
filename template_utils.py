#!/usr/bin/env python3
"""
Templating utilities for ActivityPub entities using Jinja2
"""
import json
import os
from jinja2 import Environment, FileSystemLoader


class ActivityPubTemplates:
    """Template manager for ActivityPub entities"""

    def __init__(self, template_dir='templates'):
        """Initialize template environment"""
        # Get absolute path to templates directory relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, template_dir)

        self.env = Environment(
            loader=FileSystemLoader(template_path),
            trim_blocks=True,
            lstrip_blocks=True
        )

    def render_json_template(self, template_name, **context):
        """
        Render a JSON template with the given context

        Args:
            template_name: Template file path (e.g., 'activitypub/actor.json.j2')
            **context: Template variables

        Returns:
            dict: Parsed JSON object
        """
        template = self.env.get_template(template_name)
        json_str = template.render(**context)
        return json.loads(json_str)

    def render_actor(self, config, public_key_pem=None):
        """
        Render actor template from config

        Args:
            config: Configuration dictionary
            public_key_pem: Public key PEM string

        Returns:
            dict: Actor JSON object
        """
        protocol = config['server'].get('protocol', 'https')
        template_data = {
            'website_url': f"{protocol}://{config['server']['domain']}",
            'namespace': config['activitypub']['namespace'],
            'username': config['activitypub']['username'],
            'actor_name': config['activitypub']['actor_name'],
            'actor_summary': config['activitypub']['actor_summary'],
            'public_key_pem': public_key_pem,
            'icon': config['activitypub'].get('icon'),
            'image': config['activitypub'].get('image')
        }

        return self.render_json_template('objects/actor.json.j2', **template_data)

    def render_article(self, config, post_id, title, content, post_url, summary=None, published=None):
        """
        Render article template

        Args:
            config: Configuration dictionary
            post_id: Post ID
            title: Post title
            content: Post content
            post_url: External URL for the post
            summary: Optional post summary
            published: Published timestamp

        Returns:
            dict: Post JSON object
        """
        protocol = config['server'].get('protocol', 'https')
        template_data = {
            'website_url': f"{protocol}://{config['server']['domain']}",
            'namespace': config['activitypub']['namespace'],
            'post_id': post_id,
            'title': title,
            'content': content,
            'post_url': post_url,
            'summary': summary,
            'published': published
        }

        return self.render_json_template('objects/article.json.j2', **template_data)

    def render_note(self, config, post_id, content, post_url, summary=None, published=None):
        """
        Render note template

        Args:
            config: Configuration dictionary
            post_id: Post ID
            content: Post content (Note doesn't typically have a title)
            post_url: External URL for the post
            summary: Optional post summary
            published: Published timestamp

        Returns:
            dict: Note JSON object
        """
        protocol = config['server'].get('protocol', 'https')
        template_data = {
            'website_url': f"{protocol}://{config['server']['domain']}",
            'namespace': config['activitypub']['namespace'],
            'post_id': post_id,
            'content': content,
            'post_url': post_url,
            'summary': summary,
            'published': published
        }

        return self.render_json_template('objects/note.json.j2', **template_data)

    def render_create_activity(self, activity_id, actor_id, published, post_object):
        """
        Render Create activity template

        Args:
            activity_id: Activity ID
            actor_id: Actor ID performing the activity
            published: Published timestamp
            post_object: The object being created (post/article)

        Returns:
            dict: Create activity JSON object
        """
        template_data = {
            'activity_id': activity_id,
            'actor_id': actor_id,
            'published': published,
            'object': post_object
        }

        return self.render_json_template('activities/create.json.j2', **template_data)

    def render_outbox_streaming(self, outbox_id, activities_dir, output_path):
        """
        Render outbox collection template with streaming for memory efficiency

        Args:
            outbox_id: Outbox collection ID
            activities_dir: Directory containing activity files
            output_path: Path to write outbox file

        Returns:
            int: Number of activities processed
        """
        import os

        valid_count = 0

        def activity_generator():
            """Generator that yields activity references one at a time"""
            nonlocal valid_count
            activity_files = [f for f in sorted(os.listdir(activities_dir), reverse=True) if f.endswith('.json')]

            for filename in activity_files:
                filepath = os.path.join(activities_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        activity = json.load(f)

                    # Create activity reference (only current activity in memory)
                    yield {
                        "type": activity["type"],
                        "id": activity["id"],
                        "actor": activity["actor"],
                        "published": activity["published"],
                        "object": activity["object"]["id"] if isinstance(activity["object"], dict) else activity["object"]
                    }
                    valid_count += 1

                except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                    print(f"Warning: Skipping malformed activity file: {filepath} - {e}")
                    continue

        # Count activities for totalItems (quick directory scan)
        activity_count = 0
        if os.path.exists(activities_dir):
            activity_count = len([f for f in os.listdir(activities_dir) if f.endswith('.json')])

        # Get template and create stream
        template = self.env.get_template('collections/outbox.json.j2')
        stream = template.stream(
            outbox_id=outbox_id,
            total_items=activity_count,
            activity_generator=activity_generator()
        )

        # Write stream to file
        with open(output_path, 'w') as f:
            for chunk in stream:
                f.write(chunk)

        # If valid count differs from total count, fix the totalItems field
        if valid_count != activity_count:
            self._fix_outbox_total_count(output_path, activity_count, valid_count)

        return valid_count

    def _fix_outbox_total_count(self, output_path, expected_count, actual_count):
        """
        Private method to fix totalItems count in outbox file when malformed activities are skipped

        Args:
            output_path: Path to the outbox file
            expected_count: Original count of JSON files
            actual_count: Actual count of valid activities processed
        """
        print(f"Correcting totalItems from {expected_count} to {actual_count}")

        # Read the generated file and fix totalItems
        with open(output_path, 'r') as f:
            content = f.read()

        # Replace the totalItems value using regex
        import re
        content = re.sub(
            r'"totalItems":\s*\d+',
            f'"totalItems": {actual_count}',
            content
        )

        # Write corrected file
        with open(output_path, 'w') as f:
            f.write(content)


# Global instance
templates = ActivityPubTemplates()
