#!/usr/bin/env python3
"""
Activity Delivery for TinyFedi ActivityPub Server

Delivers activities to remote actor inboxes with HTTP signature authentication.
"""

import json
import requests
from email.utils import formatdate
from typing import Optional, Dict
from urllib.parse import urlparse
import http_signatures


def load_config():
    """Load configuration from config.json"""
    with open('config.json') as f:
        return json.load(f)


def load_private_key(config: dict) -> str:
    """Load private key from configured file path"""
    private_key_file = config['security']['private_key_file']
    with open(private_key_file, 'r') as f:
        return f.read()


def get_user_agent(config: dict) -> str:
    """Get User-Agent string from config or default"""
    return config.get('server', {}).get('user_agent', 'TinyFedi/1.0')


def fetch_actor_inbox(actor_url: str, config: dict) -> Optional[str]:
    """
    Fetch the inbox URL for a remote actor

    Args:
        actor_url: Actor URL (e.g., 'https://mastodon.social/users/alice')
        config: Configuration dictionary

    Returns:
        str: Inbox URL or None if fetch fails
    """
    try:
        headers = {
            'Accept': 'application/activity+json, application/ld+json',
            'User-Agent': get_user_agent(config)
        }

        response = requests.get(actor_url, headers=headers, timeout=10)
        response.raise_for_status()
        actor_data = response.json()

        inbox_url = actor_data.get('inbox')
        if not inbox_url:
            print(f"Warning: No inbox found in actor document for {actor_url}")
            return None

        return inbox_url

    except Exception as e:
        print(f"Error fetching inbox for {actor_url}: {e}")
        return None


def deliver_activity(activity: dict, inbox_url: str, config: dict) -> bool:
    """
    Deliver an activity to a remote inbox with HTTP signature

    Args:
        activity: Activity object to deliver
        inbox_url: Target inbox URL
        config: Configuration dictionary

    Returns:
        bool: True if delivery succeeded, False otherwise
    """
    try:
        # Parse inbox URL to get host and path
        parsed = urlparse(inbox_url)
        host = parsed.netloc
        path = parsed.path
        if parsed.query:
            path += f"?{parsed.query}"

        # Prepare request
        body = json.dumps(activity).encode('utf-8')
        headers = {
            'Host': host,
            'Date': formatdate(timeval=None, localtime=False, usegmt=True),
            'Content-Type': 'application/activity+json',
            'User-Agent': get_user_agent(config)
        }

        # Load private key
        private_key_pem = load_private_key(config)

        # Get key ID from actor document
        from post_utils import get_actor_info
        actor = get_actor_info()
        if not actor or 'publicKey' not in actor:
            print("Error: Cannot find actor publicKey for signing")
            return False

        key_id = actor['publicKey']['id']

        # Sign the request
        signature_header = http_signatures.sign_request(
            method='POST',
            path=path,
            headers=headers,
            body=body,
            private_key_pem=private_key_pem,
            key_id=key_id
        )

        # Add signature to headers
        headers['Signature'] = signature_header

        # Send POST request
        response = requests.post(inbox_url, data=body, headers=headers, timeout=30)
        response.raise_for_status()

        print(f"✓ Successfully delivered activity to {inbox_url}")
        return True

    except Exception as e:
        print(f"✗ Failed to deliver activity to {inbox_url}: {e}")
        return False


def deliver_to_actor(activity: dict, actor_url: str, config: dict) -> bool:
    """
    Deliver activity to a single actor (fetches their inbox first)

    Args:
        activity: Activity object to deliver
        actor_url: Actor URL to deliver to
        config: Configuration dictionary

    Returns:
        bool: True if delivery succeeded, False otherwise
    """
    # Fetch actor's inbox URL
    inbox_url = fetch_actor_inbox(actor_url, config)
    if not inbox_url:
        return False

    # Deliver to inbox
    return deliver_activity(activity, inbox_url, config)


def deliver_to_followers(activity: dict, config: dict) -> Dict[str, bool]:
    """
    Deliver activity to all followers

    Args:
        activity: Activity object to deliver
        config: Configuration dictionary

    Returns:
        dict: Map of actor_url -> success boolean
    """
    from post_utils import get_followers_list

    followers = get_followers_list(config)
    if not followers:
        print("No followers to deliver to")
        return {}

    print(f"Delivering activity to {len(followers)} followers...")

    results = {}
    for actor_url in followers:
        print(f"Delivering to {actor_url}...")
        success = deliver_to_actor(activity, actor_url, config)
        results[actor_url] = success

    # Summary
    success_count = sum(1 for s in results.values() if s)
    print(f"\nDelivery complete: {success_count}/{len(followers)} succeeded")

    return results
