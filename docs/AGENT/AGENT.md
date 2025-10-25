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
./client/new_post.py --title "Post Title" --content "Content" --url "https://yourblog.com/post" --summary "Optional"

# Edit existing posts
./client/edit_post.py --post-id "20250101-120000-my-post"
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
1. CLI tool (`client/new_post.py`) creates post JSON with timestamp+slug ID
2. CLI creates corresponding Create activity wrapping the post
3. CLI regenerates outbox by scanning activities directory (append-only)
4. Server serves all files without restart needed (Flask auto-reload in debug mode)

**Post Update Workflow:**
1. CLI tool (`client/edit_post.py`) loads existing post and prompts for changes
2. CLI updates post JSON and adds 'updated' timestamp
3. CLI creates corresponding Update activity wrapping the modified post
4. CLI regenerates outbox and delivers Update activity to all followers

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
- **Post Creation**: ID generation, file operations, CLI workflows
- **ActivityPub Endpoints**: All Flask routes (webfinger, actor, outbox, posts, activities, inbox, followers)
- **Activity Processing**: Complete workflow from inbox → queue → processing → completion
- **Configuration Strategy**: Test isolation with `TestConfigMixin` and module reload
- **Error Handling**: Malformed activities, missing files, content negotiation failures
- **Template System**: Outbox regeneration, streaming templates, error resilience
- **Integration Tests**: End-to-end workflows and cross-component interactions

**Test Stats**: 97 tests across 8 test files, all passing with proper isolation

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

## Recent Progress (2025-09-27)

**Activity Processing System (Completed):**
- ✅ **Implemented `activity_processor.py`** - Separate module using strategy pattern for clean separation
- ✅ **Extensible Processor Architecture** - Composite key system (`Follow`, `Undo`, `Undo.Follow`) for delegation
- ✅ **FollowActivityProcessor** - Adds followers to `followers.json`, generates Accept activities (respects auto-accept config)
- ✅ **UndoActivityProcessor** - Delegates to specific undo processors based on object type
- ✅ **UndoFollowActivityProcessor** - Removes followers from collection, handles non-existent followers gracefully
- ✅ **Registry-based Selection** - Clean lookup: `PROCESSORS[activity_type]` and `PROCESSORS['Undo.Follow']`
- ✅ **Symlink-based Queue** - Avoids concurrency issues with `static/inbox/queue/` directory
- ✅ **Config-driven Directories** - All paths use `config.json` for flexibility

**Shared Utility Functions:**
- ✅ **`generate_base_url(config)`** - Eliminates URL construction duplication
- ✅ **`get_followers_list(config)`** - Shared follower management between processors
- ✅ **Template System Integration** - All activities use Jinja2 templates (`accept.json.j2`)

**Complete Follow/Unfollow Workflow:**
- ✅ **Follow Processing** - Auto-accept (configurable), follower addition, Accept activity generation
- ✅ **Undo Follow Processing** - Follower removal, proper delegation through `UndoActivityProcessor`
- ✅ **Duplicate Handling** - Multiple follows from same actor handled correctly
- ✅ **Configuration Support** - Respects `auto_accept_follow_requests` setting
- ✅ **Error Resilience** - Handles missing actors, malformed activities, non-existent followers

**Test Infrastructure (16 Tests Passing):**
- ✅ **Comprehensive Coverage** - All follow/unfollow scenarios tested
- ✅ **Delegation Testing** - Verifies `UndoActivityProcessor` routes to correct sub-processors
- ✅ **Consistent Test Setup** - Module reload prevents config caching issues between tests
- ✅ **Edge Case Testing** - Non-existent followers, duplicate follows, auto-accept disabled
- ✅ **Integration Testing** - Complete workflow verification

**Architecture Improvements:**
- ✅ **Clean Separation** - Flask handles HTTP, processors handle federation logic
- ✅ **Extensible Design** - Easy to add `Undo.Like`, `Undo.Announce`, etc.
- ✅ **No Concurrency Issues** - Symlink-based queue prevents file conflicts
- ✅ **Template-driven** - All ActivityPub entities generated consistently

## Future Enhancements

**See README.md "What's Next" section for:**
- Recommended improvements (logging, activity ID naming, outbox organization)
- Future activity support (Update, Like, Announce, Delete)
- Client-to-Server (C2S) considerations

## Recent Progress (2025-10-05)

**HTTP Signatures Implementation (Completed):**
- ✅ **Implemented `http_signatures.py`** - Complete HTTP signature module following draft-cavage-http-signatures-12 spec
- ✅ **Signature Verification** - Verifies incoming ActivityPub requests (digest, date, cryptographic signature)
- ✅ **Signature Signing** - Signs outgoing requests for delivery to remote servers
- ✅ **Public Key Fetching** - Fetches and caches actor public keys with proper fragment handling
- ✅ **Configurable Security** - `require_http_signatures` config option (false for dev, true for production)
- ✅ **Inbox Integration** - Updated inbox endpoint with signature verification
- ✅ **Documentation** - Added comprehensive explanation of HTTP vs Linked Data signatures in README

**Key Functions:**
- `verify_request()` - Complete request validation (digest + date + signature)
- `sign_request()` - Generate HTTP signature for outgoing requests
- `fetch_actor_public_key()` - Fetch public keys following ActivityPub spec
- `build_signing_string()` - Construct signing string per draft-cavage-12
- `compute_digest()` - SHA-256 digest computation for body integrity

**Architecture Decisions:**
- Custom implementation (no library) - ActivityPub uses old draft spec (draft-cavage-12), not RFC 9421
- Algorithm `hs2019` per spec (not `rsa-sha256`)
- Fragment handling: Strip fragment for fetch, match full keyId including fragment
- Configurable enforcement: Accept unsigned in dev, require in production
- HTTP signatures only (Linked Data signatures documented for future consideration)

## Recent Progress (2025-10-12)

**Activity Delivery System (Completed):**
- ✅ **Implemented `activity_delivery.py`** - Complete delivery system with HTTP signature support
- ✅ **Accept Activity Delivery** - Auto-deliver Accept responses when processing Follow activities
- ✅ **Create Activity Delivery** - Auto-deliver new posts to all followers via `new_post.py`
- ✅ **Inbox URL Fetching** - Fetches remote actor inbox URLs with proper ActivityPub headers
- ✅ **Signed Requests** - All outgoing activities signed with HTTP signatures using actor's private key
- ✅ **Error Handling** - Graceful handling of delivery failures with detailed logging
- ✅ **Configurable User-Agent** - Uses config-based User-Agent string (defaults to 'TinyFedi/1.0')

**Key Functions:**
- `deliver_to_actor()` - Deliver activity to single actor (fetches inbox, signs, POSTs)
- `deliver_to_followers()` - Broadcast activity to all followers with delivery summary
- `deliver_activity()` - Core delivery function with HTTP signature authentication
- `fetch_actor_inbox()` - Fetch inbox URL from remote actor document

**Integration Points:**
- `activity_processor.py` - Auto-delivers Accept activities when processing Follow requests
- `new_post.py` - Auto-delivers Create activities to followers when publishing posts
- Uses `http_signatures.sign_request()` for all outgoing activity authentication
- Reads actor's publicKey.id from `actor.json` for dynamic key ID (no hardcoding)

**Workflow:**
1. Activity generated (Accept from processor, or Create from new_post.py)
2. For each recipient: fetch their inbox URL from actor document
3. Sign POST request with private key using HTTP signatures
4. Deliver activity to remote inbox
5. Log success/failure for each delivery

**Test Coverage (Completed):**
- ✅ **Implemented `tests/test_activity_delivery.py`** - Comprehensive unit tests for delivery module (12 tests)
- ✅ **Implemented `tests/test_integration_delivery.py`** - End-to-end workflow tests with mocked remote (2 tests)
- ✅ **Unit Test Coverage**:
  - `fetch_actor_inbox()` - Success, missing inbox, network errors, custom User-Agent
  - `deliver_activity()` - Success, network errors, missing actor keys
  - `deliver_to_actor()` - Success, no inbox handling
  - `deliver_to_followers()` - Success, partial failures, empty follower lists
- ✅ **Integration Test Coverage**:
  - Complete Follow → Accept workflow with mocked remote actor
  - Follow → Undo Follow state transitions
  - Verifies: inbox saving, queue processing, follower management, Accept generation, delivery with signatures
- ✅ **Total Test Suite** - 97 tests passing (83 existing + 12 unit + 2 integration tests)

**Current Status**: tinyFedi now has **complete bidirectional federation** with **comprehensive test coverage** - can receive activities, process them, and deliver responses and new content to followers!

## Recent Progress (2025-10-19)

**Code Quality & Documentation:**
- ✅ **Fixed Deprecation Warnings** - Replaced `datetime.utcnow()` with `datetime.now(UTC)` (Python 3.11+)
- ✅ **README Updates** - Added Update, Like, Announce, Delete activity specifications with implementation notes
- ✅ **C2S Documentation** - Added C2S vs Mastodon API comparison to "To Consider" section

**Current Status**: S2S federation complete. Python 3.11+ required. Zero deprecation warnings. Documentation expanded with future feature roadmap.