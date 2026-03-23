# Client Contract: What tinyFedi Guarantees to tinyHome

tinyFedi's C2S API is designed so that clients (starting with tinyHome)
can be as thin as possible: **fetch, paginate, render**. This document
defines what tinyFedi must do server-side so clients don't have to.

For the full C2S research and design rationale, see
[tinyHome's C2S.md](https://github.com/nigini/tinyHomePub/blob/main/C2S.md).

## 1. Serve Objects, Not Activities

Streams (`streams/home`, `streams/posts`, etc.) return
**OrderedCollections of objects** — not activities. The server
materializes current object state from the inbox activity log as
activities arrive. Clients never need to replay Create → Update →
Delete sequences.

Each object in a stream includes activity-derived metadata as
sub-collections:

```json
{
  "type": "Note",
  "id": "https://mastodon.social/@alice/12345",
  "content": "<p>Hello world</p>",
  "published": "2026-03-20T14:30:00Z",
  "attributedTo": { ... },
  "replies": { "type": "OrderedCollection", "totalItems": 5 },
  "likes": { "type": "OrderedCollection", "totalItems": 12 },
  "shares": { "type": "OrderedCollection", "totalItems": 3 }
}
```

The `streams/notifications` stream is the exception — there, Activities
are the content (someone followed you, liked your post), so it serves
Activities.

## 2. Normalize Remote Objects on Ingest

Objects arrive from remote servers (Mastodon, Pleroma, Misskey, etc.) in
inconsistent shapes. tinyFedi normalizes during inbox materialization so
clients always see a predictable structure:

| Field | Guarantee |
|-------|-----------|
| `type` | Always a string (even if the remote sent an array, pick the most specific recognized type) |
| `content` | Always a string. If the remote sent `contentMap`, pick the best match using server locale |
| `name` | Always a string or absent. Never an object |
| `published` | Always ISO 8601 string |
| `attributedTo` | Always an embedded object with at least `id`, `type`, `name`. Resolve bare URIs server-side by fetching the remote actor |
| `attachment` | Always an array, even for a single item or when absent (empty array) |
| `tag` | Always an array |
| `url` | Always a string URI or absent |
| `inReplyTo` | Always a string URI or absent. Not an embedded object |
| `replies` / `likes` / `shares` | Always `{ "type": "OrderedCollection", "totalItems": N }` when present |

If the remote server sends a value the normalizer can't handle, the
field is omitted rather than passed through in an unpredictable shape.

## 3. Process Microsyntax Server-Side

When a client POSTs a Create activity with plain text source, tinyFedi
handles all text processing:

```json
{
  "type": "Create",
  "object": {
    "type": "Note",
    "source": {
      "mediaType": "text/plain",
      "content": "Hey @alice@mastodon.social check #decentralization https://example.com"
    }
  }
}
```

tinyFedi will:
- Resolve `@alice@mastodon.social` via WebFinger → add Mention to `tag`
- Convert `#decentralization` → add Hashtag to `tag`
- Convert URLs → add clickable links
- Generate HTML `content` from the processed text
- Populate the `tag` array with all resolved references

The client sends plain text with a `source.mediaType` hint. The server
returns the fully processed object. This means any future client (CLI,
mobile, tinyHome) gets microsyntax processing for free.

## 4. Expose Streams via Actor `streams` Property

The actor document includes a `streams` array pointing to materialized
collections. Clients discover available streams by reading the actor
profile — no hardcoded paths.

```json
{
  "streams": [
    "https://tiny.example/activitypub/streams/home",
    "https://tiny.example/activitypub/streams/posts",
    "https://tiny.example/activitypub/streams/notifications",
    "https://tiny.example/activitypub/streams/bookmarks",
    "https://tiny.example/activitypub/streams/pending-followers"
  ]
}
```

If a stream is not yet implemented, it is absent from the array. Clients
should check for presence before rendering stream-specific UI.

## 5. Authenticate with Bearer Token

For the single-actor model, tinyFedi uses a pre-shared bearer token
configured in `config.json`. All C2S requests (outbox POST, stream GET,
collection GET) require:

```
Authorization: Bearer <token>
```

Unauthenticated requests to streams return `401`. Public-facing
endpoints (actor profile, webfinger, S2S inbox POST) remain open.

## Summary: What the Client Does NOT Need to Do

| Concern | Handled by |
|---------|-----------|
| Replay activities to derive object state | **tinyFedi** (inbox materialization) |
| Normalize inconsistent remote object shapes | **tinyFedi** (ingest normalization) |
| Resolve `@mentions` and `#hashtags` | **tinyFedi** (microsyntax processing) |
| Discover available streams | **tinyFedi** (actor `streams` property) |
| WebFinger resolution | **tinyFedi** (server-side on ingest and post creation) |
| Fetch remote actor profiles for display | **tinyFedi** (embedded in `attributedTo` during normalization) |

The client's job: **GET a stream, follow `next` links, render objects.**
