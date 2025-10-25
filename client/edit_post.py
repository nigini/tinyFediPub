#!/usr/bin/env python3
"""
CLI tool for editing existing ActivityPub posts
"""
import argparse
import sys
import json
import os

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from post_utils import (
    load_config, update_post, create_update_activity,
    regenerate_outbox
)


def load_existing_post(post_id):
    """Load existing post from file"""
    config = load_config()
    posts_dir = config['directories']['posts']
    post_path = os.path.join(posts_dir, f'{post_id}.json')

    if not os.path.exists(post_path):
        print(f"❌ Error: Post '{post_id}' not found")
        return None

    with open(post_path, 'r') as f:
        return json.load(f)


def prompt_for_field(field_name, current_value):
    """
    Prompt user to update a field, showing current value

    Returns: new value or None if user wants to keep current
    """
    print(f"\n{field_name}:")
    print(f"  Current: {current_value if current_value else '(not set)'}")
    response = input(f"  New value (press Enter to keep current): ").strip()

    if response == "":
        return None  # Keep current value

    return response


def main():
    parser = argparse.ArgumentParser(description='Edit an existing ActivityPub post')
    parser.add_argument('--post-id', required=True, help='Post ID to edit')
    args = parser.parse_args()

    # Load existing post
    post = load_existing_post(args.post_id)
    if not post:
        sys.exit(1)

    print(f"\n📝 Editing post: {args.post_id}")
    print("=" * 50)

    # Prompt for each field
    new_title = prompt_for_field("Title", post.get('name'))
    new_content = prompt_for_field("Content", post.get('content'))
    new_url = prompt_for_field("URL", post.get('url'))
    new_summary = prompt_for_field("Summary", post.get('summary'))

    # Check if any changes were made
    if all(v is None for v in [new_title, new_content, new_url, new_summary]):
        print("\n❌ No changes made. Exiting.")
        sys.exit(0)

    # Confirm changes
    print("\n" + "=" * 50)
    print("Changes to be applied:")
    if new_title: print(f"  Title: {new_title}")
    if new_content: print(f"  Content: {new_content[:50]}...")
    if new_url: print(f"  URL: {new_url}")
    if new_summary: print(f"  Summary: {new_summary}")

    confirm = input("\nApply these changes? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled.")
        sys.exit(0)

    try:
        # Update the post
        updated_post, post_id, was_modified = update_post(
            args.post_id,
            title=new_title,
            content=new_content,
            url=new_url,
            summary=new_summary
        )

        # Check if any changes were actually made
        if not was_modified:
            print("\n❌ No changes made. Exiting.")
            sys.exit(0)

        # Create Update activity
        activity_obj, activity_id = create_update_activity(updated_post, post_id)
        print(f"Activity ID: {activity_id}")

        # Regenerate outbox
        regenerate_outbox()

        # Deliver to followers
        print("\n📤 Delivering to followers...")
        import activity_delivery
        config = load_config()
        delivery_results = activity_delivery.deliver_to_followers(activity_obj, config)

        # Show delivery summary
        if delivery_results:
            success_count = sum(1 for s in delivery_results.values() if s)
            total_count = len(delivery_results)
            print(f"✅ Delivered to {success_count}/{total_count} followers")

        print(f"\n✅ Post updated successfully!")

    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
