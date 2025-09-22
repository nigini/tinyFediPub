# tinyFedi.pub

A minimalist ActivityPub server designed for easy integration with personal websites.

## Overview

Simple file-based ActivityPub implementation that serves federated content from static JSON files. Perfect for personal blogs and small websites wanting to join the fediverse without complex infrastructure.

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

### 2. Configuration

Copy the example configuration file and customize it for your setup:

```bash
cp config.json.example config.json
```

All settings are externalized in `config.json`:

```json
{
  "server": {
    "domain": "yourdomain.com",
    "host": "0.0.0.0", 
    "port": 5000,
    "debug": false
  },
  "activitypub": {
    "username": "blog",
    "actor_name": "Your Blog Name",
    "actor_summary": "Description of your blog",
    "namespace": "activitypub",
    "auto_accept_follow_requests": true
  },
  "security": {
    "public_key_file": "keys/public_key.pem",
    "private_key_file": "keys/private_key.pem"
  }
}
```

**Security Note:** Keys are automatically excluded from version control via `.gitignore`.

## Deployment

Designed to run behind a reverse proxy alongside existing websites:

```nginx
location /activitypub/ {
    proxy_pass http://localhost:5000/activitypub/;
}
```

## Usage

1. Update `config.json` with your domain and actor details
2. Run `python app.py` 
3. Actor profile auto-generates from config on startup
4. Add posts using the CLI: `./new_post.py --title "Post Title" --content "Content" --url "https://yourblog.com/post"`

## Development

### Running Tests

Install dependencies and run the test suite:

```bash
pip install -r requirements.txt
python -m pytest tests/ -v
```

### Creating Posts

Use the CLI tool to create new ActivityPub posts:

```bash
./new_post.py --title "My Post" --content "Post content" --url "https://myblog.com/my-post" --summary "Optional summary"
```

This automatically:
- Creates the post JSON in `static/posts/`
- Generates the Create activity in `static/activities/`
- Regenerates the outbox collection

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

Current implementation supports `Article`/`Note` objects, `Create` activities, and `Collection` types (outbox, followers), with template structure ready for future ActivityStreams types.

## Federation Features

**Implemented:**
- **WebFinger Discovery** - `.well-known/webfinger` for actor discovery
- **Actor Profile** - Dynamic actor generation from config
- **Outbox Collection** - Serves all published activities
- **Individual Endpoints** - Posts and activities accessible via direct URLs
- **Inbox Endpoint** - Receives activities from other federated servers
- **Followers Collection** - Manages and serves follower list
- **Content Negotiation** - Proper ActivityPub headers and validation

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
- Others can discover your actor via WebFinger
- Others can follow your actor and read your posts
- You receive and store all incoming activities
- Automatic follower management (configurable)

**Configuration Options:**
- `auto_accept_follow_requests` - Automatically accept follow requests (default: true)
- Set to `false` for manual approval of followers

## What's Next

**In Development:**
- Follow request processing (add to followers, generate Accept activities)
- Activity delivery to followers (send your posts to follower inboxes)
- HTTP signature verification for secure federation

**Future Enhancements:**
- Manual follow approval workflow
- Support for Like, Announce, and other activity types
- Mention and reply handling
- Custom endpoints for follow request management

## To Consider

### Activity Processing Strategy

The inbox receives various ActivityPub activities that require different processing approaches:

**Activities requiring action:**
- **Follow** - Add to followers collection, generate Accept/Reject response
- **Undo(Follow)** - Remove from followers collection
- **Like/Announce** - Optional analytics tracking
- **Create/Update/Delete** - Handle mentions or replies to your posts

**Activities that are informational:**
- **Accept/Reject** - Responses to your outgoing Follow requests (log only)

**Processing Queue:**
Current implementation uses `static/inbox/TO_DO.json` to track activities needing processing, allowing for:
- Automatic processing (with `auto_accept_follow_requests: true` config)
- Manual approval workflows (scan unprocessed activities)
- Selective processing by activity type

**Follow Requests - Special Case:**
Following relationships are fundamental to ActivityPub federation. The current approach:
- All Follow activities saved to inbox for audit trail
- Auto-accept mode: immediately add to followers and generate Accept activity
- Manual approval mode: requires processing pending requests

**Note:** While ActivityPub spec defines standard collections (`/followers`, `/following`), many servers implement custom APIs for follow request management (e.g., Mastodon's `/api/v1/follow_requests`, Pleroma's similar endpoints). Future enhancements could add a `/pending-followers` endpoint for manual approval workflows.