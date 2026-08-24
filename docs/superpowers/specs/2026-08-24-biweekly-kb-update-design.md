# Biweekly Knowledge Base Update → Docker Republish

**Date:** 2026-08-24
**Status:** Approved

## Goal

Run the knowledge base (KB) update automatically on a biweekly schedule, and
ensure updated Docker images are republished to Quay after each accepted update —
without shipping images that a maintainer has not reviewed.

## Current State

- **`.github/workflows/update-kb.yml`** — triggered manually only
  (`workflow_dispatch`). It clones the upstream wiki + scripts, regenerates
  chunks and the vector index, runs a search-quality gate and the test suite,
  then opens a pull request containing the updated data files under
  `mcp-server/data/**` (`metadata.json`, `usearch_index.bin`,
  `script_index.json`).
- **`.github/workflows/docker-publish.yml`** — triggered on push to `main` that
  touches `mcp-server/**`, `embedding-generation/**`, `s390x_kb_search/**`, or
  `pyproject.toml` (plus manual dispatch). Builds and pushes multi-arch
  `embeddings-latest` and `latest` images to
  `quay.io/ibm/s390x-porting-mcp`.

## Design

The change is intentionally minimal. The Docker republish path already exists;
only the schedule, the reviewer assignment, and the trigger cadence need to be
added.

### Change 1 — Add the biweekly schedule to `update-kb.yml`

Add a `schedule` trigger alongside the existing `workflow_dispatch`:

```yaml
on:
  schedule:
    - cron: "0 6 1,15 * *"   # 1st & 15th of each month, 06:00 UTC
  workflow_dispatch:
```

Rationale for `1,15`: GitHub Actions cron has no native "every two weeks"
expression. Running on the 1st and 15th gives a predictable, calendar-based
cadence of roughly 14–16 days with no extra skip-step logic. The existing manual
`workflow_dispatch` trigger is retained so maintainers can run an update on
demand.

All existing job steps are unchanged: clone upstream → generate chunks →
generate vector index → quality gate → tests → open PR.

### Change 2 — Assign a default reviewer on the PR

Add the `reviewers` input to the existing `peter-evans/create-pull-request`
step so every automated KB PR requests review from `vibhutisawant`:

```yaml
      - name: Create Pull Request
        uses: peter-evans/create-pull-request@v7
        with:
          reviewers: vibhutisawant
          # ...existing inputs unchanged...
```

Note: `vibhutisawant` must be a repo collaborator / org member with access. If
not, the action logs a warning and skips the reviewer assignment without failing
the run.

### Change 3 — Docker republish: no new code

No new workflow or edit to `docker-publish.yml` is required. When a maintainer
merges the KB PR into `main`, the push modifies files under `mcp-server/data/**`,
which matches `docker-publish.yml`'s existing `paths: mcp-server/**` filter. That
automatically rebuilds and pushes `embeddings-latest` and `latest` to Quay.

## Flow

```
biweekly cron (1st & 15th, 06:00 UTC)
  └─ update-kb job: clone upstream → regenerate KB → quality gate → tests
       └─ open PR (reviewer: vibhutisawant)
            └─ maintainer reviews & merges to main
                 └─ push touches mcp-server/data/** → docker-publish fires
                      └─ new embeddings-latest + latest pushed to Quay
```

The human merge is the gate: images are never republished without a maintainer
accepting the KB PR (satisfies the "PR, human merges" requirement).

## Non-Goals

- No auto-merge / direct-commit-to-main automation.
- No changes to the KB generation logic, quality gate thresholds, or the Docker
  build itself.
- No changes to the Jenkins pipeline (CI is fully on GitHub Actions).

## Notes / Risks

- GitHub disables scheduled workflows after 60 days of **no repository
  activity**. Not a concern for an active repo, but worth knowing if the project
  goes dormant.
- Scheduled runs execute against the workflow file on the repo's default branch.
- If an upstream update produces no changes, `create-pull-request` opens no PR
  (no-op), and no Docker rebuild occurs — which is the desired behavior.

## Testing / Verification

- Validate the workflow YAML parses (e.g. `actionlint` or a manual
  `workflow_dispatch` run).
- Trigger `update-kb.yml` manually once to confirm the PR opens with
  `vibhutisawant` requested as reviewer.
- Confirm that merging a PR touching `mcp-server/data/**` triggers
  `docker-publish.yml`.
