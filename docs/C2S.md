# Client-to-Server API for tinyFedi

## The Gap: Clients in the Fediverse

tinyFedi currently operates as a **publish-only ActivityPub server**: it
federates blog posts to followers and receives activities in its inbox,
but there is no way to read that inbox as a human, follow other actors,
or interact with content — short of reading raw JSON files on disk.

The natural next step is a client. But what API should it speak?

The ActivityPub specification defines two protocols: Server-to-Server
(S2S) for federation between servers, and Client-to-Server (C2S) for
interaction between a user's client and their server. In practice, the
Fediverse runs almost entirely on S2S + the Mastodon API — a
proprietary, Mastodon-specific REST API that has become the de facto
client standard simply because Mastodon dominates the network.

The AP C2S protocol covers the basics — POST activities to outbox, GET
inbox/outbox/collections — but was left deliberately minimal. The spec
itself acknowledges having "no strongly agreed upon mechanisms" for
authentication (Section B.1). It defines server-side effects for only 9
activity types and says nothing about timelines, notifications, search,
media upload, or real-time updates.

This minimalism, combined with Mastodon's explicit rejection of C2S
(GitHub issue #10520, 2019), created a chicken-and-egg problem: no
clients because no servers implement C2S, no servers because no clients
demand it. The Mastodon API filled the vacuum.

For tinyFedi, neither option is a natural fit:

- **The Mastodon API** assumes a multi-user server with OAuth apps,
  timelines, notifications, polls, custom emoji, trending content, and
  dozens of endpoints irrelevant to a single-actor personal server.
  Implementing it would pull tinyFedi toward being a Mastodon-compatible
  server, which it is not.
- **Raw AP C2S** covers roughly 60–70% of what we need (outbox POST for
  creating/following/liking, inbox/collection GET for reading) but lacks
  critical pieces for a usable client experience.
- **A custom internal API** would inevitably reinvent a subset of one of
  the above, with no interoperability benefit.

The path forward: **implement AP C2S as the base, extend it through the
`streams` mechanism the spec already provides, and align extensions with
Fediverse Enhancement Proposals (FEPs) where they exist.**

## Related Efforts

### Implementations

Several projects have attempted C2S support with varying degrees of
success:

- **Pleroma/Akkoma** — The most widely deployed C2S-capable server.
  Supports Create/Note via outbox POST, reuses Mastodon OAuth tokens.
  C2S is secondary to the Mastodon API and receives minimal testing.
- **FedBOX** (Marius Orcsik) — A Go-based reference implementation,
  possibly the most complete C2S server. Adds non-standard top-level
  collections (`/actors`, `/activities`, `/objects`) with query parameter
  filtering. Author of FEP-6606 (collection addressing improvements,
  merged December 2024).
- **Vocata** — A Python ASGI server that is "vocabulary-agnostic,"
  storing any AS2 object type in an RDF graph. Pure transport philosophy:
  the server is a graph store and message router, all presentation
  delegated to clients.
- **ActivityPods** — Combines AP with Solid Pods. Deployed to ~500 users
  in France. Learned that granular permissions and decoupled application
  backends are essential — their v1 JWT tokens granting full Pod access
  was a security flaw.
- **CPub / openEngiadina** — An Elixir-based C2S server that was
  **abandoned** in favor of XMPP. Key lesson: developing client and
  server in lockstep meant "we were only compatible with our own
  software." JSON-LD complexity was a major burden.
- **Evan Prodromou's `ap` CLI** — A Python C2S client by the AP spec
  co-author. Demonstrates proper C2S usage (outbox POST, collection GET,
  OAuth) but notes that "not all servers that implement the ActivityPub
  federation protocol necessarily implement the ActivityPub API."

### Community Efforts

- **Social Web Foundation** — Building C2S proof-of-concepts
  (places.pub, Checkin, ReactivityPub). Described as "betting big on
  C2S" (We Distribute, August 2025).
- **SocialCG Task Forces** — W3C Social Web Incubator Community Group
  has active task forces for testing, data portability, and others. No
  dedicated C2S API task force, but the testing and geosocial work
  exercises C2S directly.
- **SocialHub NextGen API Discussion** — Community thread exploring what
  FEPs are needed for viable C2S. Notable contribution from trwnh
  arguing for an "API suite" decomposition (publishing, notifications,
  auth, media, search) rather than a monolithic spec.

### Relevant FEPs

| FEP | Title | Status | Relevance |
|-----|-------|--------|-----------|
| FEP-6606 | Collection addressing improvements | Merged (Dec 2024) | URL query params for filtering collections |
| FEP-4ccd | Pending followers collection | Draft | Client access to pending follow requests |
| FEP-c648 | Blocked collection | Draft | Exposes blocked actors |
| FEP-76ea / FEP-171b / FEP-f228 | Reply/conversation collections | Draft | Threading and conversation context |
| FEP-5bf0 | Collection sorting and filtering | Draft | `streams` on collections for filtered sub-views |
| FEP-34c1 | Collection filtering via TREE | Draft | Client-driven filtering via hypermedia |
| FEP-d8c2 | OAuth 2.0 profile for AP | Draft | Standardized C2S authentication |

## Steve Bate's Analysis

Steve Bate has produced the most systematic analysis of the C2S gap
through building both a client (Flowz) and a server (FIRM), plus the
ActivityPub test suite. Three of his insights directly inform tinyFedi's
design.

### "A Box is Not a Timeline"

The inbox and outbox are ordered collections of **activities** (events).
A timeline is a collection of **objects** (current state). These are
fundamentally different:

```
Inbox activities:   Create note-1, Create note-2, Update note-1, Delete note-2, Create note-3
Timeline objects:   note-3, note-1 (updated)
```

Reconstructing object state from an activity stream is an
**event-sourcing problem**: the client must replay Create → Update →
Delete sequences to derive what currently exists. Bate argues the
**server** should maintain these materialized views, not force every
client to replay the event log.

### The `streams` Mechanism

The AP spec (Section 4.1) defines an optional `streams` property on
actors: *"A list of supplementary Collections which may be of interest."*
It says nothing about what those collections should contain — it is
deliberately open-ended.

Bate proposes using `streams` to expose **server-maintained,
object-centric collections** alongside the standard activity-centric
inbox/outbox. Home timelines, notifications, bookmarks — each as a
collection the client can GET directly, without event-sourcing.

This pattern has **no FEP**. It remains informal across Bate's blog
posts. The closest formalization is FEP-5bf0, which extends `streams` to
collections themselves (filtered sub-views), but at the collection level
rather than the actor level.

### The Mastodon API Adapter

To break the chicken-and-egg problem, Bate proposes a standalone proxy
that translates C2S requests into Mastodon API calls. This lets C2S
clients work against Mastodon servers without requiring Mastodon to
change. While not directly relevant to tinyFedi (we control both sides),
it validates C2S as a viable client protocol: if you can map it to the
Mastodon API, the abstraction is expressive enough.

### Sources

- ["A Box is Not a Timeline"](https://www.stevebate.net/a-box-is-not-a-timeline/) (July 2023)
- ["An Inbox is Not a Queue"](https://www.stevebate.net/activitypub-an-inbox-is-not-a-queue/)
- ["ActivityPub Client API: A Way Forward"](https://www.stevebate.net/activitypub-client-api-a-way-forward/) (July 2025)
- ["NextGen ActivityPub Social API" — SocialHub](https://socialhub.activitypub.rocks/t/nextgen-activitypub-social-api/4733)
- [FIRM server — GitHub](https://github.com/steve-bate/firm)

## tinyFedi's Direction

tinyFedi will implement AP C2S as its client API, extended with
server-maintained object-centric collections exposed via the actor's
`streams` property. The server materializes these views as it processes
activities (both inbound via S2S and outbound via C2S), so clients
receive object-centric data ready to render.

### Actor Profile

The actor document exposes standard C2S endpoints plus `streams`:

```json
{
  "@context": "https://www.w3.org/ns/activitystreams",
  "type": "Person",
  "id": "https://tiny.example/activitypub/actor",
  "inbox": "https://tiny.example/activitypub/inbox",
  "outbox": "https://tiny.example/activitypub/outbox",
  "followers": "https://tiny.example/activitypub/followers",
  "following": "https://tiny.example/activitypub/following",
  "streams": [
    "https://tiny.example/activitypub/streams/home",
    "https://tiny.example/activitypub/streams/posts",
    "https://tiny.example/activitypub/streams/notifications",
    "https://tiny.example/activitypub/streams/bookmarks",
    "https://tiny.example/activitypub/streams/pending-followers"
  ]
}
```

### Endpoints

**Standard C2S (from the spec):**

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/activitypub/outbox` | POST | Client submits activities (Create, Follow, Like, Announce, Undo, etc.) |
| `/activitypub/outbox` | GET | Activity collection — what you published |
| `/activitypub/inbox` | GET | Activity collection — raw event log of what you received |
| `/activitypub/followers` | GET | Follower actor URIs |
| `/activitypub/following` | GET | Followed actor URIs |

**Object-centric streams (via `streams` property):**

| Stream | Contents | Materialized from |
|--------|----------|-------------------|
| `streams/home` | Current objects from followed actors | Inbox Create/Update/Delete activities |
| `streams/posts` | Your published objects (not wrapped in activities) | Outbox Create/Update/Delete activities |
| `streams/notifications` | Typed notifications (follows, likes, announces, mentions) | Inbox activities, categorized |
| `streams/bookmarks` | Objects you've bookmarked | C2S Add/Remove to bookmarks target |
| `streams/pending-followers` | Follow requests awaiting approval (aligns with FEP-4ccd) | Inbox Follow activities |

### Write Path

Standard C2S: the client POSTs activities to the outbox. The server
assigns IDs, stores the activity, executes side effects, delivers via
S2S, **and updates the relevant stream collections:**

```
Client POSTs Create(Note) to outbox
  → Server stores post + activity
  → Server delivers to followers via S2S
  → Server adds object to streams/posts

Client POSTs Follow(remote-actor) to outbox
  → Server sends Follow via S2S
  → Server adds to following when Accept arrives
  → Server starts receiving remote actor's posts in inbox

Client POSTs Like(remote-note) to outbox
  → Server delivers Like via S2S
  → Server adds to liked collection
```

### Read Path

Instead of replaying the inbox activity log, the client reads
materialized streams:

```
Client GETs streams/home
  → Server returns OrderedCollection of current objects
  → Objects reflect latest state (updates applied, deletes removed)
  → Ready to render — no event-sourcing required

Client GETs streams/notifications
  → Server returns typed items (follow, like, announce, mention)
  → Client renders notification list
```

The raw inbox/outbox remain available for clients that want the full
activity log.

### File System Layout

This extends tinyFedi's existing file-based storage naturally:

```
static/
├── inbox/                  # raw activities (event log — already exists)
├── activities/             # published activities (already exists)
├── posts/                  # published objects (already exists)
├── following.json          # actors you follow (new)
├── streams/
│   ├── home/               # objects from followed actors
│   ├── notifications.json  # typed notification items
│   ├── bookmarks.json      # bookmarked object references
│   └── pending-followers.json
└── ...
```

Note that `posts/` already serves the role of `streams/posts` — tinyFedi
has been storing objects separately from activities from the start.

### Authentication

For a single-actor server, a simple bearer token (configured in
`config.json`) is sufficient initially. This can evolve toward FEP-d8c2
(OAuth 2.0 profile for AP) if needed, but the complexity of OAuth is
unnecessary when there is exactly one user.

### Implementation Order

1. **Following** — Send Follow activities, maintain `following.json`,
   handle incoming Accept/Reject. This enables content flow.
2. **Inbox materialization** — When Create/Update/Delete arrives via S2S,
   update `streams/home/` with current object state.
3. **C2S outbox POST** — Accept authenticated activities from a client,
   replacing the CLI tools.
4. **Stream endpoints** — Serve the materialized collections via GET.
5. **Notifications** — Categorize inbox activities into typed
   notification items.
6. **Bookmarks** — Support Add/Remove for a bookmarks collection.

### Implications for tinyHome

This design means the tinyHome Fedi plugin simply GETs stream
collections — no activity replay, no event-sourcing, no deep
ActivityPub knowledge. The plugin fetches `streams/home` for the feed,
`streams/notifications` for alerts, and renders objects.

The same pattern applies to future adapters: tinyNostr would expose its
own object-centric collections, and tinyHome's Nostr plugin would
consume them the same way. Each adapter handles protocol complexity
internally; tinyHome sees collections of objects.

## References

### Specifications
- [W3C ActivityPub Recommendation](https://www.w3.org/TR/activitypub/) — Sections 5-6 (C2S), Section 4.1 (Actor objects, `streams` property)
- [W3C ActivityStreams 2.0](https://www.w3.org/TR/activitystreams-core/) — Collection paging
- [W3C ActivityPub Issue #71](https://github.com/w3c/activitypub/issues/71) — Discovery of collections/streams

### Steve Bate
- ["A Box is Not a Timeline"](https://www.stevebate.net/a-box-is-not-a-timeline/) — The core argument for object-centric collections
- ["An Inbox is Not a Queue"](https://www.stevebate.net/activitypub-an-inbox-is-not-a-queue/) — Clarifying inbox semantics
- ["ActivityPub Client API: A Way Forward"](https://www.stevebate.net/activitypub-client-api-a-way-forward/) — Comprehensive C2S extension proposal
- ["NextGen ActivityPub Social API" — SocialHub](https://socialhub.activitypub.rocks/t/nextgen-activitypub-social-api/4733) — Community discussion

### FEPs
- [FEP-6606: Collection addressing improvements](https://codeberg.org/fediverse/fep/pulls/452)
- [FEP-4ccd: Pending followers collection](https://codeberg.org/fediverse/fep)
- [FEP-c648: Blocked collection](https://socialhub.activitypub.rocks/t/fep-c648-blocked-collection/3349)
- [FEP-5bf0: Collection sorting and filtering](https://socialhub.activitypub.rocks/t/fep-5bf0-collection-sorting-and-filtering/3095)
- [FEP-d8c2: OAuth 2.0 profile for AP](https://codeberg.org/fediverse/fep)

### Community Discussion
- [Mastodon C2S rejection — Issue #10520](https://github.com/mastodon/mastodon/issues/10520)
- [SocialHub: C2S FAQ](https://socialhub.activitypub.rocks/t/activitypub-client-to-server-faq/1941)
- [SocialHub: Implementing AP C2S (APConf 2020)](https://socialhub.activitypub.rocks/t/implementing-activitypub-client-to-server/981)
- ["On the topic of ActivityPub C2S" — prefetcher](https://blog.nanoshinono.me/on-the-topic-of-activitypub-c2s-or-how-to-design-an-alright-protocol-and-have)
- [We Distribute: SWF betting on C2S (August 2025)](https://wedistribute.org/2025/08/social-web-foundation-is-betting-big-on-client-to-server-api/)

### Implementations
- [FIRM server — GitHub](https://github.com/steve-bate/firm)
- [FedBOX — SourceHut](https://git.sr.ht/~mariusor/fedbox)
- [Vocata — Codeberg](https://codeberg.org/Vocata/vocata)
- [ActivityPods](https://activitypods.org/the-road-to-activitypods-2-0)
- [`ap` CLI — GitHub](https://github.com/evanp/ap)
