"""
data_access — Data primitives for tinyFedi.

Each submodule owns one domain (e.g. follow relationships) and exposes a
storage-agnostic API. Storage layout is an implementation detail of each
submodule; callers operate on domain values (actor URLs, activity IDs, etc.).
"""
