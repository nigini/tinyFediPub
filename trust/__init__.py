"""
Trust module for tinyFedi.

Evaluates whether incoming activities should be accepted or rejected
based on configurable rules. See docs/ACCEPT_POST_POLICY.md for design.
"""

from collections import namedtuple
from urllib.parse import urlparse

from trust.rules import is_blocked, is_following, is_addressed_to_us, is_reply_to_known_post, is_trusted_signer

Decision = namedtuple('Decision', ['accepted', 'rule'])


def evaluate_create(activity, context, config):
    """Should we accept this incoming Create activity?

    Runs rules in priority order. First match wins.

    Args:
        activity: The incoming Create activity dict
        context: Dict with 'signed_by' (key ID or None) and 'our_actor' (our actor URL)
        config: Server configuration dict

    Returns:
        Decision(accepted=bool, rule=str)
    """
    actor = activity.get('actor', '')
    domain = urlparse(actor).hostname or ''
    signed_by = context.get('signed_by')
    our_actor = context.get('our_actor')

    if is_blocked(actor, domain, config):
        return Decision(accepted=False, rule="blocked")

    if is_following(actor, config):
        return Decision(accepted=True, rule="following")

    if is_addressed_to_us(activity, our_actor):
        return Decision(accepted=True, rule="addressed_to_us")

    if is_reply_to_known_post(activity, config):
        return Decision(accepted=True, rule="reply_to_known_post")

    if is_trusted_signer(signed_by, config):
        return Decision(accepted=True, rule="trusted_signer")

    return Decision(accepted=False, rule="default_reject")
