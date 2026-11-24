"""Accessible names for the topic and entry text fields (Phase 8).

The reference renders these fields with ``labels = {'text': ''}``, so Django's
``as_div()`` omits the ``<label>`` entirely and axe-core flags the control as
having no accessible name (a CRITICAL ``label`` violation). The agreed fix is
invisible: keep the empty label so nothing moves on screen, and carry the name
in an ``aria-label`` on the widget instead. These tests pin that an accessible
name is present and that no visible label was introduced alongside it (which
would move the layout and break the byte-identical parity Phase 7 pinned).
"""

import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from learning_logs.models import Entry, Topic


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password='alice-pass-123')


@pytest.fixture
def topic(user):
    return Topic.objects.create(text='Chess', owner=user)


@pytest.fixture
def entry(topic):
    return Entry.objects.create(topic=topic, text='Learned about en passant.')


def _control(html):
    """Return the opening tag of the rendered text control (input or textarea)."""
    match = re.search(r'<(?:input|textarea)\b[^>]*\bid="id_text"[^>]*>', html)
    assert match, 'the page did not render a control with id="id_text"'
    return match.group(0)


def test_topic_field_is_named_without_a_visible_label(client, user):
    client.force_login(user)
    html = client.get(reverse('learning_logs:new_topic')).content.decode()
    assert 'aria-label="Topic text"' in _control(html)
    assert 'for="id_text"' not in html


def test_new_entry_field_is_named_without_a_visible_label(client, user, topic):
    client.force_login(user)
    html = client.get(
        reverse('learning_logs:new_entry', args=[topic.id])
    ).content.decode()
    assert 'aria-label="Entry text"' in _control(html)
    assert 'for="id_text"' not in html


def test_edit_entry_field_is_named_without_a_visible_label(client, user, entry):
    client.force_login(user)
    html = client.get(
        reverse('learning_logs:edit_entry', args=[entry.id])
    ).content.decode()
    assert 'aria-label="Entry text"' in _control(html)
    assert 'for="id_text"' not in html
