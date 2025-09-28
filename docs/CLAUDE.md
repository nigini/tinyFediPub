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
- **Post Creation**: ID generation, file operations, CLI workflows
- **ActivityPub Endpoints**: All Flask routes (webfinger, actor, outbox, posts, activities, inbox, followers)
- **Activity Processing**: Complete workflow from inbox → queue → processing → completion
- **Configuration Strategy**: Test isolation with `TestConfigMixin` and module reload
- **Error Handling**: Malformed activities, missing files, content negotiation failures
- **Template System**: Outbox regeneration, streaming templates, error resilience
- **Integration Tests**: End-to-end workflows and cross-component interactions

**Test Stats**: 43 tests across 6 test files, all passing with proper isolation

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

## Critical TODO Items

**High Priority (Security & Production Readiness):**

1. **Activity ID Naming System**
   - **Problem**: Timestamp-based IDs cause conflicts when activities processed in same second
   - **Solution**: Implement Content-Addressable Storage (CAS) using SHA-256 content hashes
   - **Benefits**: Guaranteed uniqueness, immutability, easy duplicate detection
   - **Example**: `accept-a7b9c3d2e1f4...` instead of `accept-20250927-234936`

2. **Outbox Directory Organization**
   - **Problem**: Outgoing activities scattered in `static/activities/` with incoming posts
   - **Solution**: Mirror inbox structure with dedicated outbox folders
   - **Structure**: `static/outbox/` with `queue/` subdirectory for delivery
   - **Benefits**: Clear separation, organized file management, future delivery queue

3. **HTTP Signature Verification (CRITICAL)**
   - **Problem**: Currently accepting activities without authentication (security vulnerability)
   - **Solution**: Implement RFC 9421 HTTP Signature verification
   - **Requirements**: Actor public key fetching, signature validation, error handling
   - **Priority**: Essential before production deployment

4. **Activity Delivery System**
   - **Problem**: Generated Accept activities not sent to follower inboxes
   - **Dependencies**: Requires HTTP signature implementation for outgoing signing
   - **Solution**: POST signed activities to follower inbox endpoints
   - **Scope**: Complete bidirectional federation capability

**Implementation Notes:**
- Use existing config system for new directory structures
- Leverage template system for consistent outgoing activity format
- Build on existing `generate_activity_id()` pattern for CAS implementation
- Integrate with current processor architecture for delivery queue

**Usage:**
```bash
# Process queued activities
python activity_processor.py

# Check what activities are queued
ls static/inbox/queue/

# Check processed activities
ls static/inbox/

# Check generated Accept activities
ls static/activities/accept-*
```

**Current Status**: The server now has **complete follow/unfollow processing** with proper delegation architecture. Next phase focuses on **security hardening** and **production deployment readiness**.