# Learning Log

**Learning Log** is a personal web application that allows users to track and document their learning journeys. Built with **Python** and **Django**, this app enables users to create topics they're interested in and log entries as they explore each topic further.

## 🚧 Project Status

This project is currently in active development. Core features are being implemented and refined.

## 🧠 Features

- User authentication: registration, login, and logout.
- Create and manage **learning topics**.
- Add **journal entries** for each topic to document what you’re learning.
- Edit and view past entries.
- Clean, user-friendly interface.

## 🔧 Tech Stack

- **Backend:** Python, Django
- **Frontend:** HTML, CSS (with potential for future enhancements using Bootstrap or JavaScript frameworks)
- **Database:** SQLite (default for Django, subject to change)
- **Version Control:** Git

## 🗂️ Project Structure

```bash
learning_log/
│
├── ll_project/           # Project configuration and settings
│
├── learning_logs/        # Main app containing models, views, URLs, templates
│
├── templates/            # HTML templates
│
├── static/               # Static files (CSS, images, JS)
│
├── db.sqlite3            # SQLite database (for development)
│
└── manage.py             # Django management script

