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

    def render_accept_activity(self, activity_id, actor_id, published, follow_object):
        """
        Render Accept activity template

        Args:
            activity_id: Activity ID
            actor_id: Actor ID performing the activity
            published: Published timestamp
            follow_object: The Follow activity being accepted

        Returns:
            dict: Accept activity JSON object
        """
        template_data = {
            'activity_id': activity_id,
            'actor_id': actor_id,
            'published': published,
            'object': follow_object
        }

        return self.render_json_template('activities/accept.json.j2', **template_data)

    def render_update_activity(self, activity_id, actor_id, published, post_object):
        """
        Render Update activity template

        Args:
            activity_id: Activity ID
            actor_id: Actor ID performing the activity
            published: Published timestamp
            post_object: The object being updated (post/article with 'updated' field)

        Returns:
            dict: Update activity JSON object
        """
        template_data = {
            'activity_id': activity_id,
            'actor_id': actor_id,
            'published': published,
            'object': post_object
        }

        return self.render_json_template('activities/update.json.j2', **template_data)

    def render_followers_collection(self, followers_id, followers_list=None):
        """
        Render followers collection template

        Args:
            followers_id: Collection ID
            followers_list: List of follower actor IDs (empty list if None)

        Returns:
            dict: Followers collection JSON object
        """
        if followers_list is None:
            followers_list = []

        template_data = {
            'followers_id': followers_id,
            'total_items': len(followers_list),
            'followers': followers_list
        }

        return self.render_json_template('collections/followers.json.j2', **template_data)

    def render_ordered_collection(self, collection_id, items=None):
        """
        Render a generic OrderedCollection template

        Args:
            collection_id: Collection ID (URL)
            items: List of items (URLs or objects). Empty list if None.

        Returns:
            dict: OrderedCollection JSON object
        """
        if items is None:
            items = []

        return self.render_json_template('collections/ordered_collection.json.j2',
            collection_id=collection_id,
            total_items=len(items),
            items=items
        )

    def render_likes_collection(self, likes_id, actors_list=None):
        """
        Render likes collection as an OrderedCollection

        Args:
            likes_id: Collection ID
            actors_list: List of actor URLs who liked the post (empty list if None)

        Returns:
            dict: OrderedCollection JSON object
        """
        if actors_list is None:
            actors_list = []
        return self.render_ordered_collection(likes_id, actors_list)

    def render_outbox_collection(self, outbox_id, total_items, items, next_page=None, prev_page=None):
        """
        Render outbox as OrderedCollection with items inline and optional pagination links

        Args:
            outbox_id: Outbox collection ID
            total_items: Total number of activities
            items: List of activity summary dicts for this page
            next_page: URL for next page, or None
            prev_page: URL for previous page, or None

        Returns:
            dict: OrderedCollection JSON object
        """
        return self.render_json_template('collections/outbox.json.j2',
            outbox_id=outbox_id,
            total_items=total_items,
            items=items,
            next_page=next_page,
            prev_page=prev_page
        )


# Global instance
templates = ActivityPubTemplates()
