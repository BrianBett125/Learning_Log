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

- **Phase 1 — foundation:** decide Django/SQLite versions (§6.2/6.3); keep `ll_project/` package name (the plan's `config/` is a suggestion); confirm `base.html`, `LOGIN_*` settings, `db.sqlite3`, and that `manage.py check` is clean. *(Largely done.)*
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

- Driver: headless Google Chrome 158 via `puppeteer-core` (installed under `/tmp/ll-shots`, not the repo). Public pages captured in an anonymous browser context, private pages in a logged-in `demo` context — so the visitor navbar (Register/Log in) is what `home/login/register` show.
- Verification (three passes): (1) every page reported the Bootstrap 5.3.8 stylesheet applied, checked by computed style, navbar `bg-light` = `rgb(248,249,250)` and `.btn-primary` = `rgb(13,110,253)`; (2) every PNG is non-trivial (sampled distinct bytes ≥ 100, correct 1280×900 / 390×844 dimensions); (3) a content assertion confirmed expected strings per page (`Track your learning.`, `Log in to your account.`, topic names, form buttons) and no traceback/error page. All passed. Raw results in `reference/screenshots/capture-manifest.json`.
- The screenshots reflect the reference's **live CDN Bootstrap** (`bootstrap@5.3.8` from jsDelivr at capture time) even though the book's lockfile pins `django-bootstrap5==21.3` (see §6.2) — i.e. current Bootstrap-5 styling, which is what the plan asks for.

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

Screenshot re-capture: the headless-Chrome pipeline that produced §8 is `node /tmp/ll-shots/capture.js` (driver in `/tmp/ll-shots`, needs the server above running and the `demo` account). It re-verifies Bootstrap applied and asserts each page's content, then writes `reference/screenshots/`.
