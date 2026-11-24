# Learning Log: Evolution Plan (V1.1 → V2.0)

This document plans the evolution of Learning Log from the finished Chapter 18–20
replica (see `plan.md`, complete through Phase 9) into a knowledge platform.

`plan.md` built the faithful replica: `User → Topic → Entry`, owner-scoped
queries, Bootstrap 5 layout, 144 tests. `new_plan.md` changes the target. The
replica is the seed; this is the tree.

**Read this document as a work order.** Sections 0–3 are the rules and the map.
Section 4 is the plan itself: a single ordered list of small phases, `Phase 1`
through `Phase 78`, grouped into five releases. Each phase is a unit of work
small enough to build, test, review, and merge on its own. Execute them in
order; the ordering is dependency-driven, not arbitrary. Sections 5–13 are
reference appendices the phases lean on.

---

## North star

> A platform where a learner does not simply record what they learned. They
> organize knowledge, measure understanding, find their weak spots, and
> systematically build expertise.

Every feature below serves that sentence. If a feature does not move a learner
closer to "organized knowledge + measured understanding + systematic expertise,"
it does not belong in a release.

---

## 0. Principles

These are the rules the whole plan obeys. They are non-negotiable and they gate
every phase the same way the replica's CLAUDE.md gated every stage.

### P0. Database-driven by default (the headline)

System configuration, feature availability, and workflow logic live in the
database, not in code. A behavior that an operator might reasonably want to change
without a deploy must be data.

What this means concretely:

| Concern | Hardcoded (wrong) | Data-driven (right) |
| --- | --- | --- |
| Which features are live | `if ENABLE_QUIZZES:` in a view | a `FeatureFlag` row resolved at request time |
| Spaced-repetition intervals | a Python list constant | a `Setting` row (`srs.intervals`) |
| Topic lifecycle steps | an `if status == ...` chain | a `WorkflowDefinition` + transitions |
| Who can publish | `if user.is_staff:` | `Role` + `Permission` grants resolved from the DB |
| Reminder cadence | a cron in a file | `ScheduleConfig` rows read by Celery beat |
| Notification wording | a string literal in a task | `NotificationTemplate` rows |
| Retention/limits (uploads, rate caps, AI quotas) | magic numbers | `Setting` rows, scoped |

The runtime access pattern is one function, used everywhere:

```python
from core.config import settings, feature_enabled, workflow_for

limit = settings.get('media.max_upload_mb', scope=user)        # typed, validated, cached
if feature_enabled('quizzes', user=request.user):              # flag + rollout rules
    ...
wf = workflow_for('topic', space=space)                        # DB-defined state machine
```

#### The guardrail against over-engineering

Database-driven is a scalpel, not a religion. We do **not** build a general
rules engine that reimplements the application in data, and we do **not** move
genuinely fixed things into tables. Ask three questions about a value:

1. Would an operator plausibly want to change it as normal platform operation —
   not a code change, and not an infrastructure/env setting?
2. Does it vary by scope (global, per-user, per-space)?
3. Is it part of a workflow whose states and transitions a customer might redefine?

**Any single yes makes it data.** The three are independent, not cumulative. A
scoped value like `srs.intervals` answers yes to Q1 only; a `FeatureFlag` answers
yes to Q1 only; both are data. Q3 is the strongest yes (a whole state machine),
but it is not a required one. Three noes — and only these — cover values that are
structural: the `on_delete` rule on a foreign key, the schema of a model, the
HTTP method a form posts with. Infrastructure and security values that vary by
deployment (e.g. `SECURE_HSTS_SECONDS`) are neither code literals nor DB rows:
they come from environment variables, the replica's existing rule. This
distinction is enforced in code review and recorded per field in the data model
appendix (Section 6). It is the difference between a configurable platform and
an unmaintainable one.

### P1. Services-first (unchanged from the replica's rules)

One bounded concern, one directory. Business logic lives in a service or app, not
in root-level glue. Two sessions working on different features never touch the
same files. Contracts live in `contracts/`.

### P2. Every feature ships tests AND evals, in the same commit

Gate tests are deterministic, local, free, under two seconds, run on every
commit. Evals measure quality against a reference set and are run nightly and
before ship with a pass threshold. There are two kinds, and every feature ships
one:

- **Model evals (paid)** for AI features: a golden set scored against a threshold
  (Section 4.3 and Section 8).
- **Corpus evals (free, deterministic)** for everything else: a golden corpus or
  reference table run as a periodic job, not merely a unit test. Search gets a
  relevance corpus, the SRS scheduler gets a one-year reference simulation, export
  gets a round-trip corpus, aggregation gets a rebuild-and-diff corpus.

No feature merges without both its gate tests and its eval in the same commit.
No bug fix merges without a regression test and an eval that would have caught it.

### P3. AI goes through one service layer, never through the views

No view, model, or template imports an LLM client. Everything calls
`services/llm` over a typed contract. Per the workspace rule, that service shells
out to the **local Claude Code**, not a hosted API, unless Brian explicitly
authorizes an API. This is also the only place that enforces cost, caching,
rate limits, prompt versioning, and audit. (Section 7 has the contract;
Section 11 flags the one hard deployment question this creates.)

### P4. Vanilla, proven tech. Do not rebuild what exists.

Django, PostgreSQL, Redis, Celery, and existing libraries before custom code.
Before writing any utility (Markdown rendering, PDF export, full-text search,
SRS scheduling), search for the maintained library that already does it and
prefer that. Reach for a new datastore only when Postgres is measured to be
insufficient.

### P5. Security and auditability are default, not a phase

Owner-scoped queries (the replica's Phase 4/5 rule) stay. RBAC and audit logging
arrive in V1.1 as the foundation, not bolted on at V2.0. Rate limiting and abuse
protection (A9.4) is a V2.0 concern, stated once, in the roadmap and Section 9.

### P6. Every change names its measurable outcome

A metric, a workflow step, or a user-visible behavior that changes. "It works"
is not an outcome. If it cannot be stated, that is a Confusion Protocol stop.

---

## 1. Architecture

### 1.1 System context

```
                        +-----------------------------+
   Browser / PWA  --->  |  web  (Django: apps + DRF)   |
                        +--------------+--------------+
                                       |
        +------------------------------+------------------------------+
        |                              |                             |
   PostgreSQL                   Redis (cache,                services/llm
   (+ pgvector,                 sessions, broker)            (AI gateway)
    full-text search)                  |                             |
        |                        Celery workers                     |
        |                        + beat scheduler                  |
        +-----------------------------------------------------------+
                                       |
                                services/notifications
                                Object storage (media, exports, backups)
```

### 1.2 Services and apps (each self-contained: code, tests, evals, README, config)

`services/` holds **separate deployables only** (`services/llm`,
`services/notifications`), reserved for components with genuinely different
runtime needs (Section 12). Everything else is a Django app inside the single
`web` deployable; the table names the app, and `services/…` where a separate
deployable exists.

| Service / app | Concern | Ships |
| --- | --- | --- |
| `web` (Django project) | HTTP, templates, DRF API, auth, RBAC enforcement | V1.1 |
| `accounts` (Django app, exists) | Auth, registration, MFA (V2.0), OAuth (V2.0) | V1.1 (exists; grows in V2.0) |
| `core` (Django app) | The DB-driven config engine: settings, flags, workflows, roles, templates, schedules | V1.1 |
| `learning_logs` (Django app) | Topics, entries, editor, attachments, versioning | V1.1 (extends the replica) |
| `search` (Django app) | Full-text and semantic search, indexing | V1.1 |
| `analytics` (Django app) | Event capture, aggregates, dashboards | V1.2 |
| `services/llm` (separate, deployable) | The AI gateway. The only component that calls a model | V1.3 |
| `paths` (Django app) | Roadmaps, modules, lessons, prerequisites, schedules | V1.4 |
| `assessment` (Django app) | Quizzes, flashcards, SRS, retention | V1.3 (quizzes), V1.4 (SRS) |
| `community` (Django app) | Spaces, sharing, groups, comments, follows | V2.0 |
| `productivity` (Django app) | Goals, tasks, timer, reminders, reports, calendar | V1.2 (goals), V2.0 (calendar, tasks) |
| `services/notifications` | Email/push/reminder delivery, DST-aware scheduling | V1.2 |
| `contracts/` | JSON Schema for every cross-service boundary | V1.1 onward |

`learning_logs` and `accounts` already exist. `accounts` grows MFA and OAuth in
V2.0.

### 1.3 Data stores

| Store | Role | Introduced |
| --- | --- | --- |
| PostgreSQL | Primary DB; JSONB for settings, `tsvector` full-text search, `pgvector` for embeddings | V1.1 (replaces SQLite) |
| Redis | Cache, Celery broker, rate-limit counters, sessions | V1.1 |
| S3-compatible object storage | Attachments, exports (backup snapshots arrive in V2.0) | V1.1 |
| pgvector | AI embeddings for recommendations, gaps, related content | V1.3 |

Postgres is the workhorse. Meilisearch/OpenSearch is deliberately **not** added;
Postgres full-text search with `tsvector` and GIN indexes covers the scale this
project will realistically reach. That is a P4 decision, revisited only on
measured latency, not on speculation.

### 1.4 The `core` app: the DB-driven configuration engine

This is the spine of P0. Five model families.

**`Setting`**: typed, scoped key-value configuration.

```
Setting
  key              slug, unique per scope            e.g. "media.max_upload_mb"
  value            JSONB                             the value
  value_type       enum(str,int,float,bool,json,duration,cron)
  scope_type       enum(global,user,space)
  scope_id         nullable FK to the scoped object
  is_secret        bool                              never returned to the client, never logged
  description      text                              shown in the admin
  updated_by       FK User, updated_at
```

Resolution precedence: user over space over global. Every read is
validated against `value_type` and cached in Redis with a key that includes the
scope. A bad value fails loudly at write time (admin validation) and is rejected
at read time (returns the default, logs an audit event).

`is_secret` covers **tenant-level operational secrets** only — a value a customer
or operator supplies for their own tenant (a per-space integration key, a
customer-supplied SMTP password, an OAuth client secret for a space). The
decision rule: if the value belongs to the deployment (it configures our
infrastructure), it is an env var; if it belongs to a tenant and is changed at
runtime through the admin, it is an `is_secret` `Setting`. Such rows are
encrypted at rest with Fernet (`cryptography`, key from `SETTINGS_ENCRYPTION_KEY`
in the environment), never returned to a client, and never logged (a gate test
asserts secret values do not appear in structured logs). **Infrastructure
secrets** (`DJANGO_SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `S3_*`,
`SETTINGS_ENCRYPTION_KEY`) are never `Setting` rows; per the replica's rule they
come from environment variables only.

**`FeatureFlag`**: runtime feature availability.

```
FeatureFlag
  key            slug                                e.g. "quizzes"
  enabled        bool
  rollout        JSONB   {percentage, roles[], users[], spaces[], not_before, not_after}
  description    text
```

`feature_enabled(key, user=..., space=...)` evaluates enabled + rollout. This is
how every later feature turns on and how it can be dark-launched or killed
without a deploy.

**`WorkflowDefinition` / `WorkflowState` / `WorkflowTransition`**: declarative
state machines.

```
WorkflowDefinition   key, entity ("topic","entry","lesson","roadmap","task"), version
WorkflowState        workflow FK, name, is_initial, is_terminal, order
WorkflowTransition   workflow FK, from_state, to_state, guard (JSONB: role/permission/condition), label
```

A topic's lifecycle (draft, in progress, reviewing, mastered) is a
`WorkflowDefinition`. Guard expressions name permissions, not code, so a customer
can redefine the lifecycle. Attaching a workflow to an entity is a FK on that
entity (`Topic.workflow_state`), defaulting to the entity's default workflow.

**`Role` / `Permission` / `RoleAssignment`**: RBAC as data.

```
Permission       codename ("topic.publish","space.moderate"), description
Role             name ("owner","editor","viewer","moderator"), permissions M2M
RoleAssignment   subject (user|group) + role + scope (global|space)
```

Authorization is `has(user, 'topic.publish', space=...)`. No `if user.is_staff`
anywhere in domain code. Django's built-in permissions remain for the admin;
the domain layer reads `RoleAssignment`.

**`NotificationTemplate`** (email/push body with variables) and
**`ScheduleConfig`** (Celery beat entries read from the DB). These make messaging
and cadence data too.

**`AuditRecord`**: append-only. `actor` FK (nullable for system events), `action`,
`target_type`/`target_id`, `before`/`after` JSONB (secret values redacted),
`request_id`, `created_at`. There is no update or delete path; the table is
granted insert-only. Every config write, admin change, and auth event (Section 9,
A9.3) lands here.

Everything above is registered in the Django admin with inline validation and
every write emits an audit record (Section 9). A change to a flag, setting, role,
or workflow is a first-class, audited product operation.

### 1.5 Contracts

Every cross-service boundary is a versioned JSON Schema under
`contracts/<service>/v1/`. Both sides import the same schema, and a contract
change is called out explicitly (the replica's contract rule, unchanged). The
first and most important contract is the LLM service (Section 7).

---

## 2. How phases are executed

The plan is delivered as **78 small phases**, in dependency order. This section
defines what a phase is and how each one is run, so the plan is executable
without re-deciding the process every time.

### 2.1 What a phase is

A phase is the smallest unit that delivers one coherent, user-visible or
operator-visible capability and can be merged on its own, leaving `main` green.
A phase:

- touches one concern (one app, one service, one feature), so two phases never
  fight over the same files (P1);
- ships its own migrations, tests, and eval in the same commit (P2);
- states its measurable outcome (P6);
- names the `Setting`/flag/workflow rows it introduces (P0), or states why none
  are needed.

If a phase turns out bigger than one concern, split it; the numbering in
Section 4 is the intended split, not a ceiling. If a phase is blocked by an
undecided fork, it stops and asks (Section 11).

### 2.2 The per-phase protocol

Each phase runs the discipline of the replica, scaled to its size (see the
workspace CLAUDE.md "Task sizing"):

1. **Triage block** printed before any work: size, which tests run, solo or
   fan-out, and the branch.
2. **Branch** per the workspace Branching rules (solo mode on this repo:
   branch in place, merge yourself; team mode: worktree + PR).
3. **Build** the phase, writing gate tests and its eval in the same commit.
4. **Cold critic pass** for any phase that changes behavior or is judgment-heavy
   — a separate agent that never saw the build, judged against the phase's
   reference. Bug-fix phases get the attacker critic (re-break the fix).
5. **Self-rating** 1–10 from a fresh read of the diff; loop until the honest
   answer is "proud."
6. **Merge + report**, with a restart note.

### 2.3 The phase record

Every phase in Section 4 is written in the same five-line shape so it can be
copied straight into a task:

- **Objective** — the outcome in one sentence.
- **Deliverables** — the concrete models, views, tasks, contracts, and templates.
- **Config (P0)** — the `Setting`/flag/workflow rows it adds, or "none."
- **Acceptance** — the measurable, checkbox-able proof it works.
- **Tests / evals** — which lane runs (gate vs. eval) and what the eval scores.

---

## 3. Release roadmap

| Release | Theme | Primary areas | Enabling platform work | Phases |
| --- | --- | --- | --- | --- |
| **V1.1** | Knowledge core | Area 2 (rich text, attachments, search, bookmarks, linking, collections, versions) | Postgres, Redis, Celery, `core` config engine, RBAC, audit, CI/CD, object storage | 1–24 |
| **V1.2** | Analytics and goals | Area 3 (dashboard, activity, stats, streaks, progress, reports) + goals/reminders (A7.2, A7.3, A7.6) | `analytics`, `services/notifications`, daily/weekly Celery beat, monitoring | 25–35 |
| **V1.3** | The AI layer | Area 1 (summaries, assistant, tagging, recommendations, quizzes, gaps, objectives) + quizzes/self-assessment (A5.2, A5.3, A5.4) | `services/llm`, `pgvector`, AI caching/quotas, AI evals | 36–48 |
| **V1.4** | Paths and retention | Area 4 (roadmaps, modules, lessons, prerequisites, schedules) + flashcards/SRS/retention (A5.1, A5.5, A5.6) | SRS scheduler (in the `assessment` app), reminder integration | 49–59 |
| **V2.0** | Community and platform | Area 6 (spaces, sharing, groups, comments, follows) + Area 8 (PWA, themes, REST API, OAuth, export, backups, offline) + remaining productivity (A7.1, A7.4, A7.5) + remaining infra (A9.2, A9.4) | DRF+OpenAPI, OAuth, MFA, rate limiting, PWA/offline, observability | 60–78 |

Each phase is independent enough to build in parallel where the numbers allow,
each passes a cold critic before merge, and the full per-release suite plus
evals is the gate.

---

## 4. Phase plan (ordered)

Execute top to bottom. Within a release, phases are ordered by dependency. Two
phases can be parallelized only when they touch different apps and files; within
a single app (e.g. Phases 13–15, 19–20, 39–48) they are sequential.

Two phases are explicit **serialization points** and must run alone, never
alongside another phase: **Phase 24** (the V1.1 RBAC sweep, which touches every
V1.1 view) and **Phase 48** (the V1.3 AI-flag/cost wiring, which touches every AI
UI). Likewise, the V1.3 AI phases each register a capability in
`services/llm/prompts/`; run them sequentially or give each its own prompt file
up front, so two sessions do not edit the capability registry at once.

### 4.1 Release V1.1 — Knowledge core (Phases 1–24)

**Objective:** turn notes into structured, searchable, richly formatted,
versioned knowledge, and stand up the platform foundation so every later release
is config, not a rewrite.

**Measurable outcome:** a user can attach a PDF and an image to an entry, write
it in Markdown with highlighted code, link entry to entry, find any word across
all their material in under 300 ms, bookmark it, and see and restore a prior
version. Postgres, Redis, and Celery are live; a feature flag toggles a UI
element with no deploy.

**In scope:** A2.1–A2.8, plus foundation A9.1, A9.3, A9.5, A9.6, A9.7, A9.9,
A9.10.

**Data model additions**

| Model | Key fields | Notes |
| --- | --- | --- |
| `Entry` (extend) | `body_markdown`, `body_html` (rendered+cached), `workflow_state` FK, `updated_at` | `text` renamed to `body_markdown` by a data migration; rendering server-side, sanitized |
| `EntryVersion` | `entry` FK, `revision` int, `body_markdown`, `author`, `created_at` | snapshot on save (A2.8) |
| `Attachment` | `entry` FK, `file`, `original_name`, `content_type`, `size`, `checksum` | stored on object storage |
| `Link` | `from_entry`, `to_topic`/`to_entry`, `label` | internal links (A2.4) |
| `Collection` | `owner`, `name`, `parent` FK self | folders (A2.7) |
| `CollectionItem` | `collection`, `content_type`, `object_id`, `order` | generic membership |
| `Bookmark` | `user`, `content_type`, `object_id`, `created_at` | generic favorites (A2.6) |
| `SearchDocument` | `content_type`, `object_id`, `tsvector` | Postgres FTS index table (A2.5). Vectors are **not** stored here; they live in the separate `Embedding` model (V1.3, Phase 38), which is the single embedding store. |

**Config introduced:** `media.allowed_types`, `media.max_upload_mb`,
`media.thumbnail_sizes`, `search.page_size`, `search.snippet_length`,
`editor.markdown_flavor`, `versions.max_per_entry`, `collections.max_depth` as
`Setting` rows; `rich_editor`, `attachments`, `bookmarks`, `internal_links`,
`collections`, `version_history` as `FeatureFlag` rows; the `topic` and `entry`
lifecycles as `WorkflowDefinition` rows; `RoleAssignment` seeded with
owner/editor/viewer/moderator.

Each `Setting`/flag/workflow row is seeded by the phase that introduces it, so
the release-level list above is the union, not a single seeding step: Phase 7a
seeds `media.max_upload_mb`, `search.page_size`, `search.snippet_length`; Phase 8
seeds the flags; Phase 9a the workflows; Phase 10 the roles; Phase 13 seeds
`editor.markdown_flavor`; Phase 16 seeds `media.allowed_types`; Phase 17 seeds
`media.thumbnail_sizes`; Phase 18 seeds `versions.max_per_entry`; Phase 22 seeds
`collections.max_depth`.

**Release acceptance:** every list/route query stays owner-scoped (no regression
of the replica's IDOR protection) and RBAC is checked in addition to ownership;
an upload over `media.max_upload_mb` is rejected, and raising the `Setting`
allows it with no code change; Markdown rendering is sanitized; every config
write emits an audit record; `Entry.text` carries into `body_markdown` with no
content loss.

**Release tests / evals:** gate — model/view/RBAC/search/XSS/upload-limit tests
(extends the existing 144). Corpus evals (free) — search relevance, Markdown
golden set, version-restore round-trip. No paid evals.

---

**Phase 1 — Postgres foundation and env split**
- Objective: the app runs on PostgreSQL locally, in tests, and in production with no SQLite in the code path.
- Deliverables: `DATABASES` reads `DATABASE_URL` (via `dj-database-url`) at all times; `docker-compose.yml` (or an equivalent local Postgres) for dev; pytest DB on Postgres; `pgvector` extension present where available.
- Config (P0): none (infrastructure → env vars, per the replica's rule).
- Acceptance: the existing 144 tests pass against Postgres; `manage.py check --deploy` is clean; no `db.sqlite3` reference remains.
- Tests / evals: gate — full existing suite on Postgres; a `pytest.ini` change recorded.

**Phase 2 — Redis wiring**
- Objective: a single Redis serves cache and is ready for sessions, broker, and counters.
- Deliverables: `CACHES` → Redis; `django-redis` (or built-in backend); a `cache` health check; local Redis in the dev compose file.
- Config (P0): none (infrastructure).
- Acceptance: a cached value survives a process restart; health check reports Redis up/down.
- Tests / evals: gate — cache read/write/invalidation test; health-check test with a mocked down Redis.

**Phase 3 — Celery app, worker, and beat**
- Objective: background tasks run out of process, on a schedule.
- Deliverables: Celery app in `ll_project/celery.py`; `worker` and `beat` processes added to `Procfile`; a trivial heartbeat task.
- Config (P0): the beat schedule is *not* hardcoded here — it loads from `ScheduleConfig` once Phase 11 exists; until then, an empty schedule.
- Acceptance: a queued task runs in a worker; `manage.py check` stays clean.
- Tests / evals: gate — task runs eagerly in tests; a broker-connection test.

**Phase 4 — Object storage and media settings**
- Objective: uploads go to S3-compatible storage in production, filesystem locally.
- Deliverables: `django-storages` + `boto3`; `STORAGES['default']` switches on `S3_*` env vars; `MEDIA_URL`/`MEDIA_ROOT`; a smoke upload test.
- Config (P0): none (infrastructure).
- Acceptance: a file uploaded in a test lands in the configured backend; local dev uses the filesystem with no S3 credentials required.
- Tests / evals: gate — storage-backend selection test; upload round-trip.

**Phase 5 — CI/CD pipeline**
- Objective: every push is linted, migration-checked, and tested automatically.
- Deliverables: GitHub Actions workflow with Postgres + Redis service containers; steps: install, `ruff`/`flake8` lint, `makemigrations --check --dry-run`, `pytest`; a deploy job template gated on `main`.
- Config (P0): none.
- Acceptance: the workflow is green on the Phase 4 commit; a deliberately failing migration check turns it red.
- Tests / evals: gate — the pipeline itself; a recorded run URL.

**Phase 6 — `core` app scaffold**
- Objective: the config engine gets its own app, ready for models.
- Deliverables: `core/` app with `apps.py`, `admin.py`, `urls.py`, `tests/`, empty initial migration, README stub.
- Config (P0): none.
- Acceptance: app is installed, admin loads, `makemigrations --check` clean.
- Tests / evals: gate — app-loads smoke test.

**Phase 7a — `Setting` model, migration, and admin (the P0 spine)**
- Objective: the configuration store exists and is editable from the admin.
- Deliverables: `Setting` model + migration + admin with create/edit forms; write-time validation against `value_type`; seeds the initial rows (`media.max_upload_mb`, `search.page_size`, `search.snippet_length`).
- Config (P0): this phase *is* the config store.
- Acceptance: a `Setting` row can be created and edited in the admin; a value that fails its `value_type` is rejected at write with a clear error.
- Tests / evals: gate — model, admin-form, write-validation tests.

**Phase 7b — Typed, scoped, cached accessor and secret encryption**
- Objective: one read path, with precedence, caching, and secrets, that every later phase uses.
- Deliverables: `core/config.py` with `settings.get(key, scope=…)`; precedence user > space > global; type coercion/validation against `value_type`; a Redis cache keyed by (key, scope); Fernet encryption for `is_secret` rows (key from `SETTINGS_ENCRYPTION_KEY`); a write hook that Phase 12 wires to `AuditRecord`.
- Config (P0): none beyond Phase 7a's rows.
- Acceptance: changing a `Setting` from the admin changes behavior with no deploy; a bad stored value falls back to the default + audits at read; precedence is user > space > global; a secret value never appears in logs or serialized output.
- Tests / evals: gate — precedence, coercion, cache-invalidation, secret-redaction tests.

**Phase 8 — `FeatureFlag` and `feature_enabled()`**
- Objective: every later feature can be dark-launched or killed without a deploy.
- Deliverables: `FeatureFlag` model + migration + admin; `feature_enabled(key, user=, space=)` evaluating `enabled` + `rollout` (percentage, roles, users, spaces, not_before/not_after).
- Config (P0): seeds the V1.1 flags (`rich_editor`, `attachments`, `bookmarks`, `internal_links`, `collections`, `version_history`), all off.
- Acceptance: flipping a flag row changes UI availability with no deploy; a percentage rollout is deterministic per user; a not-yet-active flag is off.
- Tests / evals: gate — rollout evaluation table, deterministic bucketing, time-window tests.

**Phase 9a — Workflow models and admin**
- Objective: entity lifecycles are stored as data.
- Deliverables: `WorkflowDefinition`/`WorkflowState`/`WorkflowTransition` + migration + admin; seeds the `topic` and `entry` workflows (draft → in progress → reviewing → mastered).
- Config (P0): the `topic` and `entry` `WorkflowDefinition` rows.
- Acceptance: workflow rows are editable in the admin; states and transitions persist with their order and terminal flags.
- Tests / evals: gate — model/admin tests, seed integrity.

**Phase 9b — Workflow engine, guards, and entity FKs**
- Objective: entities move along their workflow, with guards that are data, not `if status ==` chains.
- Deliverables: `workflow_for(entity, space=…)`; a guard evaluator that reads permissions/conditions from the transition's JSONB, never code; `Topic.workflow_state` and `Entry.workflow_state` FKs.
- Config (P0): none beyond Phase 9a's rows.
- Acceptance: a topic's state only moves along defined transitions; a guard denies a user without the named permission; redefining a workflow row changes allowed transitions with no deploy.
- Tests / evals: gate — transitions allowed/denied, guard evaluation, terminal-state behavior.

**Phase 10 — RBAC models and `has()`**
- Objective: authorization is grants in the DB, never `is_staff`.
- Deliverables: `Permission`/`Role`/`RoleAssignment` + migration + admin; `has(user, codename, space=…)`; a seed migration with owner/editor/viewer/moderator roles.
- Config (P0): the roles and permissions themselves.
- Acceptance: `has()` resolves a user's effective permission through role assignments; a user without a grant is denied; Django admin permissions stay separate.
- Tests / evals: gate — grant/deny matrix, scoped vs. global assignments, seed integrity.

**Phase 11 — `NotificationTemplate` and `ScheduleConfig`**
- Objective: message wording and job cadence are data.
- Deliverables: `NotificationTemplate` (channel, subject, body, variables) + `ScheduleConfig` (name, crontab fields, enabled) models + admin; a Celery-beat loader that reads enabled `ScheduleConfig` rows at startup and on change.
- Config (P0): initial template + schedule rows for later releases (inactive until their phase).
- Acceptance: editing a template changes the rendered message with no deploy; a disabled `ScheduleConfig` row removes its beat entry after reload.
- Tests / evals: gate — template rendering with variables, beat-schedule loading from rows.

**Phase 12 — `AuditRecord`, append-only + wiring**
- Objective: every config, admin, and auth write leaves an immutable trace.
- Deliverables: `AuditRecord` model (no update/delete path; insert-only DB grant) + `audit(actor, action, target, before, after, request_id)` helper; a request-id middleware; wiring of Phase 7b–11 config writes and login/logout events.
- Config (P0): none (it records them).
- Acceptance: a config change writes exactly one audit row; no code path updates or deletes an audit row (asserted); secret values are redacted in `before`/`after`.
- Tests / evals: gate — write-on-config-change, immutability, redaction, request-id propagation.

**Phase 13 — Markdown pipeline**
- Objective: entries render as sanitized HTML from Markdown, with the library choice recorded (P4).
- Deliverables: render + sanitize pipeline (server-side; `markdown` + `nh3`/`bleach`, per decision 2 in Section 11); a `render_markdown()` entry point; `editor.markdown_flavor` `Setting`.
- Config (P0): `editor.markdown_flavor`.
- Acceptance: an XSS payload in Markdown is inert in output; the same input renders deterministically.
- Tests / evals: gate — XSS-in-Markdown cases, determinism. Corpus eval — a Markdown golden set (input → expected sanitized HTML).

**Phase 14 — Entry schema migration (`text` → `body_markdown`)**
- Objective: entries store Markdown plus cached HTML and a workflow state, with zero content loss.
- Deliverables: a schema migration renaming `text` → `body_markdown` and adding `body_html`, `workflow_state`, `updated_at`; a data migration rendering existing bodies to `body_html`.
- Config (P0): none (schema per Section 1.4's rule; the entry workflow itself is Phase 9a).
- Acceptance: a pre-migration fixture's content appears unchanged in `body_markdown`; every existing entry gains a non-null `body_html` and a default `workflow_state`.
- Tests / evals: gate — migration round-trip against the fixture; render-back equality.

**Phase 15 — Entry editor UI (Markdown + preview + highlighting)**
- Objective: a user writes Markdown, sees a preview, and code blocks are highlighted.
- Deliverables: editor template/view with a Markdown textarea, a preview endpoint or client-side render using the Phase 13 pipeline, and a syntax-highlighting stylesheet/JS (Pygments server-side or a small highlight lib); `rich_editor` flag gates the new UI.
- Config (P0): `rich_editor` flag.
- Acceptance: saving preserves Markdown; preview matches the server render; code blocks render highlighted; flag off falls back to the plain textarea.
- Tests / evals: gate — save/preview view tests, flag-on/off rendering.

**Phase 16 — Attachments (upload, validation, storage)**
- Objective: images, PDFs, and documents attach to entries under operator-set limits.
- Deliverables: `Attachment` model + upload form/view + storage wiring (Phase 4); enforcement of `media.allowed_types` and `media.max_upload_mb` (Phase 7a/7b); per-entry attachment list; `attachments` flag.
- Config (P0): `media.allowed_types`, `media.max_upload_mb`, `attachments` flag.
- Acceptance: a disallowed type is rejected; a 60 MB file is rejected, and raising `media.max_upload_mb` allows it with no code change (proves P0); only the owner can attach or view.
- Tests / evals: gate — type/size enforcement driven by a `Setting`, owner-scoping, upload/view round-trip.

**Phase 17 — Attachment post-processing (thumbnails + scan)**
- Objective: image derivatives and content validation happen off the request path.
- Deliverables: `Thumbnailer` Celery task (image derivatives) and `AttachmentScanner` task (content-type sniff, checksum, size confirmation).
- Config (P0): `media.thumbnail_sizes` (JSONB list of `{w, h}`).
- Acceptance: an uploaded image produces thumbnails asynchronously; the scanner records a checksum and flags a mismatched content type.
- Tests / evals: gate — task execution eager, thumbnail generation, scanner verdicts.

**Phase 18 — Version history and restore**
- Objective: every edit is recoverable.
- Deliverables: `EntryVersion` model; a snapshot service called on entry save; a list view and a restore action that writes a new revision (never overwrites history); `version_history` flag.
- Config (P0): `version_history` flag; `versions.max_per_entry`.
- Acceptance: editing an entry creates a new `EntryVersion`; restoring a prior version reproduces its exact `body_markdown`; history is owner-scoped.
- Tests / evals: gate — snapshot-on-save, restore fidelity. Corpus eval — version-restore round-trip.

**Phase 19 — Full-text search backend**
- Objective: every entry is indexed for search on save.
- Deliverables: scaffold the `search` app (`INSTALLED_APPS`, empty initial migration, tests package); `SearchDocument` model with a `tsvector` column + GIN index; a `SearchIndexer` Celery task triggered on entry save (via the Phase 3 worker). No vector/embedding column here — vectors arrive as the separate `Embedding` model in Phase 38.
- Config (P0): none (index mechanics are schema).
- Acceptance: saving an entry updates its `tsvector`; a term present only in another user's private entry is never matched; reindexing is idempotent.
- Tests / evals: gate — index-on-save, idempotent reindex, cross-user exclusion.

**Phase 20 — Search UI, ranking, and snippets**
- Objective: fast, ranked, highlighted search across a user's material.
- Deliverables: search view + template using Postgres ranking and `ts_headline` snippets; pagination driven by `search.page_size` and snippet length by `search.snippet_length`; an owner-scoped queryset.
- Config (P0): `search.page_size`, `search.snippet_length`.
- Acceptance: a query returns ranked results with highlighted snippets in under 300 ms on the reference corpus; changing `search.page_size` changes pagination with no deploy; cross-user leakage test fails closed.
- Tests / evals: gate — ranking order, pagination, owner-scoping. Corpus eval — search relevance (query → ranked expected results).

**Phase 21 — Internal linking and backlinks**
- Objective: topics and entries link to each other, and each shows what links to it.
- Deliverables: `Link` model; a link syntax or picker in the editor that resolves to a topic/entry; a backlinks panel on the target; `internal_links` flag.
- Config (P0): `internal_links` flag.
- Acceptance: linking entry A to entry B shows A in B's backlinks; a link to a non-owned target is refused; deleting a target cleans up dangling links.
- Tests / evals: gate — link creation, backlink resolution, ownership refusal, dangling-link cleanup.

**Phase 22 — Collections and folders**
- Objective: users group topics and entries into nested folders.
- Deliverables: `Collection` (self-referential `parent`) + `CollectionItem` (generic membership) + CRUD views; `collections` flag.
- Config (P0): `collections` flag; `collections.max_depth`.
- Acceptance: a collection holds topics and entries; nesting works and is depth-limited by a `Setting`; only the owner sees or edits a collection.
- Tests / evals: gate — membership, nesting/depth limit, owner-scoping.

**Phase 23 — Bookmarks and favorites**
- Objective: a user marks any topic or entry as a favorite and finds them quickly.
- Deliverables: `Bookmark` model (generic) + toggle endpoint + a favorites list page; `bookmarks` flag.
- Config (P0): `bookmarks` flag.
- Acceptance: toggling bookmarks a topic or an entry; a user's favorites list is owner-scoped; unflagged deployment hides the feature.
- Tests / evals: gate — toggle idempotency, generic-target coverage, owner-scoping.

**Phase 24 — RBAC enforcement sweep + DB optimization**
- Objective: close V1.1 by enforcing RBAC everywhere and putting the DB on a budget.
- Deliverables: replace any remaining `is_staff`/`is_superuser` in domain code with `has()`; enforce `has()` on all V1.1 views; `select_related`/`prefetch_related` on hot paths; indexes justified by `EXPLAIN`; a documented query-budget note in `reference-inventory.md`.
- Config (P0): any new permission codenames as rows.
- Acceptance: no domain-code `is_staff` (asserted by a grep/AST test); a two-user RBAC matrix passes; the search + dashboard pages meet their latency budgets on a seeded dataset; every V1.1 page is verified usable at mobile, tablet, and desktop widths (A8.2, held from V1.1 onward).
- Tests / evals: gate — RBAC matrix, no-`is_staff` assertion, `EXPLAIN`-backed index tests.

---

### 4.2 Release V1.2 — Analytics and goals (Phases 25–35)

**Objective:** make learning measurable and visible, so a learner sees
consistency and progress, not just a log.

**Measurable outcome:** a dashboard shows study hours today/this week/this
month, a streak, per-topic completion percentages, and a consistency chart; a
daily goal fires a notification; a weekly report is generated and delivered.

**In scope:** A3.1–A3.7, A7.2, A7.3, A7.6, plus foundation A9.8.

**Data model additions**

| Model | Key fields | Notes |
| --- | --- | --- |
| `LearningEvent` | `user`, `kind`, `content_type`/`object_id`, `duration_s`, `occurred_at`, `metadata` JSONB | append-only event log; the analytics source of truth |
| `DailyAggregate` | `user`, `date`, `minutes`, `events`, `streak` | rolled up nightly |
| `Goal` | `user`, `metric`, `target`, `period` | daily/weekly goals |
| `Milestone` / `Streak` | `user`, `kind`, `value`, `achieved_at` | |
| `StudySession` | `user`, `started_at`, `ended_at`, `kind` (manual) | pomodoro writes it in V2.0 |
| `Report` | `user`, `period`, `payload` JSONB, `created_at` | weekly report |

**Config introduced:** `analytics.min_session_seconds`,
`analytics.day_boundary_timezone`, `analytics.streak_grace_hours`,
`analytics.milestones`, `goals.default_daily_minutes`,
`reports.weekly_send_day`, `notifications.quiet_hours` as `Setting` rows;
`dashboard`, `streaks`, `progress_charts`, `weekly_reports` flags; beat schedule
entries as `ScheduleConfig` rows (rollup, weekly report, reminder sweep).

**Release acceptance:** aggregates are recomputable from `LearningEvent` byte for
byte; the dashboard is owner-scoped; changing `goals.default_daily_minutes`
changes the default with no deploy; day boundaries respect
`analytics.day_boundary_timezone` (DST-safe).

**Release tests / evals:** gate — aggregation, timezone/DST, streak, report,
reminder, owner-scoping. Corpus evals (free) — aggregation rebuild-and-diff,
streak reference table, report golden file. No paid evals.

---

**Phase 25 — `LearningEvent` capture**
- Objective: every meaningful learning action is recorded as an append-only event.
- Deliverables: scaffold the `analytics` app (`INSTALLED_APPS`, empty initial migration, tests package); `LearningEvent` model (append-only) + insertion helper; capture points on entry open, entry create/edit, search, and (later) review. Also creates the `StudySession` model (its writer is the Pomodoro timer, Phase 77; its reader is analytics).
- Config (P0): `analytics.min_session_seconds` (below which an event is not a session).
- Acceptance: a real user action writes one event with the right kind/object/duration; no update/delete path exists; events are owner-scoped.
- Tests / evals: gate — capture on each action, append-only assertion.

**Phase 26 — Daily aggregates and rollup job**
- Objective: nightly rollup produces daily stats that reproduce exactly from events.
- Deliverables: `DailyAggregate` model; a `RollUpDailyAggregates` Celery task scheduled via `ScheduleConfig`.
- Config (P0): the rollup `ScheduleConfig` row; `analytics.day_boundary_timezone`.
- Acceptance: rebuilding aggregates from `LearningEvent` reproduces stored values byte for byte; the job is idempotent for a re-run day.
- Tests / evals: gate — rollup correctness, idempotency. Corpus eval — rebuild-and-diff.

**Phase 27 — Personal dashboard**
- Objective: a learner sees their hours and activity at a glance.
- Deliverables: dashboard view/template showing hours today/this week/this month and a recent-activity list, all owner-scoped; `dashboard` flag.
- Config (P0): `dashboard` flag.
- Acceptance: a second user sees only their own numbers; the page renders from aggregates, not live scans; flag off hides it.
- Tests / evals: gate — owner-scoping, aggregate-backed rendering.

**Phase 28 — Streaks and milestones**
- Objective: consistency is rewarded and visible.
- Deliverables: `Streak`/`Milestone` models + computation; `analytics.streak_grace_hours` and DST-safe day boundaries from `analytics.day_boundary_timezone`; `streaks` flag. Milestone triggers (e.g. `analytics.milestones` = `{"streak_days": [7, 30, 100], "total_minutes": [600, 3000]}`) are a `Setting`, so new milestones are added without a deploy.
- Config (P0): `analytics.streak_grace_hours`, `analytics.day_boundary_timezone`, `analytics.milestones`, `streaks` flag.
- Acceptance: streaks survive a DST change and a within-grace missed day; milestones fire once; a broken streak resets correctly.
- Tests / evals: gate — DST boundaries, grace window, reset logic. Corpus eval — streak reference table.

**Phase 29 — Topic completion percentages**
- Objective: each topic shows how far along it is, driven by its workflow.
- Deliverables: completion computed from the topic's `WorkflowDefinition` states and entry progress; surfaced on the topic page.
- Config (P0): none beyond Phase 9a/9b (reuses the workflow).
- Acceptance: moving a topic/entry through its workflow changes the percentage with no code change; percentages are owner-scoped.
- Tests / evals: gate — percentage across workflow states.

**Phase 30 — Progress visualization**
- Objective: aggregates render as readable charts.
- Deliverables: chart components over `DailyAggregate` (hours over time, completion); a small charting lib chosen per P4.
- Config (P0): `progress_charts` flag.
- Acceptance: charts match the underlying aggregates; they render on mobile widths; the flag hides them with no deploy.
- Tests / evals: gate — data-mapping tests; a visual check.

**Phase 31 — Goals**
- Objective: a learner sets daily/weekly targets that drive reminders.
- Deliverables: scaffold the `productivity` app (`INSTALLED_APPS`, empty initial migration, tests package); `Goal` model + CRUD + progress display; `goals.default_daily_minutes` supplies the default.
- Config (P0): `goals.default_daily_minutes`.
- Acceptance: a new user gets the default goal; progress reflects events; changing the default `Setting` changes new users' defaults with no deploy.
- Tests / evals: gate — default resolution, progress computation, owner-scoping.

**Phase 32 — `services/notifications` (email channel)**
- Objective: templated, contracted message delivery, reusable by later releases.
- Deliverables: `services/notifications` with its own contract under `contracts/notifications/v1/`, an email channel, and retry/DST-aware send timing; the web app resolves `NotificationTemplate` rows and passes an already-rendered payload (recipient, subject, body) across the contract, so the service never touches the Django ORM; tests + README.
- Config (P0): `NotificationTemplate` rows; provider credentials as env vars.
- Acceptance: a notification renders from a template and sends through the channel; an unknown template key fails softly.
- Tests / evals: gate — contract round-trip, template rendering, channel send with a mocked transport.

**Phase 33 — Study reminders**
- Objective: due reminders fire on the operator's cadence, respecting quiet hours.
- Deliverables: a `SweepReminders` beat task reading a `ScheduleConfig` row; per-user quiet hours; delivery via Phase 32.
- Config (P0): the reminder `ScheduleConfig` row; `notifications.quiet_hours` (per-scope, defaulting to a global window).
- Acceptance: a due reminder fires once; a quiet-hours-suppressed reminder does not; cadence changes apply with no deploy.
- Tests / evals: gate — due-fire, quiet-hours, cadence-from-DB.

**Phase 34 — Weekly reports**
- Objective: a learner receives a weekly summary of their progress.
- Deliverables: `Report` model (payload JSONB) + `GenerateReports` task scheduled by `reports.weekly_send_day` + delivery via Phase 32.
- Config (P0): `reports.weekly_send_day`, `weekly_reports` flag.
- Acceptance: a generated report matches the aggregates it summarizes; the send day is `Setting`-driven.
- Tests / evals: gate — generation correctness, schedule resolution. Corpus eval — report golden file.

**Phase 35 — Observability**
- Objective: the platform is operable: logs, request ids, health, metrics.
- Deliverables: structured logging with request ids (reusing Phase 12's middleware), health endpoints for web/worker/Redis/DB, an error-tracking hook, and a metrics endpoint.
- Config (P0): none (deployment concern).
- Acceptance: a request id threads through logs; health endpoints report each dependency; the metrics endpoint exposes the documented series.
- Tests / evals: gate — health-endpoint tests, request-id propagation, metrics presence.

---

### 4.3 Release V1.3 — The AI layer (Phases 36–48)

**Objective:** turn stored knowledge into help: summaries, explanations, tags,
recommendations, quizzes, gap analysis, and objectives. This is where
`services/llm` arrives, and it is the most scrutinized release because AI
quality is a product, not a checkbox.

**Measurable outcome:** a user can summarize an entry, ask the assistant to
explain a concept, get auto-tags and a category, receive a generated quiz that
scores against a rubric, and be shown likely knowledge gaps, each with a cached,
audited, cost-bounded model call.

**In scope:** A1.1–A1.7, A5.2, A5.3, A5.4.

**Data model additions**

| Model | Key fields | Notes |
| --- | --- | --- |
| `Summary` | `entry`, `text`, `prompt_version`, `model`, `created_at` | cached artifact |
| `Tag` / `ContentTag` | `name`, `slug`; through-model `ContentTag` links a tag to any topic/entry | auto + manual |
| `Recommendation` | `user`, `kind`, `payload` JSONB, `dismissed` | |
| `Quiz` / `Question` / `Choice` / `QuizAttempt` | quiz source, questions, answers, score | ties to assessment |
| `SelfAssessment` | `user`, `content_type`/`object_id`, `confidence` (1–5), `created_at` | A5.4; feeds gap analysis |
| `KnowledgeGap` | `user`, `topic`, `evidence` JSONB, `severity` | |
| `LearningObjective` | `topic`, `text`, `source` (manual/auto) | |
| `Embedding` | `content_type`, `object_id`, `vector` (pgvector), `model` | for A1.4, A1.6, related content |

**Config introduced:** `ai.daily_call_budget`, `ai.burst_per_min`, `ai.model`,
`ai.summary_max_words`, `ai.assistant_max_tokens`, `ai.quiz_default_count`,
`ai.recommendation_count`, `ai.gap_severity_threshold`, `ai.enabled_capabilities`
as `Setting` rows; `ai_summaries`, `ai_assistant`, `ai_tagging`,
`ai_recommendations`, `ai_quizzes`, `ai_gap_analysis`, `ai_objectives`,
`self_assessment` as flags (dark-launchable).

**Release acceptance:** no non-test module outside `services/llm` constructs a
model client (AST-enforced); identical input twice makes one model call; quota
exceeded returns a typed error; every response carries `prompt_version` and every
call is audited; a capability turned off by its flag disappears with no deploy.

**Release tests / evals:** gate — contract round-trips, caching, quota,
fail-soft, flag gating, the no-client-outside-service check. **Paid evals** are
the core of this release (thresholds in Section 8).

---

**Phase 36 — `services/llm` scaffold and contract**
- Objective: the AI gateway exists as a separate deployable with a versioned contract.
- Deliverables: `services/llm` package (config, health, README, tests); `contracts/llm/v1/` (shared envelope, error schema, one schema per capability) from Section 7.
- Config (P0): none yet.
- Acceptance: the contract round-trips against fixtures; the service reports health.
- Tests / evals: gate — contract round-trip with recorded fixtures.

**Phase 37 — Model adapter: Claude Code route, prompts, cache, quotas, audit**
- Objective: one choke point that enforces caching, cost, quotas, prompt versioning, and audit.
- Deliverables: an adapter shelling out to the **local Claude Code** (per P3; hosted API only if Brian authorizes it, Section 11); a prompt registry (`prompts/<capability>@<n>.md`) with `prompt_version` recorded on every response; Redis cache keyed by (capability, prompt_version, normalized input); quota enforcement from `ai.daily_call_budget` (scoped per user, falling back to the global row) plus a burst cap from `ai.burst_per_min`; an audit record per call; typed errors; fail-soft.
- Config (P0): `ai.daily_call_budget`, `ai.burst_per_min`, `ai.enabled_capabilities`.
- Acceptance: identical input twice makes one model call (cache hit proven); exceeding the budget returns a typed quota error, not an exception; every call writes an audit row with tokens/latency/cached.
- Tests / evals: gate — cache hit, quota enforcement, fail-soft on model unavailability, audit-on-call.

**Phase 38 — `embed` capability, pgvector, and the isolation guard**
- Objective: embeddings exist for later similarity features, and no one can bypass the gateway.
- Deliverables: `embed` capability + `Embedding` model with pgvector + similarity query helper; an AST-based test asserting no module outside `services/llm` imports a model client.
- Config (P0): `ai.enabled_capabilities` includes `embed`.
- Acceptance: embeddings round-trip and support a nearest-neighbour query; the AST test fails if a client import appears elsewhere.
- Tests / evals: gate — embedding round-trip, similarity query, no-client-outside-service AST test.

**Phase 39 — AI summaries**
- Objective: a user summarizes an entry with one click.
- Deliverables: `summarize` capability + `Summary` model + entry UI + `ai.summary_max_words`; `ai_summaries` flag.
- Config (P0): `ai.summary_max_words`, `ai_summaries` flag.
- Acceptance: summarizing is cached and audited; length respects the `Setting`; flag off hides the action.
- Tests / evals: gate — caching, length bound, flag gating. Paid eval — faithfulness/coverage ≥ 0.9.

**Phase 40 — AI assistant for explanations**
- Objective: a user asks the assistant to explain a difficult concept in context.
- Deliverables: `explain` capability + an entry/topic-scoped assistant UI; `ai_assistant` flag.
- Config (P0): `ai.model`, `ai.assistant_max_tokens`, `ai_assistant` flag.
- Acceptance: explanations cite the entry context; calls are cached and audited; the UI degrades to "try again" if the model is unavailable.
- Tests / evals: gate — context passing, fail-soft. Paid eval — correctness/reading level ≥ 0.85.

**Phase 41 — Auto-categorization and tagging**
- Objective: entries get a category and tags automatically, and a user can edit them.
- Deliverables: `categorize` capability + `Tag`/`ContentTag` models + UI to review/override; tagging runs as a Celery task triggered after save (never on the save path), so saving an entry never blocks on the model; `ai_tagging` flag.
- Config (P0): `ai_tagging` flag.
- Acceptance: tags are proposed, editable, and deduplicated by slug; owner-scoped.
- Tests / evals: gate — slug dedupe, owner-scoping. Paid eval — precision/recall F1 ≥ 0.8.

**Phase 42 — Personalized recommendations**
- Objective: a learner is shown what to study next, from their own material.
- Deliverables: `recommend` capability using profile + recent events + embeddings (Phase 38) + `Recommendation` model + UI + dismiss; `ai_recommendations` flag.
- Config (P0): `ai.recommendation_count`, `ai_recommendations` flag.
- Acceptance: recommendations draw on the user's own data only; dismissals persist.
- Tests / evals: gate — dismissal persistence, owner-scoping. Paid eval — recommendation relevance.

**Phase 43 — AI quizzes (multiple-choice and open-ended)**
- Objective: quizzes are generated from entries and scored, covering both A5.2 (multiple-choice) and A5.3 (open-ended) question kinds.
- Deliverables: scaffold the `assessment` app (`INSTALLED_APPS`, empty initial migration, tests package); `quiz` capability + the `assessment` app's `Quiz`/`Question`/`Choice`/`QuizAttempt` models, with `Question.kind` = `mc` | `open`; open-ended answers are graded by the same capability against a generated rubric, with the feedback stored on the attempt; a taking-and-scoring UI; `ai.quiz_default_count`; `ai_quizzes` flag.
- Config (P0): `ai.quiz_default_count`, `ai_quizzes` flag.
- Acceptance: a generated quiz has a valid answer key; both kinds are scored and stored (multiple-choice by exact key match, open-ended by stored rubric feedback); owner-scoped.
- Tests / evals: gate — answer-key validity, both-kind scoring, owner-scoping. Paid eval — answer-key correctness ≥ 0.95 and open-ended grade agreement with a labeled set ≥ 0.8.

**Phase 44 — Self-assessment tools**
- Objective: a learner records a confidence rating on a topic or entry (A5.4). This is a generic 1–5 self-rating, so it carries no dependency on objectives, which arrive in Phase 46.
- Deliverables: `SelfAssessment` model + a rating view capturing `confidence` (1–5) against a topic or entry.
- Config (P0): `self_assessment` flag.
- Acceptance: ratings persist and are owner-scoped; they feed Phase 45 gap analysis; once objectives exist (Phase 46) a rating may additionally target one, but that is additive and not required here.
- Tests / evals: gate — persistence, owner-scoping.

**Phase 45 — Knowledge gap identification**
- Objective: likely weak spots are surfaced from evidence.
- Deliverables: `gaps` capability + `KnowledgeGap` model + UI + `ai_gap_analysis` flag.
- Config (P0): `ai.gap_severity_threshold`, `ai_gap_analysis` flag.
- Acceptance: gaps cite their evidence (quiz misses, self-ratings); owner-scoped.
- Tests / evals: gate — evidence linkage, owner-scoping. Paid eval — agreement with a labeled gap set ≥ 0.7.

**Phase 46 — Automatic learning objectives**
- Objective: topics get suggested objectives, which also become an additional target for self-assessment.
- Deliverables: `objectives` capability + `LearningObjective` model (`source` manual/auto) + a UI to edit/accept plus a manual "add objective" path + the ability for a `SelfAssessment` (Phase 44) to target an objective.
- Config (P0): `ai_objectives` flag (dark-launchable).
- Acceptance: generated objectives are editable and marked `auto`; owner-scoped.
- Tests / evals: gate — source flagging, owner-scoping. Paid eval — coverage/actionability ≥ 0.85.

**Phase 47 — AI eval harness (paid lane)** *(process phase, not user-facing)*
- Objective: AI quality is measured automatically, nightly and before ship.
- Deliverables: a harness with golden sets per capability, thresholds from Section 8, a nightly runner, and a release gate.
- Config (P0): thresholds as `Setting` rows so they can be tuned without a deploy.
- Acceptance: a capability below threshold fails the gate; the harness reports per-capability scores.
- Tests / evals: the harness *is* the eval lane; a self-test with a deliberately regressed prompt turns it red.

**Phase 48 — AI flags, cost dashboard, and hardening**
- Objective: close V1.3 with dark-launch control and visible spend.
- Deliverables: wire all AI flags, a cost dashboard reading audit records, and confirmation that no AI feature is on a save path.
- Config (P0): the full AI flag set + `ai.enabled_capabilities`.
- Acceptance: every AI flag toggles its UI with no deploy; the cost dashboard matches audit totals; killing a flag never breaks entry saving.
- Tests / evals: gate — flag toggling, save-path independence.

---

### 4.4 Release V1.4 — Learning paths and retention (Phases 49–59)

**Objective:** move from a flat topic list to structured roadmaps, and from
reading to remembering, via spaced repetition.

**Measurable outcome:** a user builds a roadmap of modules and lessons with
prerequisites, sees pending vs. complete, gets a study schedule, reviews
flashcards on an SRS schedule, and receives revision reminders.

**In scope:** A4.1–A4.6, A5.1, A5.5, A5.6.

**Data model additions**

| Model | Key fields | Notes |
| --- | --- | --- |
| `Roadmap` | `owner`, `title`, `workflow_state`, `deadline`, `visibility` | |
| `Module` | `roadmap`, `title`, `order` | |
| `Lesson` | `module`, `title`, `order`, `entry` FK nullable, `workflow_state` | completion via workflow |
| `Prerequisite` | `from_lesson`, `to_lesson` (or topic/topic), `hard` bool | cycle-checked on write |
| `StudySchedule` | `user`, `roadmap`, `cadence` JSONB | generated from `Setting` templates |
| `Deck` / `Card` | deck; card: front, back, `ease`, `interval_days`, `due_at`, `reps` | SM-2 parameters stored per card |
| `ReviewLog` | `card`, `grade`, `reviewed_at`, `interval_before/after` | retention data |
| `RetentionMetric` | `user`, `topic`, `retention`, `computed_at` | derived from ReviewLog |

**Config introduced:** `srs.intervals`, `srs.starting_ease`,
`srs.graduating_interval_days`, `srs.max_interval_days`, `srs.lapse_penalty`,
`srs.daily_new_cards`, `srs.daily_review_cap`, `paths.max_depth`,
`paths.default_schedule` as `Setting` rows; `flashcards`,
`roadmaps`, `study_schedules` flags; study-schedule and revision-reminder beat
entries as `ScheduleConfig` rows.

**Release acceptance:** the SRS scheduler is a pure function proven against a
reference table; changing `srs.intervals` changes scheduling with no deploy;
prerequisite cycles are rejected at write time; lesson completion follows its
`WorkflowDefinition`; retention is recomputable from `ReviewLog`.

**Release tests / evals:** gate — exhaustive SRS table, cycle detection,
schedule generation, DST-safe reminders, retention derivation. Corpus eval
(free) — the SRS one-year reference simulation is this release's headline.

---

**Phase 49 — Roadmaps**
- Objective: a user creates a structured roadmap.
- Deliverables: scaffold the `paths` app (`INSTALLED_APPS`, empty initial migration, tests package); `Roadmap` model + workflow tie-in (Phase 9b) + CRUD views; `roadmaps` flag.
- Config (P0): the `roadmap` `WorkflowDefinition` row; `roadmaps` flag; `paths.max_depth`.
- Acceptance: a roadmap is owner-scoped; its completion follows its workflow; depth respects `paths.max_depth`.
- Tests / evals: gate — CRUD, owner-scoping, workflow-driven completion.

**Phase 50 — Modules and lessons**
- Objective: roadmaps break into ordered modules and lessons.
- Deliverables: `Module` + `Lesson` models + UI; lesson completion via the `lesson` workflow; optional `entry` link per lesson.
- Config (P0): the `lesson` `WorkflowDefinition` row.
- Acceptance: lesson order is preserved; completion state follows workflow transitions, not an `if` chain.
- Tests / evals: gate — ordering, workflow-driven completion.

**Phase 51 — Objectives and deadlines**
- Objective: roadmaps and lessons carry objectives and due dates, and overdue items surface.
- Deliverables: objective/deadline fields + overdue surfacing in the UI and dashboard.
- Config (P0): none beyond existing (deadline is per-object data).
- Acceptance: an overdue lesson is flagged; deadlines are owner-scoped.
- Tests / evals: gate — overdue detection, owner-scoping.

**Phase 52 — Prerequisites**
- Objective: lessons/topics can require others, without cycles.
- Deliverables: `Prerequisite` model + a cycle check on write + a "blocked" indicator in the UI.
- Config (P0): `hard` vs. soft prerequisite is data on the row.
- Acceptance: a cyclic prerequisite set is rejected at write time; a blocked lesson is clearly marked.
- Tests / evals: gate — cycle detection (incl. long cycles), blocking logic.

**Phase 53 — Study schedules**
- Objective: a learner gets a generated schedule for a roadmap.
- Deliverables: `StudySchedule` model + a `GenerateStudySchedule` task from `paths.default_schedule` templates + UI; `study_schedules` flag.
- Config (P0): `paths.default_schedule`, `study_schedules` flag, the schedule `ScheduleConfig` row.
- Acceptance: a generated schedule is deterministic for the same inputs; changing the default template changes new schedules with no deploy.
- Tests / evals: gate — deterministic generation, template-driven output.

**Phase 54 — Decks and cards**
- Objective: flashcards exist as decks of cards.
- Deliverables: `Deck`/`Card` models with SM-2 state fields (`ease`, `interval_days`, `due_at`, `reps`) + CRUD; `flashcards` flag.
- Config (P0): `flashcards` flag; `srs.daily_new_cards`, `srs.daily_review_cap`.
- Acceptance: cards are owner-scoped; SM-2 fields persist across edits.
- Tests / evals: gate — CRUD, owner-scoping, field persistence.

**Phase 55 — SRScheduler pure function**
- Objective: scheduling is a deterministic function, fully unit-tested.
- Deliverables: `SRScheduler` (`grade + card state + settings → next state`), reading `srs.intervals`, `srs.starting_ease`, `srs.graduating_interval_days`, `srs.max_interval_days`, `srs.lapse_penalty`.
- Config (P0): the `srs.*` settings.
- Acceptance: the function is pure and reproducible; changing `srs.intervals` changes scheduling with no deploy.
- Tests / evals: gate — an exhaustive state-transition table.

**Phase 56 — SRS one-year reference simulation (headline eval)** *(eval phase, not user-facing)*
- Objective: prove scheduling behavior over a year against a frozen expected schedule.
- Deliverables: a scripted grade sequence over a simulated year compared to a frozen expected schedule.
- Config (P0): none (reuses `srs.*`).
- Acceptance: the simulation matches the frozen schedule; a changed `srs.intervals` changes the outcome in the expected way.
- Tests / evals: corpus eval — the one-year simulation.

**Phase 57 — Flashcard review UI and review log**
- Objective: a learner reviews due cards and every review is logged.
- Deliverables: a review UI + `ReviewLog` model + a `SweepDueCards` task that queues due cards.
- Config (P0): the due-cards `ScheduleConfig` row.
- Acceptance: only due cards are shown; each grade writes a `ReviewLog` with before/after intervals.
- Tests / evals: gate — due selection, log correctness.

**Phase 58 — Retention tracking**
- Objective: retention is derived from review history and shown over time.
- Deliverables: `RetentionMetric` model + derivation from `ReviewLog` + a visualization.
- Config (P0): none.
- Acceptance: retention is recomputable from `ReviewLog`; the metric is owner-scoped.
- Tests / evals: gate — derivation correctness, recomputability, owner-scoping.

**Phase 59 — Revision reminders**
- Objective: due reviews generate reminders on a schedule.
- Deliverables: a revision-reminder beat entry (`ScheduleConfig`) delivered via Phase 32, DST-safe.
- Config (P0): the reminder `ScheduleConfig` row.
- Acceptance: a due review fires a reminder once, DST-safe; cadence is data-driven.
- Tests / evals: gate — due-fire, DST boundaries, cadence-from-DB.

---

### 4.5 Release V2.0 — Community and platform (Phases 60–78)

**Objective:** make knowledge shareable, installable, and operable at scale.

**Measurable outcome:** users join public or private spaces, share selected
topics, comment, follow each other, and share roadmaps; the app installs as a PWA
with offline access; a documented REST API exists; OAuth and MFA work; data
exports to PDF/Markdown/JSON; backups and monitoring run.

**In scope:** Area 6 (A6.1–A6.7), Area 8 (A8.1–A8.8), plus A7.1, A7.4, A7.5,
A9.2, A9.4.

**Data model additions**

| Model | Key fields | Notes |
| --- | --- | --- |
| `Space` | `owner`, `name`, `visibility` (public/private/group) | |
| `SpaceMembership` | `space`, `user`, `role` FK | RBAC scoped to the space |
| `Share` | `content_type`/`object_id`, `space` or `user`, `can_comment`, `can_copy` | |
| `Comment` | `content_type`/`object_id`, `author`, `body_markdown`, `parent` | threaded |
| `Follow` | `follower`, `followee`, `created_at` | |
| `Task` | `user`, `title`, `due_at`, `workflow_state`, `source` | |
| `CalendarLink` | `user`, `provider`, `external_id`, `secret` | iCal/Google |
| `Export` | `user`, `format`, `status`, `file` | |
| `OfflineChange` | `user`, `device`, `payload`, `applied_at` | sync ledger |

**Config introduced:** `spaces.allow_public`, `community.max_comment_depth`,
`api.rate_limit_per_min`, `exports.formats`, `pwa.cache_version`,
`themes.allow_user_choice`, `pomodoro.default_minutes`,
`pomodoro.break_minutes` as settings; `community`, `public_spaces`, `comments`,
`rest_api`, `pwa`, `offline_mode`, `oauth`, `mfa`, `exports`, `pomodoro`,
`tasks`, `follows` as flags.

**Release acceptance:** a private space's content is invisible to non-members
(both directions); offline edits sync without loss (conflict rule documented and
tested); JSON export re-imports to an equivalent state; the API is contract-tested
against the OpenAPI schema; rate limits trigger a 429 and the cap is
`Setting`-driven.

**Release tests / evals:** gate — space isolation, comment threading, follow
graph, API schema conformance, export/import round-trip, rate-limit behavior,
offline conflict resolution. Corpus evals (free) — export round-trip, offline
scenarios, API schema conformance.

---

**Phase 60 — Spaces and space-scoped RBAC**
- Objective: content lives in public, private, or group spaces, isolated by role.
- Deliverables: scaffold the `community` app (`INSTALLED_APPS`, empty initial migration, tests package); `Space` + `SpaceMembership` models + space-scoped `has()` integration (Phase 10) + CRUD + isolation enforcement; `community` flag, `spaces.allow_public`.
- Config (P0): `spaces.allow_public`, `community` flag.
- Acceptance: a private space's content is invisible to a non-member in both directions; public spaces are gated by `spaces.allow_public`.
- Tests / evals: gate — two-direction isolation, role checks, public gating.

**Phase 61 — Sharing topics and entries**
- Objective: a user shares selected topics/entries into a space or with a user.
- Deliverables: `Share` model (generic target, `can_comment`, `can_copy`) + share UI + permission enforcement.
- Config (P0): `public_spaces` flag for the public path.
- Acceptance: a share grants exactly the declared rights; revoking removes access; a shared private entry is not exposed beyond the grant.
- Tests / evals: gate — grant/revoke, rights enforcement, no over-exposure.

**Phase 62 — Collaborative groups**
- Objective: groups of learners share a space with roles.
- Deliverables: group membership + role management on top of `SpaceMembership`.
- Config (P0): group role rows.
- Acceptance: a member's role governs what they can do in the group space; leaving removes access.
- Tests / evals: gate — role permissions, join/leave.

**Phase 63 — Comments and discussions**
- Objective: threaded discussion on shared content.
- Deliverables: `Comment` model (threaded via self-FK) + UI + `community.max_comment_depth`; `comments` flag.
- Config (P0): `community.max_comment_depth`, `comments` flag.
- Acceptance: replies nest to the configured depth and no further; only users with comment rights can post.
- Tests / evals: gate — depth limit, permission enforcement, threading.

**Phase 64 — Peer sharing and follows**
- Objective: learners follow each other and see shared activity.
- Deliverables: `Follow` model + a feed of followed users' shared content + follow/unfollow UI.
- Config (P0): `follows` flag.
- Acceptance: a follow surfaces the followee's shared items only; unfollow stops it.
- Tests / evals: gate — feed scoping, follow/unfollow.

**Phase 65 — Shared roadmaps**
- Objective: a roadmap can be shared into a space and copied.
- Deliverables: share a `Roadmap` (Phase 61 mechanism) + a copy-into-my-space action respecting `can_copy`.
- Config (P0): `can_copy` on the share row.
- Acceptance: a copied roadmap is independent of the original; copying is refused when `can_copy` is false.
- Tests / evals: gate — independent copy, `can_copy` enforcement.

**Phase 66 — REST API and OpenAPI schema**
- Objective: a documented, RBAC-honoring API.
- Deliverables: DRF + an OpenAPI schema at `/api/schema/`; endpoints reusing the same `has()` checks; `rest_api` flag; contract tests.
- Config (P0): `rest_api` flag.
- Acceptance: the API matches the OpenAPI schema (conformance test); every endpoint enforces the same RBAC as the web UI.
- Tests / evals: gate — schema conformance, RBAC parity. Corpus eval — API schema conformance.

**Phase 67 — OAuth authentication**
- Objective: users sign in with an external provider.
- Deliverables: OAuth flow in `accounts` (maintained library, P4) + account linking.
- Config (P0): `oauth` flag; provider client secrets as `is_secret` `Setting` rows (tenant-level) or env vars (deployment-level) per Section 1.4.
- Acceptance: an OAuth login creates/links an account; state/PKCE is validated.
- Tests / evals: gate — flow validation, account linking, error paths.

**Phase 68 — Multi-factor authentication**
- Objective: a user can require a second factor; recovery is possible.
- Deliverables: TOTP (maintained library) + recovery codes + a per-user require flag + the login step.
- Config (P0): `mfa` flag; per-user require setting.
- Acceptance: a user with MFA must present a valid TOTP; a recovery code works once; disabling MFA requires re-auth.
- Tests / evals: gate — TOTP verification, recovery single-use, require-flag enforcement.

**Phase 69 — Rate limiting and abuse protection**
- Objective: abusive traffic is throttled with operator-set caps.
- Deliverables: Redis-counter middleware + login throttling + `api.rate_limit_per_min`, reusing the AI quota mechanism.
- Config (P0): `api.rate_limit_per_min`.
- Acceptance: exceeding the cap returns 429; raising the `Setting` raises the cap with no deploy; login throttling slows brute force.
- Tests / evals: gate — 429 behavior, `Setting`-driven cap, login throttle.

**Phase 70 — Progressive Web App**
- Objective: the app installs and works offline as a shell.
- Deliverables: web app manifest + service worker + offline shell; `pwa.cache_version`; `pwa` flag.
- Config (P0): `pwa.cache_version`, `pwa` flag.
- Acceptance: the app is installable; the shell loads offline; bumping `pwa.cache_version` invalidates caches.
- Tests / evals: gate — manifest validity, cache-version bump behavior.

**Phase 71 — Offline access and synchronization**
- Objective: offline edits sync without loss.
- Deliverables: `OfflineChange` ledger + a sync endpoint + a documented conflict rule; `offline_mode` flag.
- Config (P0): `offline_mode` flag.
- Acceptance: queued offline edits apply on reconnect; a conflict resolves by the documented rule; no edit is lost.
- Tests / evals: gate — sync application, conflict resolution. Corpus eval — offline conflict scenarios.

**Phase 72 — Dark and light themes**
- Objective: a user chooses a theme.
- Deliverables: theme tokens + a toggle + persistence; `themes.allow_user_choice`.
- Config (P0): `themes.allow_user_choice`.
- Acceptance: the theme persists across sessions; disabling user choice forces the default.
- Tests / evals: gate — persistence, forced-default; a visual check across breakpoints.

**Phase 73 — Data export (PDF, Markdown, JSON)**
- Objective: a user exports their material.
- Deliverables: export services for PDF/Markdown/JSON + `Export` model + a download UI; `exports` flag, `exports.formats`.
- Config (P0): `exports` flag, `exports.formats`.
- Acceptance: a JSON export re-imports to an equivalent state; only selected formats are offered per `exports.formats`.
- Tests / evals: gate — export correctness. Corpus eval — export round-trip (PDF/Markdown/JSON).

**Phase 74 — Automated backups and recovery**
- Objective: backups run on a schedule and restore is proven.
- Deliverables: a scheduled `pg_dump` + media snapshot to object storage, driven by `ScheduleConfig`, plus a restore management command and a restore test.
- Config (P0): the backup `ScheduleConfig` row.
- Acceptance: a backup file is produced on schedule; the restore path reproduces the data in a scratch database (a backup nobody has restored is not a backup).
- Tests / evals: gate — backup production, restore to a scratch DB.

**Phase 75 — Calendar integration**
- Objective: deadlines and study sessions appear in a calendar.
- Deliverables: `CalendarLink` model + iCal feed (and/or Google push) + settings.
- Config (P0): provider config; `CalendarLink.secret` as an `is_secret` `Setting` where tenant-supplied.
- Acceptance: an iCal feed contains the user's deadlines; a linked calendar reflects updates.
- Tests / evals: gate — feed contents, link lifecycle, secret handling.

**Phase 76 — Tasks and assignments**
- Objective: a learner manages tasks alongside learning.
- Deliverables: `Task` model + workflow tie-in + CRUD + dashboard surface; `tasks` flag.
- Config (P0): the `task` `WorkflowDefinition` row; `tasks` flag.
- Acceptance: task state follows its workflow; tasks are owner-scoped.
- Tests / evals: gate — workflow-driven state, owner-scoping.

**Phase 77 — Pomodoro study timer**
- Objective: a timed study session feeds analytics.
- Deliverables: a timer UI that writes a `StudySession` (Phase 25's model) and emits `LearningEvent`s; `pomodoro` flag.
- Config (P0): `pomodoro` flag; `pomodoro.default_minutes`, `pomodoro.break_minutes`.
- Acceptance: a completed session appears in analytics; abandoned sessions are handled per a documented rule.
- Tests / evals: gate — session recording, analytics integration.

**Phase 78 — Final hardening and scalable deployment**
- Objective: close the whole plan: stateless, observable, load-tested, and DoD-complete.
- Deliverables: stateless web + separate worker/beat, managed Postgres/Redis, object storage, monitoring/alerting, a load smoke test, and a full DoD sweep across all five releases.
- Config (P0): the complete `Setting`/flag/workflow catalogue documented and seeded.
- Acceptance: the app scales horizontally (two web dynos, one worker); monitoring alerts on error-rate and latency; every release's DoD (Section 10) is re-checked and recorded.
- Tests / evals: gate — full suite green on the production-shaped stack. Evals — the full nightly set runs and passes at threshold.

---

## 5. Coverage matrix (all 65 requested features)

Every feature the request named, mapped to a release and the phase that delivers
it. Nothing is dropped.

**Area 1: Intelligent learning management** → V1.3
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A1.1 | AI-generated summaries of entries | V1.3 | 39 |
| A1.2 | AI assistant for explaining concepts | V1.3 | 40 |
| A1.3 | Automatic topic categorization and tagging | V1.3 | 41 |
| A1.4 | Personalized learning recommendations | V1.3 | 42 |
| A1.5 | AI-generated quizzes from entries | V1.3 | 43 |
| A1.6 | Knowledge gap identification | V1.3 | 45 |
| A1.7 | Automatic learning objectives | V1.3 | 46 |

**Area 2: Advanced knowledge management** → V1.1
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A2.1 | Rich-text editor with Markdown | V1.1 | 13, 15 |
| A2.2 | Code syntax highlighting | V1.1 | 15 |
| A2.3 | Image, PDF, document attachments | V1.1 | 16, 17 |
| A2.4 | Internal linking between topics and entries | V1.1 | 21 |
| A2.5 | Full-text search | V1.1 | 19, 20 |
| A2.6 | Bookmarks and favorites | V1.1 | 23 |
| A2.7 | Learning collections and folders | V1.1 | 22 |
| A2.8 | Version history for edited entries | V1.1 | 18 |

**Area 3: Learning analytics and progress** → V1.2
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A3.1 | Personal learning dashboard | V1.2 | 27 |
| A3.2 | Learning hours and activity tracking | V1.2 | 25, 26 |
| A3.3 | Daily, weekly, monthly statistics | V1.2 | 26 |
| A3.4 | Learning streaks and milestones | V1.2 | 28 |
| A3.5 | Topic completion percentages | V1.2 | 29 |
| A3.6 | Progress visualization | V1.2 | 30 |
| A3.7 | Learning consistency reports | V1.2 | 34 |

**Area 4: Structured learning paths** → V1.4
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A4.1 | Structured learning roadmaps | V1.4 | 49 |
| A4.2 | Topics into modules and lessons | V1.4 | 50 |
| A4.3 | Objectives and deadlines | V1.4 | 51 |
| A4.4 | Completed and pending lessons | V1.4 | 50 |
| A4.5 | Prerequisite relationships | V1.4 | 52 |
| A4.6 | Personalized study schedules | V1.4 | 53 |

**Area 5: Assessment and retention** → V1.3 (quizzes), V1.4 (SRS)
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A5.1 | Flashcards with spaced repetition | V1.4 | 54–57 |
| A5.2 | Automated quizzes and assessments | V1.3 | 43 (shares the phase with A1.5: A1.5 is generation, A5.2 is the take-and-score flow) |
| A5.3 | Multiple-choice and open-ended questions | V1.3 | 43 |
| A5.4 | Self-assessment tools | V1.3 | 44 |
| A5.5 | Knowledge retention tracking | V1.4 | 58 |
| A5.6 | Revision reminders | V1.4 | 59 |

**Area 6: Collaboration and community** → V2.0
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A6.1 | Public and private learning spaces | V2.0 | 60 |
| A6.2 | Share selected topics and entries | V2.0 | 61 |
| A6.3 | Collaborative learning groups | V2.0 | 62 |
| A6.4 | Comments and discussions | V2.0 | 63 |
| A6.5 | Peer knowledge sharing | V2.0 | 64 |
| A6.6 | Follow other learners | V2.0 | 64 |
| A6.7 | Shared learning roadmaps | V2.0 | 65 |

**Area 7: Productivity and engagement** → V1.2 (goals/reminders/reports), V2.0 (calendar/tasks/timer)
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A7.1 | Calendar integration | V2.0 | 75 |
| A7.2 | Study reminders and notifications | V1.2 | 33 |
| A7.3 | Daily learning goals | V1.2 | 31 |
| A7.4 | Task and assignment management | V2.0 | 76 |
| A7.5 | Pomodoro study timer | V2.0 | 77 |
| A7.6 | Weekly learning reports | V1.2 | 34 |

**Area 8: Modern platform capabilities** → V2.0
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A8.1 | Progressive Web App (PWA) | V2.0 | 70 |
| A8.2 | Responsive mobile-first interface | V1.1 onward (cross-cutting) | 15 onward |
| A8.3 | Dark and light themes | V2.0 | 72 |
| A8.4 | REST API | V2.0 | 66 |
| A8.5 | OAuth authentication | V2.0 | 67 |
| A8.6 | Export to PDF, Markdown, JSON | V2.0 | 73 |
| A8.7 | Automated backups and recovery | V2.0 | 74 |
| A8.8 | Offline access and synchronization | V2.0 | 71 |

**Area 9: Security and infrastructure** → spread across releases
| # | Feature | Release | Phase |
| --- | --- | --- | --- |
| A9.1 | Role-based access control | V1.1 | 10, 24 |
| A9.2 | Multi-factor authentication | V2.0 | 68 |
| A9.3 | Audit logs | V1.1 | 12 |
| A9.4 | Rate limiting and abuse protection | V2.0 | 69 |
| A9.5 | Background task processing | V1.1 | 3 |
| A9.6 | Redis caching | V1.1 | 2 |
| A9.7 | Database optimization | V1.1 onward | 24, 78 |
| A9.8 | Centralized logging and monitoring | V1.2 | 35 |
| A9.9 | Automated CI/CD pipelines | V1.1 | 5 |
| A9.10 | Scalable deployment architecture | V1.1 onward | 1–5, 78 |

---

## 6. Data model appendix (placement rules)

For each new model, record **config vs. schema**: which of its fields are
`Setting`/flag/workflow data (P0) and which are fixed schema. The rule:

- If a field's value an operator would edit, it is a `Setting` (or is guarded by
  a `FeatureFlag`), not a `models.IntegerField` with a literal default.
- If a field defines a state machine, it is a `WorkflowDefinition`, not a
  `choices=` list.
- If a field grants authority, it is a `RoleAssignment`, not an `is_staff` check.

Model families to add, grouped by release, are listed per release in Section 4.
Common conventions:
- Every user-authored model carries `created_at`, `updated_at`, and an `owner`
  (or inherits ownership from its parent), and every query is owner-scoped.
- Every model that an operator configures is registered in the admin with
  validation, and its writes are audited.
- Generic relations (bookmarks, collections, comments, shares, exports) use
  `contenttypes` so one mechanism serves topics, entries, and later objects.

---

## 7. LLM service contract (appendix)

Location: `contracts/llm/v1/`. One JSON Schema per capability plus a shared
error schema.

Shared response envelope:

```jsonc
{ "ok": true,
  "result": { /* capability-specific */ },
  "model": "string",
  "prompt_version": "capability@n",
  "usage": {"input_tokens": 0, "output_tokens": 0, "cost_estimate": 0.0},
  "cached": false,
  "request_id": "uuid" }
```

Shared error envelope (always a 2xx-shaped typed error, never a raw traceback):

```jsonc
{ "ok": false,
  "error": {"code": "quota_exceeded | invalid_input | model_unavailable",
            "message": "string", "retry_after_s": 0},
  "request_id": "uuid" }
```

Capabilities and their request/result fields:

| Capability | Request | Result | Phase |
| --- | --- | --- | --- |
| `summarize` | `{text, max_words, locale}` | `{summary, key_points[]}` | 39 |
| `explain` | `{concept, context, level}` | `{explanation, examples[]}` | 40 |
| `categorize` | `{text, taxonomy[]?}` | `{category, tags[]}` | 41 |
| `recommend` | `{profile, recent[], goal?}` | `{recommendations[]}` | 42 |
| `quiz` | `{source, count, types[], difficulty}` | `{questions[]}` | 43 |
| `gaps` | `{corpus[], goal?}` | `{gaps[]}` | 45 |
| `objectives` | `{topic_text}` | `{objectives[]}` | 46 |
| `embed` | `{texts[]}` | `{vectors[][], dim}` | 38 |

Rules baked into the contract: idempotent by input hash (cache), every result
carries `prompt_version`, errors are typed, and no capability blocks a save.

---

## 8. Test and eval strategy

Two lanes, different budgets (P2):

**Gate tests** (deterministic, local, free, under two seconds, every commit):
models, views, RBAC, ownership, config resolution, the SRS table, search,
export/import, contract round-trips with fixtures, the AST-based "no model client
outside `services/llm`" check. Run in CI on every push. The current suite (144
tests) grows into many app-scoped suites; each app keeps its own `tests/`
package.

**Periodic evals** (nightly + before ship) come in the two kinds defined by P2:
- **Model evals (paid, thresholded)** for AI features:

  | Capability | Eval | Threshold |
  | --- | --- | --- |
  | summarize | faithfulness (no invented facts), coverage, length bound | pass rate ≥ 0.9 |
  | explain | correctness vs. a gold answer, reading level match | ≥ 0.85 |
  | categorize | precision/recall vs. a labeled set | F1 ≥ 0.8 |
  | quiz | answer-key correctness, distractor quality | correct ≥ 0.95 |
  | recommend | relevance vs. a labeled set | ≥ 0.8 |
  | gaps | agreement with a human-labeled gap set | ≥ 0.7 |
  | objectives | coverage of the topic, actionability | ≥ 0.85 |

- **Corpus evals (free, deterministic)** for everything else, run as scheduled
  jobs against a golden corpus: search relevance, Markdown golden set, and
  version-restore round-trip (V1.1, Phases 13/18/20); aggregation rebuild-and-diff
  and streak reference table (V1.2, Phases 26/28); the SRS one-year simulation
  (V1.4, Phase 56); export round-trip and offline scenarios (V2.0, Phases 71/73).
  Each release's section names its own.

- Each eval writes a score; a drop below threshold blocks the release.

Per phase, the report states which lane ran and why, exactly as the replica's
protocol did.

---

## 9. Deployment and operations (Scalingo)

The replica already ships Scalingo readiness (`Procfile`, `bin/post_deploy.sh`,
`.python-version`, the `STACK`-gated settings). The evolution extends it:

- **Addons:** PostgreSQL (with `pgvector`), Redis, object storage (S3-compatible).
- **Procfile processes:** `web` (gunicorn), `worker` (Celery), `beat` (Celery
  beat), and the existing `postdeploy` (migrate + `collectstatic`).
- **Env vars:** the replica's `DJANGO_*` set, plus `DATABASE_URL` (auto),
  `REDIS_URL`, `S3_*`, `SETTINGS_ENCRYPTION_KEY`, and, for the AI service,
  whatever the local Claude Code route needs (Section 11).
- **Migrations:** unchanged rule. Generate locally, commit, apply in
  `post_deploy.sh`. Never `makemigrations` on the server.
- **Backups (V2.0, Phase 74):** scheduled `pg_dump` + media snapshot to object
  storage, with a **tested restore**.
- **Monitoring (V1.2, Phase 35):** health endpoints, structured logs with request
  ids, error tracking, and a metrics endpoint.

Cross-cutting infrastructure mapping (area 9): A9.1 RBAC → Phase 10/24; A9.3
audit → Phase 12; A9.5 Celery → Phase 3; A9.6 Redis → Phase 2; A9.7 DB
optimization → Phases 24/78; A9.9 CI/CD → Phase 5; A9.10 scalable deploy →
Phases 1–5/78; A9.2 MFA → Phase 68; A9.4 rate limiting → Phase 69; A9.8
observability → Phase 35.

Standards that hold across all releases:
- All domain authorization goes through `core` RBAC; no `is_staff`/`is_superuser`
  in domain code.
- All cross-boundary calls use a `contracts/` schema.
- All config writes are audited. Infrastructure secrets stay in env vars; only
  tenant-level operational secrets are `is_secret` settings (encrypted at rest,
  never logged, never serialized to a client).
- Owner-scoping (the replica's Phase 4/5 rule) is never regressed: RBAC is added
  on top of ownership, never instead of it.
- Every service has a health endpoint and its own test + eval suite.
- Responsive/mobile-first (A8.2) is a posture held from V1.1 onward (the
  replica's Bootstrap 5 layout), not a V2.0 feature; each release keeps it.

---

## 10. Definition of done

A phase is done when (per Section 2.2): it passed triage, shipped its migration,
gate tests, and eval in one commit, passed a cold critic where required, earned a
proud self-rating, and merged with a restart note.

A release is done when:

- Every phase in its scope is merged, each built as an independent unit that
  passed a cold critic.
- Gate tests and the release's evals are in the diff, green, and CI-enforced.
- New behavior is configurable per P0 (or the review records why it is fixed
  schema).
- RBAC and owner-scoping hold; no authorization regressions.
- The measurable outcome for the release is demonstrated (a metric, a screenshot,
  or a test that fails without the feature).
- Every page added in the release is verified usable at mobile, tablet, and
  desktop widths (A8.2, re-checked each release, not only at V1.1).
- No secret is committed; migrations apply to a fresh database; the README and
  the project's reference inventory (`reference-inventory.md`) record what
  changed.
- The PR is merged to `main`, and the report names what to restart.

The plan is done when all five releases are complete and Phase 78's DoD sweep
passes.

---

## 11. Open decisions (Confusion Protocol)

These are high-stakes forks that need a decision before the affected phase
starts. They are named, with options and a recommendation, rather than guessed.

1. **How the AI service reaches a model in production (the big one).**
   The workspace rule (P3) is "local Claude Code, not a hosted API." A cloud
   deploy (Scalingo) cannot run the local Claude Code the way a workstation does.
   Options:
   (a) run `services/llm` on a host that has Claude Code and is reachable by the
   web app; (b) Brian explicitly authorizes a hosted API for this one service,
   keeping all other rules; (c) keep AI features local-only for now and gate them
   by flag in production.
   *Recommendation:* decide this at the start of V1.3 (before Phase 36). It blocks
   the AI release and nothing else. Options (a) or (b); do not silently pick a
   hosted API.

2. **Markdown and rich-text library (Phase 13).** Server-rendered Markdown
   (`markdown` + `nh3`/`bleach`) versus a JS editor (TipTap/ProseMirror/Toast UI).
   *Recommendation:* server-rendered Markdown first (P4, simplest, testable,
   matches the no-JS-framework posture); add a JS editor only if the UX demands
   it.

3. **Search engine (Phase 19).** Postgres FTS versus Meilisearch/OpenSearch.
   *Recommendation:* Postgres FTS. Revisit only on measured latency.

4. **Object storage provider (Phase 4).** Which S3-compatible store (Scalingo's,
   AWS S3, Backblaze B2, Cloudflare R2).
   *Recommendation:* whatever integrates with the Scalingo region; abstract behind
   `django-storages`.

5. **Charting library (Phase 30).** Server-rendered SVG versus a small JS library.
   *Recommendation:* the smallest maintained lib that renders the required charts;
   avoid a heavy framework.

6. **Community safety model (Phase 60).** Open registration for public spaces
   raises moderation and abuse questions.
   *Recommendation:* private/group spaces first, public spaces behind
   `public_spaces` and a moderation design.

---

## 12. Non-goals

- No mobile native apps. The PWA (A8.1, Phase 70) is the mobile story.
- No microservices explosion. `web` stays a Django monolith with clean app
  boundaries; only `services/llm` and `services/notifications` are separate
  deployables, because they have genuinely different runtime needs.
- No real-time collaboration (multiplayer editing). Async comments and sharing
  only.
- No marketplace, no payments, no course hosting for third parties.
- No re-engineering of the replica's security posture for its own sake; the
  ownership and CSRF/XSS guarantees carry forward unchanged.

---

## 13. Immediate next phase

Start **Phase 1 (Postgres foundation and env split)**, then proceed down the list
in Section 4. Phases 1–5 are the platform foundation and can partly parallelize
(2 and 5 do not block on each other); Phases 6–12 build the `core` config engine
that every later phase depends on; Phases 13–24 deliver the V1.1 knowledge
features.

When Brian says go, this plan, like `plan.md` before it, is executed phase by
phase with the same discipline: triage block, tests and evals in the diff, a cold
critic pass, a self-rating, and a merge to `main` with a restart note. Phase 78's
DoD sweep closes the whole evolution.
