#!/usr/bin/env python3
"""
Utilities for creating ActivityPub posts
"""
import json
import os
import re
from datetime import datetime
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
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')

    if title:
        suffix = slugify(title)
        if suffix:
            return f"{timestamp}-{suffix}"

    return timestamp

def generate_activity_id(activity_type):
    """
    Generate activity ID with timestamp + type

    Args:
        activity_type: Activity type (e.g., 'create', 'accept', 'follow')

    Returns:
        str: Activity ID like 'create-20250921-143022' or 'accept-20250921-143022'
    """
    timestamp = datetime.utcnow().strftime('%Y%m%d-%H%M%S')
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
    published = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

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
    
    # Get actor info from the actual served file
    actor = get_actor_info()
    if not actor:
        raise Exception("Cannot create activity: actor.json not found. Please run the server first.")

    # Generate activity ID
    activity_id = generate_activity_id('create')

    # Extract domain/namespace from actor ID
    actor_id = actor['id']
    base_url = actor_id.rsplit('/actor', 1)[0]  # Remove '/actor' suffix

    # Create activity object using template
    activity = templates.render_create_activity(
        activity_id=f"{base_url}/activities/{activity_id}",
        actor_id=actor_id,
        published=post_object["published"],
        post_object=post_object
    )
    
    # Save activity file
    config = load_config()
    activities_dir = config['directories']['activities']
    os.makedirs(activities_dir, exist_ok=True)
    activity_path = os.path.join(activities_dir, f'{activity_id}.json')
    with open(activity_path, 'w') as f:
        json.dump(activity, f, indent=2)
    print(f"✓ Created activity: {activity_path}")
    
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