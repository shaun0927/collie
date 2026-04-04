# Known Limitations

This document lists the most important limitations that remain after the hardening work through PR-08.

## 1. Live governance integrations are only partially validated

The code now models and reacts to GitHub-native governance signals, but not every path has been validated against live repositories in CI.

Still recommended:
- sandbox validation for protected branches
- sandbox validation for merge queue
- sandbox validation for auto-merge enablement

## 2. Merge queue enqueue is only partially implemented

The executor can distinguish merge-queue-required situations, but merge queue behavior still depends on GitHub support and token capabilities. Unsupported paths should surface blocked results clearly.

## 3. Structured analyzer outputs depend on provider compliance

Collie now fails closed to `HOLD` when providers return malformed or non-JSON outputs. This is safer, but it can reduce automation quality if a provider drifts from the expected response contract.

## 4. Repo profiling is richer but still heuristic

Repo profiling now gathers significantly more signals, but it still uses inference and repository conventions rather than authoritative semantic understanding. Large or unusual repositories may still require manual philosophy tuning.

## 5. GitHub Action remains triage-first, not execution-first

The bundled Action is suitable for scheduled bark runs and queue refresh. It should not be treated as a drop-in autonomous execution workflow without additional sandbox validation.
