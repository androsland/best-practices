# Secure SaaS fixture

This directory is an inert virtual project used to test positive audit evidence. Files ending in `.fixture` preserve their logical application names for the audit engine but are never installed, executed, built, or deployed by this repository.

The root Python contract tests validate important security and rollout signals directly from these artifacts. The fixture marker activates logical-name mapping only when the audit targets this directory itself; ordinary repositories do not treat `.fixture` files as executable code.
