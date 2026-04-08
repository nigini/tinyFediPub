# Accept Post Policy

How tinyFedi decides whether to accept or reject incoming `Create` activities.

## Problem

When a remote server POSTs a `Create(Note)` or `Create(Article)` to your inbox,
tinyFedi must decide: store this post, or discard it?

On a multi-user server (like Mastodon), the answer is often "accept everything
and let users filter." On a single-user, self-hosted server like tinyFedi, that
approach floods storage with unsolicited content. We need an acceptance policy
that captures content we care about while rejecting noise.

### The Forwarding Complication

ActivityPub spec (section 7.1.2) allows inbox forwarding: when Bob replies to
Alice's post and addresses it to Alice's `followers` collection, Alice's server
forwards Bob's reply to all her followers — because Bob can't enumerate that
collection himself.

This means the HTTP signature on a forwarded activity belongs to the
**forwarding server**, not the **original author**. The receiving server must
decide whether to trust the forwarder.

### The Threading Complication

AS2's `inReplyTo` only points to the **immediate parent**, not the thread root.
There is no standard "root post" or "conversation" field in AS2 (Mastodon uses a
non-standard `conversation` property). This means:

- If Alice replies to your post, `inReplyTo` points to your post — easy to detect.
- If Bob replies to Alice's reply, `inReplyTo` points to Alice's reply — you'd
  miss the connection to your original post unless you walk the chain or already
  have Alice's reply stored.

## Existing Approaches

### Mastodon

- Accepts `Create` activities after HTTP signature verification
- For forwarded activities (signer != actor): requires a JSON-LD Signature
  (`RsaSignature2017`) from the original author. Rejects if verification fails.
- Tracks `relayed_through_actor` **in-memory** during processing, but does NOT
  persist delivery provenance to the database
- Mastodon's own docs call LD Signatures "outdated and not recommended for new
  implementations"

### Misskey

- Strict domain matching: `actor.uri` domain must match `object.id` domain
- Silently drops forwarded activities where domains don't match
- Effectively **no inbox forwarding support**

### Pleroma/Akkoma

- HTTP signature verification only, no LD Signature support
- Cannot verify forwarded activities at all

### Summary

| Server    | Forwarding | Provenance storage | Trust model    |
|-----------|------------|--------------------|----------------|
| Mastodon  | LD Sigs    | In-memory only     | Instance-level |
| Misskey   | Rejected   | None               | Domain match   |
| Pleroma   | Can't verify | None             | HTTP sig only  |

No existing implementation persists "who delivered this" alongside stored
activities. This is an unexplored area in the fediverse.

## tinyFedi Acceptance Rules

Ordered by priority. The first matching rule wins:

### Rule 0: Block List

If the actor or their domain is in the block list, **reject**. This takes
precedence over all other rules.

### Rule 1: Following

If the actor is in `following.json`, **accept**. This is the primary path —
content from people you chose to follow.

### Rule 2: Addressed to You

If your actor URL appears in the activity's `to` or `cc` fields, **accept**.
This covers direct messages and mentions from anyone.

### Rule 3: Reply to Known Post

If the object's `inReplyTo` points to any post we already have — local
(`posts/local/`) or remote (`posts/remote/`) — **accept**. This lets
conversations naturally accrete: you follow Alice, receive her post, Bob replies
to it, you accept Bob's reply because you have Alice's post.

**Depth risk**: a viral thread could flood storage. Consider a configurable
depth limit or cap on replies from non-followed actors.

**Threading limitation**: this only catches direct replies to posts we have. If
Bob replies to Carol's reply to Alice's post, and we don't have Carol's reply,
we miss Bob's. On-demand thread pulling (client-initiated) is the intended
solution for deeper thread exploration.

### Rule 4: Trusted Forwarder

If the HTTP signature actor differs from the activity actor (forwarded
activity), and the **signer** is in `following.json`, **accept**. This leverages
HTTP signature verification we already perform — no LD Signatures or FEP-8b32
needed.

Requires storing `_signed_by` metadata on inbox activities so the processor can
check who delivered it.

### Rule 5: Default Reject

None of the above matched — **reject**. On a single-user server, silence is
better than noise.

## Storage Design

Remote posts are stored with the original object kept pristine, and tinyFedi
annotations in a separate metadata file:

```
posts/remote/
  mastodon.social/
    alice/
      12345/
        object.json      <- original AS2 object, untouched
        metadata.json    <- tinyFedi annotations
```

### Why Separate Files?

- **Integrity proof preservation**: if the object carries a FEP-8b32 proof, any
  modification would invalidate it. Storing the original untouched ensures
  proofs remain verifiable.
- **No collision risk**: informal `_` prefixed fields could collide with fields
  in the original object.
- **Clean separation**: tinyFedi's bookkeeping doesn't pollute the AS2 object.

### Metadata Fields

```json
{
  "received_at": "2026-04-07T17:12:23Z",
  "signed_by": "https://social.coop/users/alice#main-key",
  "forwarded": false,
  "accepted_by_rule": "following"
}
```

- `received_at`: when tinyFedi received the activity
- `signed_by`: the actor whose HTTP signature was verified on delivery
- `forwarded`: true if `signed_by` differs from the object's `attributedTo`
- `accepted_by_rule`: which acceptance rule matched (useful for debugging and
  for the trust graph)

## Future: Trust Graph

The acceptance rules above are static — you either follow someone or you don't.
A trust graph would make acceptance dynamic, evolving based on your interactions:

| Signal             | Trust effect                              |
|--------------------|-------------------------------------------|
| Follow an actor    | Trust their posts + their forwards        |
| Like a post        | Positive signal for that actor            |
| Announce/boost     | Stronger positive signal                  |
| Reply to someone   | Engagement signal                         |
| Block an actor     | Reject everything from them               |
| Block a domain     | Reject everything from that server        |
| Trusted forwarder  | Inherit partial trust for forwarded posts |

### How It Would Work

A `trust.json` file (or similar) tracks trust scores per actor/domain, updated
by your actions. The acceptance check becomes:

```
if trust_score(actor, activity) > threshold:
    accept
else:
    reject
```

This is essentially a **Web of Trust** applied to ActivityPub — your own
interactions shape what you see, without relying on algorithmic curation or
centralized moderation.

### Design Considerations

- **Single-user context**: on a one-person server, the trust graph reflects one
  person's preferences. This is a feature, not a limitation — it's YOUR feed.
- **Transitivity**: if you trust Alice and Alice boosts Bob's post, Bob gets
  indirect trust. How many hops? Configurable.
- **Decay**: trust signals could decay over time. An old follow with no recent
  interaction might carry less weight than an active conversation.
- **Transparency**: the trust graph should be inspectable. You should be able to
  ask "why did I see this post?" and get a clear answer.
- **Relationship to FEP-8b32**: object integrity proofs make trust decisions
  more reliable — you can verify that a forwarded post actually came from who it
  claims, independent of who delivered it.

## Future: On-Demand Thread Retrieval

Rather than automatically pulling entire conversation threads, tinyFedi takes a
**pull model** for deep threading:

1. Server receives and stores direct posts from followed actors
2. Client sees a post with `inReplyTo` or a replies collection URL
3. Client requests: "show me the thread around this post"
4. Server fetches the `inReplyTo` chain (walking up to the root) and/or the
   replies collection from the remote server
5. Results are cached temporarily but not necessarily persisted

This keeps `posts/remote/` focused on content you care about, while still
allowing full thread exploration when you want it.
