# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a minimal ActivityPub server implementation using Flask. It's designed for easy integration with personal websites and uses a file-based approach for maximum simplicity. The server can federate blog posts to the fediverse without complex infrastructure.

## Commands

**Development:**
```bash
# IMPORTANT: Always activate virtual environment first
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure the config file
cp config.json.example config.json
# Edit config.json with your domain and settings

# Run the server (generates actor.json on startup)
python app.py

# Create new posts
./new_post.py --title "Post Title" --content "Content" --url "https://yourblog.com/post" --summary "Optional"
```

**Testing:**
```bash
# IMPORTANT: Always activate virtual environment first
source .venv/bin/activate

# Run full test suite
python -m pytest tests/ -v

# Test specific endpoints
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/actor
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/outbox
curl -H "Accept: application/activity+json" http://localhost:5000/activitypub/posts/<post-id>
```

## Architecture

**Configuration:**
- All settings externalized in `config.json` (server, ActivityPub, security)
- Users must copy `config.json.example` to `config.json` and customize it
- Cryptographic keys stored in `keys/` directory (excluded from git)
- Actor profile generated dynamically from config on server startup

**URL Structure:**
- All ActivityPub endpoints use the `/activitypub/` namespace (configurable)
- WebFinger discovery at `/.well-known/webfinger` (protocol requirement)
- Designed to run behind reverse proxy: `proxy_pass http://localhost:5000/activitypub/`

**Data Model:**
- **Activities** (`/activitypub/activities/<id>`) - Actions that happened (e.g., Create, Update)
- **Objects** (`/activitypub/posts/<id>`) - The content being acted upon (blog posts)
- **Actor** (`/activitypub/actor`) - The blog identity/profile (generated from config)
- **Outbox** (`/activitypub/outbox`) - Collection of all activities (dynamically generated)

**File-Based Architecture:**
- `config.json` - All configuration (domain, actor details, key file paths)
- `keys/` - Public/private key files (auto-generated with OpenSSL)
- `static/webfinger.json` - WebFinger response
- `static/actor.json` - Actor profile (generated from config)
- `static/posts/` - Individual post objects (created by CLI)
- `static/activities/` - Individual activity files (created by CLI)
- `static/outbox.json` - Generated dynamically from activities directory

**Post Creation Workflow:**
1. CLI tool (`new_post.py`) creates post JSON with timestamp+slug ID
2. CLI creates corresponding Create activity wrapping the post
3. CLI regenerates outbox by scanning activities directory (append-only)
4. Server serves all files without restart needed (Flask auto-reload in debug mode)

**Key Features:**
- **Memory efficient**: Outbox streams from files without loading all activities (using Jinja2 generators)
- **Template-driven**: All ActivityPub entities generated from Jinja2 templates for maintainability
- **Self-healing**: Outbox can be rebuilt from activities directory at any time
- **Error resilient**: Malformed activity files are skipped gracefully with warnings
- **Simple deployment**: Just files, no database required
- **Flexible URLs**: Post URLs can point anywhere (existing blog, external sites, etc.)
- **Secure**: Private keys never committed, proper ActivityPub content negotiation

## Test Coverage

Comprehensive test suite in `tests/` covering:
- Post ID generation (timestamp + optional slug)
- Post/activity creation and file operations
- Outbox regeneration from activities (with streaming templates)
- Malformed activity file handling and error resilience
- CLI workflow integration
- All Flask endpoints (webfinger, actor, outbox, posts, activities)
- Content negotiation and error handling

## Current Status

✅ **Implemented:**
- WebFinger discovery
- Actor profile with dynamic generation (Jinja2 templated)
- Outbox collection (streaming template generation)
- Individual post and activity endpoints (templated)
- CLI tool for post creation
- Proper ActivityPub content types and headers
- Comprehensive test suite with error handling tests
- Secure key management
- Extensible template system for future ActivityPub types
- **NEW**: Inbox endpoint with activity saving to `static/inbox/`
- **NEW**: Followers collection endpoint with template-based generation
- **NEW**: Utility functions for activity ID generation and actor URL parsing
- **NEW**: ActivityPub Accept header validation via decorator pattern

## Recent Progress (2025-09-21)

**Inbox Implementation:**
- All incoming activities saved to `static/inbox/` with structured filenames
- Filename format: `{type}-{timestamp}-{domain}.json` (e.g., `follow-20250921-143022-mastodon-social.json`)
- Comprehensive test coverage for activity saving and HTTP endpoint validation
- Content-type validation for ActivityPub requests

**Followers Collection:**
- `/followers` endpoint with empty collection auto-generation
- Template-based JSON generation using `templates/collections/followers.json.j2`
- File creation on-demand when endpoint is accessed
- Test coverage for endpoint behavior and file creation

**Code Quality Improvements:**
- Refactored Accept header validation into reusable `@require_activitypub_accept` decorator
- Created utility functions: `generate_activity_id()` and `parse_actor_url()`
- Organized tests into separate files: `test_inbox.py`, `test_followers.py`
- Added configuration option: `auto_accept_follow_requests: true` (default)

**Processing Queue Design:**
- Designed `static/inbox/TO_DO.json` structure for tracking pending activities
- Format: `{"filename": "timestamp"}` for chronological processing
- Documented activity processing strategy in README.md "To Consider" section

⏳ **Next Steps (In Progress):**
- Implement Follow activity processing with TO_DO.json queue
- Generate Accept activities for Follow requests (auto-accept mode)
- Activity delivery to followers (outgoing activities)
- HTTP signature verification for secure federation

⏳ **Future (Manual Approval):**
- Manual follow approval workflow when `auto_accept_follow_requests: false`
- Possible `/pending-followers` endpoint for management
- CLI tools for processing pending requests

The server now accepts incoming activities and manages followers, moving from "read-only" toward full federation capability.