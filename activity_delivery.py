#!/usr/bin/env python3
"""
Activity Delivery for TinyFedi ActivityPub Server

Delivers activities to remote actor inboxes with HTTP signature authentication.
"""

import json
from typing import Optional, Dict
import http_signatures


def load_config():
    """Load configuration from config.json"""
    with open('config.json') as f:
        return json.load(f)


def fetch_actor_inbox(actor_url: str, config: dict) -> Optional[str]:
    """
    Fetch the inbox URL for a remote actor using a signed GET.

    Args:
        actor_url: Actor URL (e.g., 'https://mastodon.social/users/alice')
        config: Configuration dictionary

    Returns:
        str: Inbox URL or None if fetch fails
    """
    actor_data = http_signatures.signed_get(actor_url, config)
    if not actor_data:
        return None

    inbox_url = actor_data.get('inbox')
    if not inbox_url:
        print(f"Warning: No inbox found in actor document for {actor_url}")
        return None

    return inbox_url


def deliver_activity(activity: dict, inbox_url: str, config: dict) -> bool:
    """
    Deliver an activity to a remote inbox with HTTP signature.

    Args:
        activity: Activity object to deliver
        inbox_url: Target inbox URL
        config: Configuration dictionary

    Returns:
        bool: True if delivery succeeded, False otherwise
    """
    return http_signatures.signed_post(inbox_url, activity, config)


def deliver_to_actor(activity: dict, actor_url: str, config: dict) -> bool:
    """
    Deliver activity to a single actor (fetches their inbox first).

    Args:
        activity: Activity object to deliver
        actor_url: Actor URL to deliver to
        config: Configuration dictionary

    Returns:
        bool: True if delivery succeeded, False otherwise
    """
    inbox_url = fetch_actor_inbox(actor_url, config)
    if not inbox_url:
        return False

    return deliver_activity(activity, inbox_url, config)


def deliver_to_followers(activity: dict, config: dict) -> Dict[str, bool]:
    """
    Deliver activity to all followers.

    Args:
        activity: Activity object to deliver
        config: Configuration dictionary

    Returns:
        dict: Map of actor_url -> success boolean
    """
    from data_access import follow as follow_store

    followers = follow_store.get_followers(config)
    if not followers:
        print("No followers to deliver to")
        return {}

    print(f"Delivering activity to {len(followers)} followers...")

    results = {}
    for actor_url in followers:
        print(f"  → {actor_url}")
        results[actor_url] = deliver_to_actor(activity, actor_url, config)

    success_count = sum(1 for s in results.values() if s)
    print(f"\nDelivery complete: {success_count}/{len(followers)} succeeded")
    return results