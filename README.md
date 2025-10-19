# tinyFedi

A minimalist ActivityPub server designed for easy integration with personal websites.

## Overview

Simple file-based ActivityPub implementation that serves federated content 
from static JSON files. Perfect for personal blogs and small websites 
wanting to join the fediverse without a complex infrastructure.

<div style="text-align:center">
    <img src="./docs/images/tinyfedi1.png" 
    style="width:70%; min-width:500px; max-width:800px" 
    alt="tinyFedi connects content, like blog posts, to the Fediverse">
</div>

## Tech Stack

- **Flask** - Lightweight web framework
- **Jinja2** - Template engine for ActivityPub entities
- **File-based storage** - All content served from static JSON files
- **Zero dependencies** - Minimal external requirements

## Setup

### 1. Generate Cryptographic Keys

ActivityPub requires public/private key pairs for secure federation:

```bash
mkdir keys
openssl genrsa -out keys/private_key.pem 2048
openssl rsa -in keys/private_key.pem -pubout -out keys/public_key.pem
```

**Security Note:** Keys are automatically excluded from version control via `.gitignore`.

### 2. Configuration

Copy the example configuration file and customize it for your setup:

```bash
cp config.json.example config.json
```

**!!!** Actor's profile auto-generates from config on startup

### 3. Take it for a Ride

```bash
python app.py
```

Add posts using the CLI: 

```bash
./new_post.py --title "Post Title" --content "Content" --url "https://yourblog.com/post"`
```
**Note:** New posts are automatically delivered to followers when created.

Process incoming activities: 

```bash
python activity_processor.py` #or set up as a cron job
```
**Note:** Activities received in the inbox are automatically queued to be 
processed! 


## Deployment

Designed to run behind a reverse proxy alongside existing websites:

```nginx
location /activitypub/ {
    proxy_pass http://localhost:5000/activitypub/;
}
```

## Development

### Running Tests

Install dependencies and run the test suite:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Writing Tests

This project uses a comprehensive test isolation strategy to ensure reliable testing. All test classes should inherit from `TestConfigMixin` for proper test isolation.

**Key principles:**
- Each test gets its own temporary directory and configuration
- Module reload prevents global variable caching issues
- Configuration-driven paths (no hardcoded references)
- Import app modules INSIDE test methods, AFTER `setUp()` runs

**See `tests/test_config.py`** for complete documentation, usage patterns, helper methods, and implementation details of the test configuration strategy.

## Template System

ActivityPub entities are generated using Jinja2 templates for maintainability and extensibility:

```
templates/
├── objects/          # ActivityStreams Object types
│   ├── actor.json.j2      # Person/Service actors
│   ├── article.json.j2    # Blog posts, articles
│   └── note.json.j2       # Short messages (future)
├── activities/       # ActivityStreams Activity types
│   ├── create.json.j2     # Create activities
│   └── update.json.j2     # Update activities (future)
└── collections/      # ActivityStreams Collections
    ├── outbox.json.j2     # Outbox collections
    └── followers.json.j2  # Followers collections
```

**Design Philosophy:**
- **Type-specific templates** - Each ActivityStreams type has its own template
- **Extensible** - Easy to add new object types (Note, Image, Event) and activity types (Like, Follow, Announce)
- **Spec-compliant** - Templates ensure proper ActivityPub/ActivityStreams structure
- **Configurable** - All values injected from `config.json` and runtime data


## Federation Features

**Implemented:**
- **WebFinger Discovery** - `.well-known/webfinger` for actor discovery
- **Actor Profile** - Dynamic actor generation from config
- **Outbox Collection** - Serves all published activities
- **Individual Endpoints** - Posts and activities accessible via direct URLs
- **Inbox Endpoint** - Receives activities from other federated servers with HTTP signature verification
- **Followers Collection** - Manages and serves follower list
- **Content Negotiation** - Proper ActivityPub headers and validation
- **HTTP Signature Verification** - Cryptographic validation of incoming activities (configurable)
- **HTTP Signature Signing** - Sign outgoing activities for secure delivery

**File Structure:**
```
static/
├── actor.json           # Your actor profile (auto-generated)
├── outbox.json          # Collection of your activities (auto-generated)
├── followers.json       # Collection of followers (auto-generated)
├── posts/               # Individual post objects
│   └── 20250921-143022-my-post.json
├── activities/          # Individual activity objects
│   └── create-20250921-143022.json
└── inbox/               # Received activities from other servers
    ├── TO_DO.json       # Queue of activities needing processing
    ├── follow-*.json    # Follow requests received
    └── undo-*.json      # Unfollow activities received
```

**Current Capabilities:**
- ✅ Others can discover your actor via WebFinger
- ✅ Others can follow your actor and read your posts
- ✅ You receive and process all incoming activities
- ✅ Automatic follower management (add/remove followers)
- ✅ Auto-respond to Follow requests with Accept activities
- ✅ Deliver new posts to all followers automatically
- ✅ HTTP signature verification for incoming activities (configurable)
- ✅ HTTP signature signing for all outgoing deliveries

**Configuration Options:**
- `auto_accept_follow_requests` - Automatically accept follow requests (default: true). Set to `false` for manual approval of followers
- `require_http_signatures` - Require HTTP signatures on all incoming activities (default: false). Set to `true` for production to reject unsigned server-to-server traffic

## What's Next

**Recommended Improvements:**
- **Proper logging system** - Replace print() statements with Python's logging module
- **Activity ID naming improvements** - Fix timestamp conflicts by implementing Content-Addressable Storage (CAS) approach using content hashes instead of timestamps
- **Outbox folder organization** - Create dedicated outbox directory structure mirroring inbox organization for better file management
- **Deprecation fixes** - Replace datetime.utcnow() with datetime.now(datetime.UTC) for Python 3.12+

**Future Enhancements:**
- Manual follow approval workflow
- Support for Like, Announce, Update, and other activity types
- Mention and reply handling
- Clients endpoints

## To Consider

### Linked Data Signatures vs HTTP Signatures

**Current Implementation:** HTTP Signatures (transport-layer, header-based)

The fediverse currently uses **HTTP Signatures** (draft-cavage-http-signatures-12) which sign the HTTP request itself. The signature lives in the `Signature` header, and the activity JSON body remains clean without embedded signatures.

**Alternative Approach:** Linked Data Signatures (object-layer, embedded)

**Linked Data Signatures** embed cryptographic signatures directly in the ActivityPub JSON document:

```json
{
  "type": "Follow",
  "actor": "https://example.com/users/alice",
  "object": "https://yourserver.com/actor",
  "signature": {
    "type": "RsaSignature2017",
    "creator": "https://example.com/users/alice#main-key",
    "created": "2025-01-05T12:00:00Z",
    "signatureValue": "base64encodedstuff=="
  }
}
```

**Potential Advantages:**
- **Persistence:** Signature travels with the activity when stored/forwarded
- **Verification without transport:** Can verify authenticity of stored activities later
- **Migration scenarios:** Verify integrity and authorship of archived activities
- **Multi-hop federation:** Original signature preserved through forwarding

**Why Not Implemented:**
- More complex (requires JSON-LD canonicalization)
- Mostly deprecated in modern fediverse (Mastodon, Pleroma use HTTP signatures)
- HTTP signatures are simpler and cover the same security requirements for real-time federation
