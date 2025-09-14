#!/usr/bin/env python3
"""
Utilities for creating ActivityPub posts
"""
import json
import re
from datetime import datetime

def load_config():
    """Load configuration from config.json"""
    with open('config.json', 'r') as f:
        return json.load(f)

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

def create_post(title, content, url, summary=None, post_id=None):
    """
    Create a post JSON object and save to file
    
    Args:
        title: Post title
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
    
    # Build ActivityPub URLs
    domain = config['server']['domain']
    namespace = config['activitypub']['namespace']
    website_url = f"https://{domain}"
    
    # Create post object
    post = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Article",
        "id": f"{website_url}/{namespace}/posts/{post_id}",
        "url": url,  # User-provided URL
        "attributedTo": f"{website_url}/{namespace}/actor",
        "published": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "name": title,
        "content": content
    }
    
    if summary:
        post["summary"] = summary
    
    # Save post file
    posts_dir = 'static/posts'
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
        with open('static/actor.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        # Fallback: generate from config if actor.json doesn't exist
        print("Warning: static/actor.json not found. Run the server first to generate it.")
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
    activity_id = f"create-{post_id}"
    
    # Extract domain/namespace from actor ID
    actor_id = actor['id']
    base_url = actor_id.rsplit('/actor', 1)[0]  # Remove '/actor' suffix
    
    # Create activity object
    activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Create",
        "id": f"{base_url}/activities/{activity_id}",
        "actor": actor_id,
        "published": post_object["published"],  # Same timestamp as post
        "object": post_object
    }
    
    # Save activity file
    activities_dir = 'static/activities'
    os.makedirs(activities_dir, exist_ok=True)
    activity_path = os.path.join(activities_dir, f'{activity_id}.json')
    with open(activity_path, 'w') as f:
        json.dump(activity, f, indent=2)
    print(f"✓ Created activity: {activity_path}")
    
    return activity, activity_id

def regenerate_outbox():
    """
    Regenerate outbox.json by scanning activities directory
    Writes directly to file without loading all activities into memory
    """
    import os
    
    actor = get_actor_info()
    if not actor:
        raise Exception("Cannot generate outbox: actor.json not found")
    
    base_url = actor['id'].rsplit('/actor', 1)[0]
    activities_dir = 'static/activities'
    outbox_path = 'static/outbox.json'
    
    # Ensure static directory exists
    os.makedirs('static', exist_ok=True)
    
    # Count activities first
    activity_count = 0
    activity_files = []
    if os.path.exists(activities_dir):
        activity_files = [f for f in sorted(os.listdir(activities_dir), reverse=True) if f.endswith('.json')]
        activity_count = len(activity_files)
    
    # Write outbox file directly
    with open(outbox_path, 'w') as outbox_file:
        # Write outbox header
        outbox_file.write('{\n')
        outbox_file.write('  "@context": "https://www.w3.org/ns/activitystreams",\n')
        outbox_file.write('  "type": "OrderedCollection",\n')
        outbox_file.write(f'  "id": "{base_url}/outbox",\n')
        outbox_file.write(f'  "totalItems": {activity_count},\n')
        outbox_file.write('  "orderedItems": [\n')
        
        # Write each activity reference
        for i, filename in enumerate(activity_files):
            filepath = os.path.join(activities_dir, filename)
            try:
                with open(filepath, 'r') as f:
                    activity = json.load(f)
                
                # Create activity reference
                activity_ref = {
                    "type": activity["type"],
                    "id": activity["id"],
                    "actor": activity["actor"],
                    "published": activity["published"],
                    "object": activity["object"]["id"] if isinstance(activity["object"], dict) else activity["object"]
                }
                
                # Write activity reference (with comma except for last item)
                outbox_file.write('    ')
                json.dump(activity_ref, outbox_file, separators=(',', ':'))
                if i < len(activity_files) - 1:
                    outbox_file.write(',')
                outbox_file.write('\n')
                
            except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
                print(f"Warning: Skipping malformed activity file: {filepath} - {e}")
                continue
        
        # Close outbox
        outbox_file.write('  ]\n')
        outbox_file.write('}\n')
    
    print(f"✓ Regenerated outbox with {activity_count} activities")