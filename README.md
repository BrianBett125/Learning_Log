# 📘 Learning Log

Learning Log is a Django web application that lets users track their learning by
organizing topics and recording dated entries under each one.

---

## 🚀 Overview

This application allows users to:

* Create learning topics
* Log entries under each topic
* Review past entries
* Manage and edit their own records

Data is private: every topic belongs to one user, and ownership is enforced
server-side on every view, so one user can never read or modify another's data.

---

## 🧠 Core Features

* 🔐 User authentication (register, login, logout)
* 📂 Topic management (create and list)
* 📝 Entry logging per topic
* ✏️ Editing of existing entries
* 🎨 Bootstrap 5 interface shared across every page

---

## 🏗️ Tech Stack

| Layer      | Technology                                       |
| ---------- | ------------------------------------------------ |
| Language   | Python 3.14                                      |
| Backend    | Django 5.2 (LTS)                                 |
| Frontend   | Bootstrap 5 via `django-bootstrap5`              |
| Database   | SQLite (development), PostgreSQL (Scalingo)      |
| Testing    | `pytest` + `pytest-django`                       |
| Deployment | Scalingo (gunicorn, WhiteNoise, `dj-database-url`) |

Exact versions are pinned in [requirements.txt](requirements.txt).

---

## 📁 Project Structure

```
Learning_Log/
├── manage.py
├── requirements.txt
├── pytest.ini                 # pytest configuration
├── conftest.py                # test bootstrap (supplies a throwaway SECRET_KEY)
├── Procfile                   # Scalingo process definitions (web, postdeploy)
├── .python-version            # Python version Scalingo builds with
├── .env.example               # template for local configuration
├── reference-inventory.md     # Phase 0 audit of the reference implementation
├── bin/
│   └── post_deploy.sh         # runs `migrate` after each deploy
├── ll_project/                # project settings and root URL configuration
│   ├── settings.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── learning_logs/             # topics and entries
│   ├── migrations/
│   ├── templates/learning_logs/
│   ├── tests/
│   ├── admin.py
│   ├── forms.py
│   ├── models.py
│   ├── urls.py
│   └── views.py
├── accounts/                  # registration and authentication
│   ├── migrations/
│   ├── templates/registration/
│   ├── tests/
│   ├── urls.py
│   └── views.py
├── reference/
│   └── screenshots/           # visual baseline captured from the reference app
└── tests/                     # project-level configuration tests
    └── test_production_settings.py
```

Templates live inside the app that owns them, not in a top-level `templates/`
directory.

---

## ⚙️ Setup & Installation

### 1. Clone the repository

```
git clone https://github.com/BrianBett125/Learning_Log.git
cd Learning_Log
```

### 2. Create and activate a virtual environment

```
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```
.venv\Scripts\activate
```

### 3. Install dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create your `.env` file

The settings module reads `DJANGO_SECRET_KEY` from the environment and refuses to
start without it. Copy the template and fill in a freshly generated key:

```
cp .env.example .env
python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
```

Paste the printed value into `.env` as `DJANGO_SECRET_KEY`. The real `.env` is
git-ignored and must never be committed.

### 5. Apply migrations

```
python manage.py migrate
```

### 6. Create a superuser (optional, for the admin site)

```
python manage.py createsuperuser
```

### 7. Run the development server

```
python manage.py runserver
```

Then open:

* App: http://127.0.0.1:8000/
* Admin: http://127.0.0.1:8000/admin/

---

## 🔑 Environment Variables

Set these in `.env` for local development, or in the host's environment for
deployment. See [.env.example](.env.example).

| Variable               | Required        | Default | Purpose                                                                                                   |
| ---------------------- | --------------- | ------- | --------------------------------------------------------------------------------------------------------- |
| `DJANGO_SECRET_KEY`    | Yes             | —       | Django secret key. The app raises `ImproperlyConfigured` if it is missing.                                 |
| `DJANGO_DEBUG`         | No              | `True`  | Set to `False` in production. Turns on HTTPS redirect, HSTS and secure cookies.                            |
| `DJANGO_ALLOWED_HOSTS` | When `DEBUG=False` | empty   | Comma-separated hostnames the app will serve.                                                              |
| `DATABASE_URL`         | Scalingo only   | —       | Connection string for the PostgreSQL addon. Read only when `STACK` contains `scalingo`.                    |
| `STACK`                | Scalingo only   | —       | Set by Scalingo's buildpack. Its presence activates the Scalingo database and static-file configuration.   |

---

## 🗄️ Database Migrations

Migrations are committed to the repository. Apply them with:

```
python manage.py migrate
```

Only generate new migrations when you change a model:

```
python manage.py makemigrations
python manage.py migrate
```

Never run `makemigrations` on a server; commit the generated files instead. On
Scalingo, `bin/post_deploy.sh` runs `migrate` automatically after each deploy.

---

## ✅ Running the Tests

With the virtual environment active:

```
pytest
```

Or without activating it:

```
.venv/bin/python -m pytest
```

The suite covers models, views, ownership isolation, CSRF and XSS handling,
accessibility attributes, and the production/deployment configuration.

Django's own checks:

```
python manage.py check
# Production checks (requires a non-debug configuration):
DJANGO_DEBUG=False DJANGO_ALLOWED_HOSTS=example.com python manage.py check --deploy
```

---

## 🚀 Deployment (Scalingo)

The repository already contains the files Scalingo needs:

* `Procfile` — starts gunicorn and runs the post-deploy hook.
* `bin/post_deploy.sh` — applies migrations after each deploy.
* `.python-version` — pins the Python build.
* `ll_project/settings.py` — switches to PostgreSQL and WhiteNoise when
  `STACK` contains `scalingo`.

Steps:

1. Create a Scalingo account and install the
   [Scalingo CLI](https://doc.scalingo.com/tools/cli/start), then
   [add your SSH key](https://doc.scalingo.com/platform/getting-started/first-steps#ssh-key-setup).

2. Create the application and add a PostgreSQL addon:

   ```
   scalingo create learning-log
   ```

   Add the database from the dashboard's **Addons** tab, or with
   `scalingo --app learning-log addons-add postgresql <plan>`.

3. Set the production environment variables:

   ```
   scalingo --app learning-log env-set \
     DJANGO_SECRET_KEY=<a freshly generated key> \
     DJANGO_DEBUG=False \
     DJANGO_ALLOWED_HOSTS=learning-log.osc-fr1.scalingo.io
   ```

   Scalingo injects `DATABASE_URL` automatically once the addon exists. If you
   omit `DJANGO_ALLOWED_HOSTS`, the app falls back to accepting any host.

4. Add the Scalingo git remote and deploy. Get the exact remote URL (it depends
   on your app's region) with:

   ```
   scalingo --app learning-log git-show
   ```

   Then:

   ```
   git remote add scalingo <the URL printed above>
   git push scalingo main
   ```

5. The `postdeploy` hook runs `bin/post_deploy.sh`, which applies migrations.
   Create an admin account on the deployed app:

   ```
   scalingo --app learning-log run python manage.py createsuperuser
   ```

6. Confirm the deployed app can register a user, log in, create a topic, add an
   entry, and edit it, and that a second account cannot see the first account's
   data.

---

## ⚠️ Troubleshooting

### `ImproperlyConfigured: DJANGO_SECRET_KEY is not set`

Create `.env` from the template and set the key (see step 4 above).

```
cp .env.example .env
```

### `ModuleNotFoundError: No module named 'X'`

Install the pinned dependencies:

```
pip install -r requirements.txt
```

### Port already in use

```
python manage.py runserver 8001
```

### `python` not found

Use `python3` instead of `python`.

---

## 🔮 Roadmap

* 🔍 Full-text search for topics and entries
* 🏷️ Tagging system
* 📝 Markdown / rich text editor
* 🔌 REST API (Django REST Framework)

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit changes
4. Submit a pull request

---

## 📄 License

This project is open-source and available under the MIT License.

---

## 👨‍💻 Author

Brian Bett

Software Engineer | Python | Django | AI Enthusiast
