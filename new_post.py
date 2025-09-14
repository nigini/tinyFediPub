#!/usr/bin/env python3
"""
CLI tool for creating new ActivityPub posts
"""
import argparse
import sys
from post_utils import create_post, create_activity, regenerate_outbox

def main():
    parser = argparse.ArgumentParser(description='Create a new ActivityPub post')
    parser.add_argument('--type', choices=['note', 'article'], default='note', help='Post type: note for short posts, article for blog posts (default: note)')
    parser.add_argument('--title', help='Post title (required for articles, not used for notes per ActivityStreams spec)')
    parser.add_argument('--content', required=True, help='Post content')
    parser.add_argument('--url', required=True, help='Full URL where post can be read')
    parser.add_argument('--summary', help='Optional post summary')
    parser.add_argument('--id', help='Custom post ID (default: auto-generated)')

    args = parser.parse_args()

    # Validation: articles require a title
    if args.type == 'article' and not args.title:
        print("❌ Error: --title is required for article posts")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Create post and activity
        post_obj, post_id = create_post(args.type, args.title, args.content, args.url, args.summary, args.id)
        activity_obj, activity_id = create_activity(post_obj, post_id)
        
        # Regenerate outbox
        regenerate_outbox()
        
        print(f"\n✅ Post created successfully!")
        print(f"Post ID: {post_id}")
        print(f"Activity ID: {activity_id}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()