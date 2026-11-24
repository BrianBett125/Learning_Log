# Reference Inventory — Learning Log (Python Crash Course 3e, Ch. 18–20)

Phase 0 deliverable. Every claim below was read from the pinned source, not inferred.

## Provenance

- Official source: `github.com/ehmatthes/pcc_3e`, commit `3690082cad0aad58cedb4face741aa025d6e8d73` (2026-03-24), subject "Update references to Upsun.", shallow-cloned to `/tmp/pcc_3e`.
- Reference of record: `chapter_20/deploying_learning_log` (the complete, styled, deployment-prepared final state). `chapter_20/styling_learning_log` is the same app before deployment files were added; both were inspected.
- Author pages read: `ehmatthes.github.io/pcc_3e/new_in_3e/`, `ehmatthes.github.io/pcc_3e/updates/deploying_django/` (verified against its raw markdown source), `ehmatthes.github.io/pcc_3e/`.
- Reference was run locally (see "How to run the reference"): `chapter_20/styling_learning_log` migrated and served on Django 5.2.19 / Python 3.14.
- Reference screenshots captured at `reference/screenshots/` (10 PNGs): headless Chrome 158, Bootstrap 5.3.8 CSS confirmed applied on every page, page content asserted. See §8.

---

## 1. Verified inventory of the official final state

### 1.1 Models — `learning_logs/models.py`

**Topic**
- `text = models.CharField(max_length=200)`
- `date_added = models.DateTimeField(auto_now_add=True)`
- `owner = models.ForeignKey(User, on_delete=models.CASCADE)`
- `__str__` returns `self.text`

**Entry**
- `topic = models.ForeignKey(Topic, on_delete=models.CASCADE)`
- `text = models.TextField()`
- `date_added = models.DateTimeField(auto_now_add=True)`
- `Meta.verbose_name_plural = 'entries'`
- `__str__` returns `f"{self.text[:50]}..."`

`accounts/models.py` is empty (Django's built-in `auth.User` is used, no custom user model).

Note: there is **no** `updated`/`date_modified` field on `Entry`. The plan makes edit-tracking optional; the reference does not track it.

### 1.2 Forms — `learning_logs/forms.py`

- `TopicForm(ModelForm)`: `model = Topic`, `fields = ['text']`, `labels = {'text': ''}`
- `EntryForm(ModelForm)`: `model = Entry`, `fields = ['text']`, `labels = {'text': ''}`, `widgets = {'text': forms.Textarea(attrs={'cols': 80})}`
- `accounts` has **no** `forms.py`; registration uses `django.contrib.auth.forms.UserCreationForm` directly.

### 1.3 Views — `learning_logs/views.py`

| View | Decorator | Behaviour |
|---|---|---|
| `index(request)` | none | renders `learning_logs/index.html` |
| `topics(request)` | `@login_required` | `Topic.objects.filter(owner=request.user).order_by('date_added')` |
| `topic(request, topic_id)` | `@login_required` | `Topic.objects.get(id=topic_id)`; `if topic.owner != request.user: raise Http404`; `entries = topic.entry_set.order_by('-date_added')` |
| `new_topic(request)` | `@login_required` | on valid POST: `form.save(commit=False)`, `owner=request.user`, `save()`, redirect `learning_logs:topics` |
| `new_entry(request, topic_id)` | `@login_required` | `topic = Topic.objects.get(id=topic_id)`; on valid POST sets `entry.topic = topic`, redirect `learning_logs:topic` |
| `edit_entry(request, entry_id)` | `@login_required` | `entry = Entry.objects.get(id=entry_id)`; `topic = entry.topic`; `if topic.owner != request.user: raise Http404` |

Authorization pattern: **`raise Http404`** on ownership mismatch (not 403). Lookups use `.get(id=...)`, **not** `get_object_or_404`.

### 1.4 Accounts — `accounts/views.py`, `accounts/urls.py`

- `register(request)`: `UserCreationForm`; on valid → `form.save()`, `login(request, new_user)`, redirect `learning_logs:index`.
- `accounts/urls.py`: `app_name='accounts'`;
  - `path('', include('django.contrib.auth.urls'))` → supplies `login/`, `logout/`, `password_change/`, `password_change/done/`, `password_reset/` (and its sub-paths).
  - `path('register/', views.register, name='register')`.

### 1.5 URL patterns

`ll_project/urls.py`: `admin/` → admin; `accounts/` → `accounts.urls`; `''` → `learning_logs.urls`.

`learning_logs/urls.py` (`app_name = 'learning_logs'`):

| Path | Name | View |
|---|---|---|
| `''` | `index` | `views.index` |
| `topics/` | `topics` | `views.topics` |
| `topics/<int:topic_id>/` | `topic` | `views.topic` |
| `new_topic/` | `new_topic` | `views.new_topic` |
| `new_entry/<int:topic_id>/` | `new_entry` | `views.new_entry` |
| `edit_entry/<int:entry_id>/` | `edit_entry` | `views.edit_entry` |

**This differs from the plan's §5 route table**, which guessed `/topics/new/` for topic creation. The reference uses `/new_topic/` at the project root (not nested under `/topics/`).

### 1.6 Templates

Templates resolve from two places: per-app `templates/` dirs (via `APP_DIRS`) and a project-level `templates/` dir (via `TEMPLATES.DIRS = [BASE_DIR / 'templates']`, used only for `404.html`/`500.html`).

| Template | Key content (verified) |
|---|---|
| `learning_logs/base.html` | `<title>Learning Log</title>`; `{% load django_bootstrap5 %}` + `bootstrap_css` + `bootstrap_javascript`; navbar `navbar navbar-expand-md navbar-light bg-light mb-4 border` with brand link, **Topics** link (`me-auto`), account block (`ms-auto`): if authenticated `Hello, {{ user.username }}.` else **Register** + **Log in** links; if authenticated a POST form `Log out` (`btn btn-outline-secondary btn-sm`); blocks `page_header` and `content` |
| `learning_logs/index.html` | hero: `p-3 mb-4 bg-light border rounded-3` wrapper, `h1.display-3` "Track your learning.", `p.lead` description, `btn btn-primary btn-lg` **Register »** linking to `accounts:register` |
| `learning_logs/topics.html` | `h1` Topics; `ul.list-group` of topic links; empty state "No topics have been added yet."; "Add a new topic" link |
| `learning_logs/topic.html` | `h1` = topic text; "Add new entry" link; per entry a `div.card` with `h4.card-header` = `{{ entry.date_added\|date:'M d, Y H:i' }}` + "edit entry" link, and `div.card-body` = `{{ entry.text\|linebreaks }}`; empty state "There are no entries for this topic yet." |
| `learning_logs/new_topic.html` | "Add a new topic:"; POST form; `{{ form.as_div }}`; button "Add topic" |
| `learning_logs/new_entry.html` | link back to topic; "Add a new entry:"; POST form; `{{ form.as_div }}`; button "Add entry" |
| `learning_logs/edit_entry.html` | link back to topic; "Edit entry:"; POST form; `{{ form.as_div }}`; button "Save changes" |
| `accounts/.../login.html` | `page_header` "Log in to your account."; `{% load django_bootstrap5 %}`; `{% bootstrap_form form %}`; `{% bootstrap_button button_type="submit" content="Log in" %}` |
| `accounts/.../register.html` | POST form; `{{ form.as_div }}`; button "Register" |
| `templates/404.html` | `page_header` "The item you requested is not available. (404)" |
| `templates/500.html` | `page_header` "There has been an internal error. (500)" |

All state-changing forms use `{% csrf_token %}`; logout is a **POST** form.

### 1.7 Settings — `ll_project/settings.py`

> Describes the *reference* app as captured in Phase 0. Maarifa's own settings
> diverged in Phase 1 (PostgreSQL from `DATABASE_URL`, no SQLite); §12 is the
> current truth for this repository.

- `INSTALLED_APPS`: `learning_logs`, `accounts`, `django_bootstrap5`, then the Django defaults.
- `MIDDLEWARE`: Django defaults only (`Security`, `Session`, `Common`, `Csrf`, `Auth`, `Messages`, `XFrameOptions`).
- `TEMPLATES`: `DIRS = [BASE_DIR / 'templates']`, `APP_DIRS = True`.
- `DATABASES`: SQLite at `BASE_DIR / 'db.sqlite3'`.
- `STATIC_URL = 'static/'`; no `STATICFILES_DIRS`, no custom static files (Bootstrap comes from `django-bootstrap5`).
- `LOGIN_REDIRECT_URL = 'learning_logs:index'`, `LOGOUT_REDIRECT_URL = 'learning_logs:index'`, `LOGIN_URL = 'accounts:login'`.
- `SECRET_KEY` is hardcoded (the book's value); `DEBUG = True`; `ALLOWED_HOSTS = []`.
- A `platformshconfig` block runs only on Platform.sh: sets `DEBUG = False`, appends `.platformsh.site`, `SECRET_KEY = config.projectEntropy`, and rebuilds `DATABASES` on the Platform.sh PostgreSQL credentials.

### 1.8 Migrations

- `learning_logs`: `0001_initial` (Topic), `0002_entry` (Entry), `0003_topic_owner` (adds `owner` FK).
- `accounts`: `migrations/__init__.py` only.

### 1.9 Deployment files — `chapter_20/deploying_learning_log`

- `.platform.app.yaml`: `name: ll_project`, `type: "python:3.10"`, `relationships: database: "db:postgresql"`, `start: "gunicorn -w 4 -b unix:$SOCKET ll_project.wsgi:application"`, `/static` location, build hook (`pip install -r requirements.txt`, `-r requirements_remote.txt`, `collectstatic`), deploy hook (`manage.py migrate`).
- `.platform/routes.yaml`, `.platform/services.yaml`, `.platform/local/*`.
- `requirements.txt`: `asgiref==3.5.2`, `beautifulsoup4==4.11.1`, `Django==4.1b1`, `django-bootstrap5==21.3`, `platformshconfig==2.4.0`, `soupsieve==2.3.2.post1`, `sqlparse==0.4.2`.
- `requirements_remote.txt`: `gunicorn`, `psycopg2`.
- `.gitignore`: `ll_env/`, `__pycache__/`, `*.sqlite3`, `.DS_Store`.

### 1.10 Static assets

No project `static/` directory in the official Ch. 20 code. Bootstrap 5 is provided by `django-bootstrap5` template tags (`bootstrap_css`/`bootstrap_javascript` in `base.html`). The plan's suggested `static/css` and `static/images` do not exist in the reference.

---

## 2. Chapter progression (verified)

| Stage | Directory | Adds |
|---|---|---|
| Ch. 18 | `making_pages` | `Topic` model only; `index.html`; minimal `urls.py`/`views.py` |
| Ch. 18 | `building_additional_pages` | `base.html`; `topics.html`; `topic.html`; nav; `0002_entry` adds `Entry` |
| Ch. 19 | `setting_up_user_accounts` | `accounts` app (`login.html`, `register.html`, `register` view, auth URLs); **no** `owner` yet |
| Ch. 19 | `allowing_users_to_own_their_data` | `owner` FK on `Topic`; `0003_topic_owner`; `@login_required`; `Http404` ownership checks |
| Ch. 20 | `styling_learning_log` | `django-bootstrap5` styling across all templates (hero, cards, list-group, bootstrap forms) |
| Ch. 20 | `deploying_learning_log` | `templates/404.html`, `templates/500.html`; `.platform/` + `.platform.app.yaml`; `requirements.txt`, `requirements_remote.txt` |

`owner` is introduced only in `allowing_users_to_own_their_data` (Ch. 19), confirmed by the presence of `0003_topic_owner` there and its absence in `setting_up_user_accounts`.

---

## 3. Page-by-page interface and user journeys

| Page | Route | Access | What the user sees / does |
|---|---|---|---|
| Home | `/` | Public | Hero "Track your learning." + **Register »** button; navbar shows Register + Log in |
| Register | `/accounts/register/` | Public | `UserCreationForm` (username, password1, password2); submit "Register"; on success auto-login → home |
| Login | `/accounts/login/` | Public | Username/password; bootstrap-styled submit "Log in"; success → `LOGIN_REDIRECT_URL` (home). Bad creds → form errors |
| Log out | `/accounts/logout/` | Authenticated | POST from navbar button → `LOGOUT_REDIRECT_URL` (home) |
| Topics | `/topics/` | Authenticated | Ordered list (oldest first) of the user's topics; empty state; "Add a new topic" |
| New topic | `/new_topic/` | Authenticated | Single `text` field; submit "Add topic" → back to `/topics/` |
| Topic detail | `/topics/<id>/` | Owner only | `h1` topic; "Add new entry"; newest-first entry cards with timestamp + "edit entry"; empty state |
| New entry | `/new_entry/<topic_id>/` | Authenticated | Single `text` textarea (80 cols); submit "Add entry" → back to topic |
| Edit entry | `/edit_entry/<entry_id>/` | Owner only | Pre-filled textarea; submit "Save changes" → back to topic |
| Admin | `/admin/` | Staff | Django admin |

Journey: register → auto-login → create topic → open topic → add entry → edit entry; log out; log back in. Non-owner or anonymous hitting a protected path is redirected to login (`@login_required`) or gets 404 (ownership mismatch).

---

## 4. Deployment guidance: book vs. author's current advice

| | Book (Ch. 20 source) | Author's current guidance |
|---|---|---|
| Host | Platform.sh | **Scalingo** (Platform.sh rebranded to **Upsun** and is **no longer recommended**) |
| Mechanism | manual `.platform.app.yaml`, `platformshconfig` | `django-simple-deploy` via plugin `dsd-scalingo` (`pip install dsd-scalingo`, add `django_simple_deploy` to `INSTALLED_APPS`, `python manage.py deploy --automate-all`) |
| Python | `python:3.10` (buildpack) | `.python-version` file |
| Django pinned | `Django==4.1b1` | `django==5.2.8` (`django-bootstrap5==25.2`, `asgiref==3.10.0`, `sqlparse==0.5.3`) |
| Created files | `.platform/*` | `.gitignore`, `.python-version`, `Procfile`, `bin/post_deploy.sh` |
| Prod DB | Platform.sh `db:postgresql` via `config.credentials('database')` | `dj_database_url.config(env="DATABASE_URL", ...)` |
| Prod settings block | `if config.is_valid_platform():` → `DEBUG=False` | `if "scalingo" in os.environ.get("STACK", ""):` → `DEBUG=False`, `ALLOWED_HOSTS=["*"]`, WhiteNoise `CompressedManifestStaticFilesStorage`, `STATIC_ROOT='staticfiles'` |
| `SECRET_KEY` in prod | `config.projectEntropy` | **not mentioned** on the page |
| Later pushes | `platform push` | `git push scalingo main` |

Exact wording (author's page): the book "walks you through the process of deploying Learning Log to the hosting company Platform.sh. That company has rebranded as Upsun, but they've changed their approach to deployment so much that I can no longer recommend them ... However, [Scalingo](https://scalingo.com/) is a modern web hosting platform that supports Django."

Exact wording (`new_in_3e`): "The third edition uses Python 3.11." / "The Learning Log project is built using Django 4.1, and the project is styled using Bootstrap 5."

---

## 5. Current repository vs. the official reference (verified diffs)

The current repo is **not** a copy of the reference; it is a hand-typed variant and contains defects. `diff -rq` of `chapter_20/deploying_learning_log` against the repo shows differing files across the app plus the following.

**Defects in the current repo:**

1. `learning_logs/models.py:21-26` — `Entry.__str__` is indented **inside** `class Meta`, so `Entry` has no `__str__`. The reference defines it on the class.
2. `accounts/templates/registration/login.html` — malformed: 13 lines, ends mid-tag at `</`, missing `</form>` and `{% endblock %}`. Django raises `TemplateSyntaxError: Unclosed tag on line 3: 'block'`, so `/accounts/login/` 500s.
3. `learning_logs/urls.py:12` — `path('topics/<int:topic_id>', ...)` is missing its trailing slash (reference: `topics/<int:topic_id>/`).
4. `learning_logs/urls.py:16` — the new-entry route is `new_topic/<int:topic_id>/` with `name='new_entry'`; the reference (and the plan §5) use `new_entry/<int:topic_id>/`. The route is wrong.
5. `learning_logs/templates/learning_logs/index.html` — placeholder text ("Learning Log helps you keep track of your learning, for any topic you are interested in"); missing the reference's `display-3` hero and **Register** button.

**Structural gaps vs. the reference:**

- No `templates/404.html` or `templates/500.html`; no project-level `templates/` dir.
- No `.platform/` deploy config, no `requirements_remote.txt`.
- `admin.py` files are Django's stubs (reference registers `Topic` and `Entry`).

**Files that already match the reference** (safe to keep): `learning_logs/views.py`, `learning_logs/forms.py`, `accounts/views.py`, `accounts/urls.py`, `learning_logs/templates/learning_logs/base.html`.

Migrations differ only in the "Generated by Django X.Y" header and import ordering — the repo's were regenerated with Django 5.2.1 (repo's committed venv held `Django 5.2.1`), the reference's with `4.1b1`.

---

## 6. Uncertainties and decisions needed

_Decisions confirmed by Brian on 2026-11-24 are marked **DECIDED**; the rest stay open._

1. **Screenshots — RESOLVED.** Headless Chrome is available on this machine (see §8). Ten reference PNGs are captured and verified under `reference/screenshots/`. **DECIDED (2026-11-24):** commit them as repo docs (§6.7).
2. **Bootstrap version** — the book states "Bootstrap 5"; the book's own lockfile pins `django-bootstrap5==21.3`, the author's current guide uses `25.2`. **DECIDED (2026-11-24):** current latest, `django-bootstrap5==26.4` (installed and pinned in `requirements.txt`).
3. **Django version** — plan §2 says use a currently supported release, not the book's 4.1. **DECIDED (2026-11-24):** Django `5.2.19`, the latest 5.2 LTS patch (installed and pinned).
4. **`new_entry` ownership hole** — the official book view does **not** check that the topic belongs to the current user, so a logged-in user can add an entry to any topic by URL. Plan §5 and §9 explicitly require this check ("User A cannot create an entry under User B's topic"). **DECIDED (2026-11-24):** add the ownership check (diverge from the book) and document it as a deliberate difference.
5. **Deployment provider** — plan §2 says provider choice is a separate decision. The repo currently ships Platform.sh config; the author recommends Scalingo. Decide before Phase 9.
6. **Route nestling** — plan §5 guessed `/topics/new/`; the reference uses `/new_topic/`. **DECIDED (2026-11-24):** follow the reference, `/new_topic/` (URL-name `learning_logs:new_entry`).
7. **Commit the reference screenshots?** — `reference/screenshots/` holds 10 PNGs (~400 KB total). They are the Phase 7 visual baseline. **DECIDED (2026-11-24):** commit them as repo docs.

---

## 7. Proposed implementation checklist (mapped to plan phases)

- **Phase 1 — foundation:** decide Django/SQLite versions (§6.2/6.3); keep `ll_project/` package name (the plan's `config/` is a suggestion); confirm `base.html`, `LOGIN_*` settings, `db.sqlite3`, and that `manage.py check` is clean. *(Done; the `db.sqlite3` item is superseded by §12 — the app now runs on PostgreSQL and has no SQLite path.)*
- **Phase 2 — models/admin:** fix `Entry.__str__` nesting; register `Topic`/`Entry` in admin; keep `0001-0003` migrations; add model tests (relationships, `__str__`).
- **Phase 3 — public pages/layout:** rebuild `index.html` to the `display-3` hero; confirm `base.html` nav + auth-aware links; add `pytest`/`pytest-django` scaffold with model tests.
- **Phase 4 — topics:** fix the `topics/<id>/` trailing slash; scope queries to `request.user`; add form validation + empty state; authorization tests (anonymous redirect, cross-user 404).
- **Phase 5 — entries:** fix the `new_entry/<topic_id>/` route; **add the missing parent-topic ownership check** (§6.4); entry view/form tests incl. cross-user creation.
- **Phase 6 — auth:** fix the broken `login.html`; add registration/login/logout tests and redirect assertions.
- **Phase 7 — visual matching:** run the reference, compare each page, align typography/spacing/cards/buttons; record unavoidable differences.
- **Phase 8 — QA:** full test suite, `manage.py check`, two-user isolation walkthrough, accessibility pass.
- **Phase 9 — docs/deploy:** README setup, env var + migration docs, deployment config (provider per §6.5).

---

## 8. Captured reference screenshots (Phase 0 artifact)

Location: `reference/screenshots/` (in the repo workspace; commit decision in §6.7).

| File | Page | Route | Context | Viewport |
|---|---|---|---|---|
| `home.png` | Public home / hero | `/` | anonymous | 1280×900 |
| `login.png` | Login form | `/accounts/login/` | anonymous | 1280×900 |
| `register.png` | Registration form | `/accounts/register/` | anonymous | 1280×900 |
| `topics.png` | Topic list | `/topics/` | `demo` | 1280×900 |
| `topic_detail.png` | Topic detail + entry cards | `/topics/1/` | `demo` | 1280×900 |
| `new_topic.png` | New-topic form | `/new_topic/` | `demo` | 1280×900 |
| `new_entry.png` | New-entry form | `/new_entry/1/` | `demo` | 1280×900 |
| `edit_entry.png` | Edit-entry form | `/edit_entry/1/` | `demo` | 1280×900 |
| `mobile_home.png` | Home (responsive) | `/` | anonymous | 390×844 @2x |
| `mobile_topic_detail.png` | Topic detail (responsive) | `/topics/1/` | `demo` | 390×844 @2x |

How they were produced and verified (so the baseline is reproducible, not trusted):

- Driver: headless Google Chrome 158 via `puppeteer-core` (a throwaway driver kept outside the repo, not committed). Public pages captured in an anonymous browser context, private pages in a logged-in `demo` context — so the visitor navbar (Register/Log in) is what `home/login/register` show.
- Verification (three passes): (1) every page reported the Bootstrap 5.3.8 stylesheet applied, checked by computed style, navbar `bg-light` = `rgb(248,249,250)` and `.btn-primary` = `rgb(13,110,253)`; (2) every PNG is non-trivial (sampled distinct bytes ≥ 100, correct 1280×900 / 390×844 dimensions); (3) a content assertion confirmed expected strings per page (`Track your learning.`, `Log in to your account.`, topic names, form buttons) and no traceback/error page. All passed. Raw results in `reference/screenshots/capture-manifest.json`.
- The screenshots reflect the reference's **live CDN Bootstrap** (`bootstrap@5.3.8` from jsDelivr at capture time) even though the book's lockfile pins `django-bootstrap5==21.3` (see §6.2) — i.e. current Bootstrap-5 styling, which is what the plan asks for.

---

## 9. Phase 7 — visual matching results (2026-11-24)

Goal: every page must visually match the reference; markup/CSS only, no new features. Two independent, reproducible layers.

**Layer A — source byte diff.** Every `.py` and `.html` under `learning_logs/` and `accounts/` was diffed against `/tmp/pcc_3e/chapter_20/styling_learning_log`. No template diverges from the reference in any way that can render differently. The only template differences are a trailing newline at EOF (ours has one, the reference's does not) and one blank line in `index.html` that in the reference carries 6 trailing spaces and in ours is empty (both collapse to the same whitespace node). The one genuine markup divergence found, a mixed space+tab indent in `new_topic.html`, was corrected in this phase; it now differs only by the trailing newline. Python differences are comments, docstrings, import order, whitespace, and the deliberate Phase 4/5 ownership edits (`get_object_or_404(..., owner=request.user)`), none of which affect rendering.

**Layer B — pixel diff.** All 10 pages were captured with the Phase 0 harness (headless Chrome 158, same viewports, same seeded `demo` data) and diffed against `reference/screenshots/`: **all 10 pages byte-identical to the baseline (sha256)**. In addition, 66 viewport widths straddling the Bootstrap breakpoints (`navbar-expand-md` at 768, plus 576/992/1200), 9 hover/focus/active states, and 4 states the fixed snapshots never render (wrong-password re-render, register password mismatch, empty new-topic/new-entry, empty topic list, long content on an empty and a populated topic) were compared side by side: zero differences.

**Recorded differences (all non-visual; none is a Phase 7 markup issue):**

1. **Trailing newline at EOF.** Every source file of ours ends with a newline; the reference's do not. Invisible; kept deliberately (POSIX convention, clean diffs).
2. **`index.html` blank line.** Reference line 6 is `"      \n"`, ours is `"\n"`. HTML whitespace collapsing makes this invisible; the rendered home screenshot is byte-identical.
3. **Login/register text caret.** A 1x22 px delta can appear on `login`/`register` between runs: the blinking caret in the autofocused username input. Non-deterministic in the harness; re-capturing the reference server against its own baseline reproduces the identical 1x22 sliver at the same coordinates, so it is harness-side, not markup.
4. **Missing-ID responses (pre-existing, non-visual).** `/topics/99999/`, `/new_entry/99999/`, `/edit_entry/99999/` return 404 in ours and 500 in the reference (the reference lets `Topic.DoesNotExist` escape; we use `get_object_or_404` with an owner filter, per section 6.4 and Phases 4/5). Ours is the strictly better behaviour and it is not reachable from normal navigation.
5. **`settings.py` `context_processors.debug`.** Ours omits it; no template references `debug` or `sql_queries`, so rendering is unaffected.

---

## 10. Phase 8 — quality assurance results (2026-11-24)

Goal (plan §8): run the full suite and the system checks, walk every main flow as two separate users, check keyboard/labels/focus/mobile, and review security settings and dependency versions.

**Deterministic checks**

- `pytest -q` → **137 passed** (104 at the end of Phase 7; +33 this phase).
- `manage.py check` → no issues (0 silenced).
- `manage.py check --deploy` → 5 warnings, all production-hardening defaults deferred to Phase 9: `security.W004` (HSTS), `W008` (SSL redirect), `W012` (`SESSION_COOKIE_SECURE`), `W016` (`CSRF_COOKIE_SECURE`), `W018` (`DEBUG` may be True).

**Three independent verifier passes** (separate throwaway copies, seeded `alice`/`bob`, run in parallel; reports under `/tmp/ll-phase8/{security,isolation,a11y}/REPORT.md`)

1. **Security and dependencies — PASS, with one history finding.** CSRF is enforced on all six state-changing endpoints (a token-less POST is 403, a token-carrying POST succeeds) verified both with `Client(enforce_csrf_checks=True)` and against a live server with `curl`; user content is escaped and inert across the five XSS payloads the unit tests define; `MIDDLEWARE` carries `SecurityMiddleware`, `CsrfViewMiddleware` and `XFrameOptionsMiddleware`; `requirements.txt` matches `pip freeze`, `pip check` is clean, Django is 5.2.19 LTS with no known advisories.
2. **Two-user isolation — PASS on all 8 acceptance items.** Anonymous visitors are redirected; `alice` sees only her topics; a cross-user topic or entry id returns 404 (get and post); a crafted POST into `bob`'s topic returns 404 and creates nothing (entry count stays 1, zero injected rows); each user's own flows work; logout is POST-only (GET 405).
3. **Accessibility (axe-core 4.14.1, 8 pages x 2 viewports) — 24 violation instances on the untouched reference markup**: 6 CRITICAL (unlabelled `#id_text` on the three form pages), 6 SERIOUS (colour contrast on `Log out` 4.44:1 and `edit entry` 4.24:1), 12 MODERATE (missing `<h1>` on 5 pages, heading-order on the topic page). Keyboard journey passes: no focus trap, every focusable element shows a visible focus indicator.

**Decision 1 — accessibility.** These defects are inherited byte-for-byte from the reference, and Phase 7 pinned byte-identical visual parity, so most fixes would move pixels. Only the CRITICAL defect was fixed, and only invisibly: `TopicForm`/`EntryForm` now carry an `aria-label` ("Topic text" / "Entry text") on the text widget while the visible label stays empty, so the control has an accessible name and nothing moves on screen. The 18 remaining (SERIOUS contrast + MODERATE headings) are recorded here as **accepted debt inherited from the reference**, not fixed, to hold the parity requirement. A regression test (`learning_logs/tests/test_accessibility.py`) pins that the name is present and that no visible label reappears.

**Decision 2 — committed secret.** A development `SECRET_KEY` (`django-insecure-…`, hardcoded at `ll_project/settings.py:23` in commit `b3c3fd7`) is present in git **history**; it was removed from the working tree in `c43b8aa` and settings now require `DJANGO_SECRET_KEY` from the environment. It was a local development key that never signed production sessions, so it is documented here and **accepted** rather than purged from history (a rewrite would change every commit hash and destroy the existing audit trail).

**Coverage added this phase** (`accounts/tests/test_security.py`, `learning_logs/tests/test_security.py`, `learning_logs/tests/test_accessibility.py`; +33 tests). Before this phase the only CSRF assertions were of the form `assert 'csrfmiddlewaretoken' in html`, which is proof a token is emitted, not that a request without one is refused (Django's test client disables CSRF checks by default), and no test exercised output escaping. The new tests cover: token-less POST rejected with 403 and no side effect on all six endpoints; the issued token accepted; a wrong token rejected while the CSRF cookie is present; topic title escaped on the topics list and the topic page, and entry body escaped on the topic page; stored `{{ 7*7 }}` not re-evaluated as template code; and a stored payload in one user's topic invisible to another (404).

---

## 11. Phase 9 — documentation and deployment readiness (2026-11-24)

Goal (plan §8): write setup instructions, document the environment variables and
migrations, document how to run the tests, add production configuration for the
chosen host, and confirm the local acceptance criteria pass. The five
`check --deploy` warnings Phase 8 deferred (W004 HSTS, W008 SSL redirect, W012
session cookie, W016 CSRF cookie, W018 DEBUG) are resolved here.

**Host decision.** §6.5 left the provider open. The book's `chapter_20` ships an
obsolete Platform.sh config (`.platform.app.yaml`, `python:3.10`), so it is not
used. The author's current guidance adopts **Scalingo**, and the repo is prepared
for it while the actual deploy stays with the operator (local verification only).

**Authoritative source for the platform files.** The author's guide drives
`django-simple-deploy` with the `dsd-scalingo` plugin (`ehmatthes/dsd-scalingo`),
whose generator (`dsd_scalingo/platform_deployer.py`, `.../templates/settings.py`)
emits exactly the files below. They were reproduced from that generator rather
than guessed:

| File | Content |
| --- | --- |
| `Procfile` | `web: gunicorn ll_project.wsgi --log-file -` and `postdeploy: bash bin/post_deploy.sh` |
| `bin/post_deploy.sh` | `#!/bin/sh` then `python manage.py migrate` (executable, mode `775`) |
| `.python-version` | `3.14` (buildpack pins the interpreter) |

**Deviations from the generator** (documented rather than copied blindly):
`psycopg[binary]` (psycopg 3) replaces `psycopg2`; `dj-static` is omitted because
WhiteNoise already serves the static files; and the static block sets both
`STORAGES` keys explicitly (`default` and `staticfiles`) rather than only
`staticfiles`. `STATICFILES_DIRS` is absent because the project ships no local
static directory at all (no top-level `static/`, no app `static/`); the Bootstrap
assets come from the CDN through `django-bootstrap5`.

**`ll_project/settings.py`.** Two additive blocks, both inert locally:

1. A `STACK`-gated Scalingo block (`if 'scalingo' in os.environ.get('STACK', '')`):
   switches `DATABASES` to the platform PostgreSQL via `dj_database_url`, forces
   `DEBUG = False`, inserts `WhiteNoiseMiddleware`, sets the WhiteNoise
   `CompressedManifestStaticFilesStorage` for static files, and uses
   `ALLOWED_HOSTS = ALLOWED_HOSTS or ['*']` so an explicit
   `DJANGO_ALLOWED_HOSTS` is honoured and only an unset one falls back to the
   platform default.
2. A `DEBUG`-gated production-hardening block (`if not DEBUG`): sets
   `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`,
   `CSRF_COOKIE_SECURE`, and one-year HSTS with subdomains and preload.

`STATIC_ROOT = BASE_DIR / 'staticfiles'` was added unconditionally (git-ignored).

**Documentation.** `README.md` was rewritten: corrected project structure (adds
`Procfile`, `.python-version`, `bin/post_deploy.sh`, `tests/`, `conftest.py`),
the required `.env`/`DJANGO_SECRET_KEY` step, an Environment Variables table, a
Database Migrations section, a Running the Tests section, and a Scalingo
deployment section. `.env.example` already documents the three local variables.

**Deterministic results**

- `manage.py check --deploy --fail-level WARNING` with `DJANGO_DEBUG=False
  DJANGO_ALLOWED_HOSTS=example.com` → **no issues (0 silenced)**; the five Phase 8
  warnings are resolved.
- `manage.py check` → no issues. `manage.py collectstatic` → 127 files copied.
- Scalingo branch confirmed through a fresh interpreter with
  `STACK=scalingo-26` and a `DATABASE_URL`: `DEBUG=False`, DB engine
  `django.db.backends.postgresql`, WhiteNoise in `MIDDLEWARE`, the manifest
  storage for `staticfiles`, and every hardening flag on.
- `tests/test_production_settings.py` (+7 tests) starts a fresh interpreter per
  scenario, which is the only honest way to test settings evaluated once at import.

**README verified from a clean checkout** (acceptance: "README setup instructions
work from a clean checkout"). The tree was copied to `/tmp/ll-clean` without
`.git`/`.venv`/`.env`/`db.sqlite3`, then the documented steps were run: venv,
`pip install -r requirements.txt` (`pip check` clean), `.env` from `.env.example`
with a generated key, `manage.py migrate` on a fresh database (all migrations OK),
`pytest` → **144 passed**. A gunicorn smoke test of the exact `Procfile` web
command returned HTTP 200 for `/` and `/accounts/login/`.

Note: this container's `/usr/bin/python3` ships without `ensurepip`, so
`python3 -m venv .venv` produces a venv without pip here; pip was bootstrapped
with `get-pip.py` to mirror how the project's own venv was built. On a normal
machine `python3 -m venv` includes pip and the README step works verbatim.

**Bug found and fixed by that clean-checkout run.** `tests/test_production_settings.py`
was not hermetic: `_env()` pinned `DJANGO_SECRET_KEY` and cleared `STACK`/
`DATABASE_URL`, but not `DJANGO_ALLOWED_HOSTS`. Because `settings.py` calls
`load_dotenv(BASE_DIR / '.env')` and `load_dotenv` does not override a variable
already set, a developer `.env` containing `DJANGO_ALLOWED_HOSTS` leaked into the
child interpreter and broke the assertion that an unset value falls back to
`['*']`. It had passed earlier only while `.env` was empty. `_env()` now pins
`DJANGO_DEBUG` and `DJANGO_ALLOWED_HOSTS` too, so the tests no longer depend on a
machine's local configuration.

**Three-pass README verification.** (1) Every command in Setup, Environment
Variables, Migrations, Tests and Deployment was run in `/tmp/ll-clean` and its
output matched what the text claims. (2) The internal links (`requirements.txt`,
`.env.example`) resolve to real files. (3) The deployment section was checked
against the Scalingo CLI surface and the `dsd-scalingo` generator; the env-set,
addon, `git-show` and postdeploy steps match the platform's documented flow.

---

## 12. Phase 1 — PostgreSQL foundation and env split (2026-11-24)

Goal (plan §4, Phase 1): the app runs on PostgreSQL locally, in tests, and in
production, with no SQLite in the code path; `DATABASE_URL` drives the connection
in every environment; a local PostgreSQL is one command away; the `pgvector`
extension is present where available.

**`ll_project/settings.py`.** `DATABASES` now reads `DATABASE_URL` everywhere via
`dj_database_url.config(...)`, with the SQLite default deleted. When the variable
is unset the default targets the docker-compose service
(`postgres://maarifa:maarifa@127.0.0.1:5433/maarifa`). `conn_max_age=600` and
`conn_health_checks=True` are on; `dj_database_url` is imported at module level.
The `STACK=scalingo` block no longer overrides `DATABASES` (the DB is
env-driven now); it still forces `DEBUG=False`, inserts WhiteNoise, sets the
manifest static storage, and applies the `ALLOWED_HOSTS` fallback. The Scalingo
branch keeps the one database setting it used to own:
`DATABASES['default']['OPTIONS']['sslmode'] = 'require'`, so the platform
deployment reaches PostgreSQL over TLS. It deliberately keys off `STACK`
(platform), not `DEBUG`: the docker-compose database speaks no TLS, so a local
`DJANGO_DEBUG=False` run (to exercise `check --deploy`) must still connect.

**Env split.** Every environment difference is now an environment variable
(`DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_URL`,
`STACK`), matching P0's rule that infrastructure values live in env vars, not
`Setting` rows and not code branches. `.env.example` documents `DATABASE_URL`
with the same default the settings fall back to.

**`docker-compose.yml` + `docker/postgres/init.sql`.** One service, `db`, on
`pgvector/pgvector:pg17` — PostgreSQL 17 with the `vector` extension available.
The host port is **5433**, published as `${POSTGRES_PORT:-5433}:5432`, chosen so
a system PostgreSQL already bound to 5432 does not collide (this machine runs
one). An `init.sql` runs `CREATE EXTENSION IF NOT EXISTS vector;` on first
volume creation; a `pg_isready` healthcheck gates readiness. The compose service
and the settings fallback are kept in lockstep by a gate test, so a fresh clone
cannot start a container it then fails to reach.

**`pytest.ini` change (recorded).** Added `addopts = --create-db
--strict-markers`, with a comment stating that the suite runs on PostgreSQL and
that the connection comes from `DATABASE_URL`. `--create-db` is pinned so the
test database is rebuilt every run regardless of a developer's `PYTEST_ADDOPTS`
(a reused database could hide a missing migration); `--strict-markers` fails on a
mistyped marker instead of ignoring it. No DB options belong in `pytest.ini` —
the URL is owned by the settings module.

**`.gitignore`.** The `db.sqlite3` / `db.sqlite3-journal` rules are kept, as
defence in depth: nothing in the code path writes those files any more, but an
old command or a stray tool still could, and a binary must never reach a commit.
The rules ignore a file, they do not reference a backend.

**Tests.** New `tests/test_database_config.py` (9 tests): the loaded engine is
PostgreSQL; no project `.py` references SQLite (AST scan for a `.sqlite3` string,
a `sqlite://` URL, or a `sqlite3` import, prose excluded); a meta-test proves that
scanner catches every shape (backend literal, URL string, bare and dotted
import);
`DATABASE_URL` is honoured; the unset fallback matches the compose service's
port, database, and user; the compose image is the pgvector one; `init.sql`
enables the extension; and the extension is installable on the server running the
suite (skipped, not failed, when the server lacks it).
`tests/test_production_settings.py` was updated for the new truth (local
development is PostgreSQL, not SQLite), asserts the Scalingo branch requires
`sslmode=require`, and asserts a plain `DEBUG=False` deployment does not (so the
local Docker database stays reachable).

**Deterministic results**

- `docker compose up -d db` → healthy; `pg_extension` lists `vector`.
- Full suite on the Docker PostgreSQL: **153 passed** (144 existing + 9 new),
  0 failed, 0 skipped — the pgvector test ran and passed on this server.
- `manage.py check` → no issues. `manage.py check --deploy --fail-level WARNING`
  with `DJANGO_DEBUG=False` and a strong key → **no issues (0 silenced)**.
- No SQLite engine string remains in any project Python module (asserted).

---

## How to run the reference

```bash
# official app, styled, on the local interpreter
cp -r /tmp/pcc_3e/chapter_20/styling_learning_log /tmp/ll_ref
cd /tmp/ll_ref
/home/codetitan/projects/Learning_Log/.venv/bin/python manage.py migrate
/home/codetitan/projects/Learning_Log/.venv/bin/python manage.py runserver 127.0.0.1:8765
# then open http://127.0.0.1:8765/
```

Login with the seeded demo account: username `demo`, password `demopass123` (local throwaway only).

Screenshot re-capture: reproduce the §8 baseline with headless Chrome plus `puppeteer-core` against the server above and the `demo` account. Log in for the private pages, use a fresh context for the public pages, assert each page's content and that Bootstrap applied, then write `reference/screenshots/`.
