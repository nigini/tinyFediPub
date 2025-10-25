#!/usr/bin/env python3
"""
Utilities for creating ActivityPub posts
"""
import json
import os
import re
from datetime import datetime, UTC
from template_utils import templates

def load_config():
    """Load configuration from config.json"""
    try:
        with open('config.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print("❌ Error: config.json not found!")
        print("Please copy the example configuration file and customize it:")
        print("  cp config.json.example config.json")
        print("Then edit config.json with your domain and settings.")
        raise SystemExit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Error: config.json is not valid JSON: {e}")
        print("Please check the file format and try again.")
        raise SystemExit(1)

def slugify(text):
    """Convert text to URL-safe slug"""
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')[:30]  # Limit length

def generate_post_id(title=None):
    """
    Generate post ID with timestamp + optional title suffix

    Args:
        title: Optional title to create suffix from

    Returns:
        str: Post ID like '20250913-143022' or '20250913-143022-my-post'
    """
    timestamp = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')

    if title:
        suffix = slugify(title)
        if suffix:
            return f"{timestamp}-{suffix}"

    return timestamp

def generate_base_url(config):
    """
    Generate base ActivityPub URL from config

    Args:
        config: Configuration dictionary

    Returns:
        str: Base URL like 'https://example.com/activitypub'
    """
    protocol = config['server'].get('protocol', 'https')
    domain = config['server']['domain']
    namespace = config['activitypub']['namespace']
    return f"{protocol}://{domain}/{namespace}"

def get_followers_list(config):
    """
    Get current followers list from followers.json

    Args:
        config: Configuration dictionary

    Returns:
        list: List of follower actor URLs
    """
    import json
    import os

    followers_dir = config['directories']['followers']
    followers_path = os.path.join(followers_dir, 'followers.json')

    # Ensure directory exists
    os.makedirs(followers_dir, exist_ok=True)

    # Load existing followers or return empty list
    if os.path.exists(followers_path):
        with open(followers_path, 'r') as f:
            followers_data = json.load(f)
        return followers_data.get('items', [])
    else:
        return []

def generate_activity_id(activity_type):
    """
    Generate activity ID with timestamp + type

    Args:
        activity_type: Activity type (e.g., 'create', 'accept', 'follow')

    Returns:
        str: Activity ID like 'create-20250921-143022' or 'accept-20250921-143022'
    """
    timestamp = datetime.now(UTC).strftime('%Y%m%d-%H%M%S')
    return f"{activity_type.lower()}-{timestamp}"

def parse_actor_url(actor_url):
    """
    Extract useful information from actor URL

    Args:
        actor_url: Actor URL (e.g., 'https://mastodon.social/users/alice')

    Returns:
        tuple: (domain, username) where username may be None if not extractable
    """
    if not actor_url or not isinstance(actor_url, str):
        return ('unknown', None)

    try:
        from urllib.parse import urlparse
        parsed = urlparse(actor_url)
        domain = parsed.netloc or 'unknown'

        # Try to extract username from common ActivityPub URL patterns
        username = None
        path = parsed.path.strip('/')
        if path:
            # Common patterns: /users/alice, /@alice, /u/alice
            if path.startswith('users/'):
                parts = path.split('/')
                if len(parts) >= 2:
                    username = parts[1]  # Take the part right after 'users'
            elif path.startswith('@'):
                username = path[1:]
            elif path.startswith('u/'):
                parts = path.split('/')
                if len(parts) >= 2:
                    username = parts[1]  # Take the part right after 'u'

        return (domain, username)

    except Exception:
        return ('unknown', None)

def create_post(post_type, title, content, url, summary=None, post_id=None):
    """
    Create a post JSON object and save to file

    Args:
        post_type: Type of post ('article' or 'note')
        title: Post title (required for articles, optional for notes)
        content: Post content
        url: Full URL where post can be read (e.g., blog post URL)
        summary: Optional summary
        post_id: Custom post ID, auto-generated if None

    Returns:
        tuple: (post_object, post_id)
    """
    import os
    
    config = load_config()
    
    # Generate post ID if not provided
    if post_id is None:
        post_id = generate_post_id(title)

    # Generate published timestamp
    published = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Create post object using appropriate template
    if post_type == 'article':
        post = templates.render_article(
            config=config,
            post_id=post_id,
            title=title,
            content=content,
            post_url=url,
            summary=summary,
            published=published
        )
    else:  # note (default)
        post = templates.render_note(
            config=config,
            post_id=post_id,
            content=content,
            post_url=url,
            summary=summary,
            published=published
        )
    
    # Save post file
    config = load_config()
    posts_dir = config['directories']['posts']
    os.makedirs(posts_dir, exist_ok=True)
    post_path = os.path.join(posts_dir, f'{post_id}.json')
    with open(post_path, 'w') as f:
        json.dump(post, f, indent=2)
    print(f"✓ Created post: {post_path}")
    
    return post, post_id

def update_post(post_id, title=None, content=None, url=None, summary=None):
    """
    Update an existing post and add 'updated' timestamp

    Args:
        post_id: Post ID to update
        title: New title (None to keep existing)
        content: New content (None to keep existing)
        url: New URL (None to keep existing)
        summary: New summary (None to keep existing)

    Returns:
        tuple: (updated_post_object, post_id, was_modified)
        where was_modified is True if any changes were made
    """
    import os

    config = load_config()
    posts_dir = config['directories']['posts']
    post_path = os.path.join(posts_dir, f'{post_id}.json')

    # Load existing post
    if not os.path.exists(post_path):
        raise FileNotFoundError(f"Post not found: {post_id}")

    with open(post_path, 'r') as f:
        post = json.load(f)

    # Check if any changes are being made
    has_changes = any([
        title is not None,
        content is not None,
        url is not None,
        summary is not None
    ])

    # If no changes, return unchanged post
    if not has_changes:
        return post, post_id, False

    # Update fields if provided
    if title is not None:
        post['name'] = title
    if content is not None:
        post['content'] = content
    if url is not None:
        post['url'] = url
    if summary is not None:
        post['summary'] = summary

    # Add updated timestamp
    post['updated'] = datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')

    # Save updated post
    with open(post_path, 'w') as f:
        json.dump(post, f, indent=2)
    print(f"✓ Updated post: {post_path}")

    return post, post_id, True

def get_actor_info():
    """
    Get actor information from generated actor.json

    Returns:
        dict: Actor object with id, etc.
    """
    try:
        config = load_config()
        outbox_dir = config['directories']['outbox']
        actor_file = os.path.join(outbox_dir, 'actor.json')
        with open(actor_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback: generate from config if actor.json doesn't exist
        print("Warning: actor.json not found. Run the server first to generate it.")
        return None

def save_activity_file(activity, activity_id, config):
    """
    Save activity object to file

    Args:
        activity: Activity object to save
        activity_id: Activity ID (filename without extension)
        config: Configuration dictionary

    Returns:
        str: Path to saved activity file
    """
    import os

    activities_dir = config['directories']['activities']
    os.makedirs(activities_dir, exist_ok=True)
    activity_path = os.path.join(activities_dir, f'{activity_id}.json')

    with open(activity_path, 'w') as f:
        json.dump(activity, f, indent=2)

    return activity_path

def create_activity(post_object, post_id):
    """
    Create a Create activity that wraps the post and save to file
    
    Args:
        post_object: The post object from create_post()
        post_id: The post ID
        
    Returns:
        tuple: (activity_object, activity_id)
    """
    import os
    
    # Get configuration and actor info
    config = load_config()
    actor = get_actor_info()
    if not actor:
        raise Exception("Cannot create activity: actor.json not found. Please run the server first.")

    # Generate activity ID
    activity_id = generate_activity_id('create')

    # Get base URL and actor ID
    base_url = generate_base_url(config)
    actor_id = actor['id']

    # Create activity object using template
    activity = templates.render_create_activity(
        activity_id=f"{base_url}/activities/{activity_id}",
        actor_id=actor_id,
        published=post_object["published"],
        post_object=post_object
    )

    # Save activity file
    activity_path = save_activity_file(activity, activity_id, config)
    print(f"✓ Created activity: {activity_path}")

    return activity, activity_id

def create_update_activity(post_object, post_id):
    """
    Create an Update activity that wraps the updated post and save to file

    Args:
        post_object: The updated post object from update_post()
        post_id: The post ID

    Returns:
        tuple: (activity_object, activity_id)
    """
    # Get configuration and actor info
    config = load_config()
    actor = get_actor_info()
    if not actor:
        raise Exception("Cannot create activity: actor.json not found. Please run the server first.")

    # Generate activity ID
    activity_id = generate_activity_id('update')

    # Get base URL and actor ID
    base_url = generate_base_url(config)
    actor_id = actor['id']

    # Create activity object using template (use 'updated' timestamp if available)
    published_time = post_object.get("updated", post_object["published"])
    activity = templates.render_update_activity(
        activity_id=f"{base_url}/activities/{activity_id}",
        actor_id=actor_id,
        published=published_time,
        post_object=post_object
    )

    # Save activity file
    activity_path = save_activity_file(activity, activity_id, config)
    print(f"✓ Created Update activity: {activity_path}")

    return activity, activity_id

def regenerate_outbox():
    """
    Regenerate outbox.json by streaming activities directory using template generator
    Memory efficient - only loads one activity at a time
    """
    import os

    actor = get_actor_info()
    if not actor:
        raise Exception("Cannot generate outbox: actor.json not found")

    base_url = actor['id'].rsplit('/actor', 1)[0]
    config = load_config()
    activities_dir = config['directories']['activities']
    outbox_dir = config['directories']['outbox']
    outbox_path = os.path.join(outbox_dir, 'outbox.json')

    # Ensure directories exist
    os.makedirs(outbox_dir, exist_ok=True)

    # Use streaming template rendering
    activity_count = templates.render_outbox_streaming(
        outbox_id=f"{base_url}/outbox",
        activities_dir=activities_dir,
        output_path=outbox_path
    )

    print(f"✓ Regenerated outbox with {activity_count} activities (streaming)")