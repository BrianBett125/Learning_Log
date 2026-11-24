#!/bin/sh

# Runs after each deploy, before the new container takes traffic.
# `makemigrations` is a local, committed step; only `migrate` runs here.
python manage.py migrate
