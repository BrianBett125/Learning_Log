# 📘 Learning Log

Learning Log is a Django-based web application that enables users to track their learning journey by organizing topics and recording structured entries over time.

---

## 🚀 Overview

This application allows users to:

* Create learning topics
* Log entries under each topic
* Track progress over time
* Manage and edit previous learning records

It is designed as a minimal but extensible system that can evolve into a full learning management or knowledge-tracking platform.

---

## 🧠 Core Features

* 🔐 User authentication (register, login, logout)
* 📂 Topic management (create, update, delete)
* 📝 Entry logging per topic
* ✏️ Edit and review past entries
* 🎨 Simple UI (Bootstrap-enabled)

---

## 🏗️ Tech Stack

| Layer     | Technology           |
| --------- | -------------------- |
| Backend   | Python, Django       |
| Frontend  | HTML, CSS, Bootstrap |
| Database  | SQLite (default)     |
| Dev Tools | Git, Virtualenv      |

---

## 📁 Project Structure

```
learning_log/
│
├── ll_project/        # Django project settings
├── learning_logs/     # Core application (models, views, urls)
├── templates/         # HTML templates
├── static/            # CSS, JS, images
├── manage.py
└── requirements.txt
```

---

## ⚙️ Setup & Installation

### 1. Clone Repository

```
git clone https://github.com/<your-username>/learning_log.git
cd learning_log
```

---

### 2. Create Virtual Environment

```
python3 -m venv venv
source venv/bin/activate
```

Windows:

```
venv\Scripts\activate
```

---

### 3. Install Dependencies

```
pip install --upgrade pip
pip install -r requirements.txt
```

> If you encounter missing packages:

```
pip install django django-bootstrap5
```

---

### 4. Apply Migrations

```
python manage.py migrate
```

---

### 5. Create Superuser (Optional)

```
python manage.py createsuperuser
```

---

### 6. Run Development Server

```
python manage.py runserver
```

Open in browser:

```
http://127.0.0.1:8000/
```

Admin panel:

```
http://127.0.0.1:8000/admin/
```

---

## ⚠️ Troubleshooting

### ModuleNotFoundError

```
ModuleNotFoundError: No module named 'X'
```

Fix:

```
pip install X
```

---

### Port Already in Use

```
python manage.py runserver 8001
```

---

### Python Not Found

```
python3 manage.py runserver
```

---

## 🔮 Roadmap

* 🔍 Full-text search for topics and entries
* 🏷️ Tagging system
* 📝 Markdown / rich text editor
* 🔌 REST API (Django REST Framework)
* 🎨 Improved UI/UX (responsive design)
* 🧪 Unit & integration testing

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

---
