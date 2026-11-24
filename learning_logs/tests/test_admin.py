"""Admin registration tests for the learning_logs models."""

from django.contrib import admin

from learning_logs.models import Entry, Topic


def test_topic_is_registered_in_admin():
    assert Topic in admin.site._registry


def test_entry_is_registered_in_admin():
    assert Entry in admin.site._registry
