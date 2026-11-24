"""CSRF enforcement and output escaping for the learning-log views (Phase 8).

Plan §9 requires that "Forms use CSRF protection" and that "User content is
safely escaped in templates". Neither was tested before this phase: the topic
and entry suites only asserted that a ``csrfmiddlewaretoken`` field appears in a
page (present, not enforced), and no test fed markup through a user-supplied
field to see whether it survives as markup.

Two invariants are pinned here.

* CSRF. With ``enforce_csrf_checks=True`` every state-changing form endpoint
  rejects a token-less POST with 403 and changes nothing, and accepts one
  carrying the token the page issued. Delete ``CsrfViewMiddleware`` and the 403
  cases fail.
* Escaping. Text a user stores (topic titles, entry bodies) is rendered through
  Django's autoescaping, so ``<``, ``>``, ``"`` and ``'`` arrive as entities and
  the raw markup never reaches the browser. Turn autoescaping off and the
  raw-payload assertions fail.
"""

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from learning_logs.models import Entry, Topic


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password='alice-pass-123')


@pytest.fixture
def other_user(db):
    return User.objects.create_user(username='bob', password='bob-pass-123')


@pytest.fixture
def topic(user):
    return Topic.objects.create(text='Chess', owner=user)


@pytest.fixture
def entry(topic):
    return Entry.objects.create(topic=topic, text='Learned about en passant.')


def _csrf_client():
    """A client that actually enforces CSRF (the default test client does not)."""
    return Client(enforce_csrf_checks=True)


def _issued_token(client, url):
    """Load a page so the CSRF cookie is set, then return the token it issued."""
    response = client.get(url)
    assert response.status_code == 200
    return client.cookies['csrftoken'].value


# --- CSRF enforcement on the form endpoints ---------------------------------


def test_new_topic_post_without_a_csrf_token_is_rejected(user):
    client = _csrf_client()
    client.force_login(user)
    response = client.post(reverse('learning_logs:new_topic'), {'text': 'Forged'})
    assert response.status_code == 403
    assert Topic.objects.filter(text='Forged').count() == 0


def test_new_topic_post_with_the_issued_csrf_token_creates_the_topic(user):
    client = _csrf_client()
    client.force_login(user)
    token = _issued_token(client, reverse('learning_logs:new_topic'))
    response = client.post(
        reverse('learning_logs:new_topic'),
        {'text': 'Rust', 'csrfmiddlewaretoken': token},
    )
    assert response.status_code == 302
    assert Topic.objects.filter(text='Rust', owner=user).exists()


def test_new_entry_post_without_a_csrf_token_is_rejected(user, topic):
    client = _csrf_client()
    client.force_login(user)
    response = client.post(
        reverse('learning_logs:new_entry', args=[topic.id]), {'text': 'Forged'}
    )
    assert response.status_code == 403
    assert Entry.objects.filter(text='Forged').count() == 0


def test_new_entry_post_with_the_issued_csrf_token_creates_the_entry(user, topic):
    client = _csrf_client()
    client.force_login(user)
    url = reverse('learning_logs:new_entry', args=[topic.id])
    token = _issued_token(client, url)
    response = client.post(
        url, {'text': 'First move', 'csrfmiddlewaretoken': token}
    )
    assert response.status_code == 302
    assert Entry.objects.filter(text='First move', topic=topic).exists()


def test_edit_entry_post_without_a_csrf_token_is_rejected(user, entry):
    client = _csrf_client()
    client.force_login(user)
    response = client.post(
        reverse('learning_logs:edit_entry', args=[entry.id]), {'text': 'Forged'}
    )
    assert response.status_code == 403
    entry.refresh_from_db()
    assert entry.text == 'Learned about en passant.'


def test_edit_entry_post_with_the_issued_csrf_token_saves_the_change(user, entry):
    client = _csrf_client()
    client.force_login(user)
    url = reverse('learning_logs:edit_entry', args=[entry.id])
    token = _issued_token(client, url)
    response = client.post(
        url, {'text': 'Learned the pin.', 'csrfmiddlewaretoken': token}
    )
    assert response.status_code == 302
    entry.refresh_from_db()
    assert entry.text == 'Learned the pin.'


# --- Output escaping of user content ----------------------------------------

# Each payload is a shape that would execute if it reached the browser raw.
XSS_PAYLOADS = [
    '<script>alert(1)</script>',
    '<img src=x onerror=alert(1)>',
    '"><script>alert(1)</script>',
    '</div><script>alert(1)</script>',
    '<svg/onload=alert(1)>',
]


@pytest.mark.parametrize('payload', XSS_PAYLOADS)
def test_topic_title_is_escaped_on_the_topics_list(client, user, payload):
    Topic.objects.create(text=payload, owner=user)
    client.force_login(user)
    html = client.get(reverse('learning_logs:topics')).content.decode()
    assert payload not in html
    assert escape(payload) in html


@pytest.mark.parametrize('payload', XSS_PAYLOADS)
def test_topic_title_is_escaped_on_the_topic_page(client, user, payload):
    topic = Topic.objects.create(text=payload, owner=user)
    client.force_login(user)
    html = client.get(reverse('learning_logs:topic', args=[topic.id])).content.decode()
    assert payload not in html
    assert escape(payload) in html


@pytest.mark.parametrize('payload', XSS_PAYLOADS)
def test_entry_text_is_escaped_on_the_topic_page(client, user, payload):
    # Entry text renders through |linebreaks, which escapes before it wraps the
    # text in <p>/<br> tags, so the payload must still arrive as entities.
    topic = Topic.objects.create(text='Chess', owner=user)
    Entry.objects.create(topic=topic, text=payload)
    client.force_login(user)
    html = client.get(reverse('learning_logs:topic', args=[topic.id])).content.decode()
    assert payload not in html
    assert escape(payload) in html


def test_stored_text_is_not_re_evaluated_as_template_code(client, user):
    # Django renders context values, it does not re-parse their output, so a
    # stored "{{ 7*7 }}" must appear literally rather than computing 49.
    topic = Topic.objects.create(text='{{ 7*7 }}', owner=user)
    client.force_login(user)
    html = client.get(reverse('learning_logs:topic', args=[topic.id])).content.decode()
    assert '{{ 7*7 }}' in html


def test_other_users_cannot_see_escaped_payloads_they_do_not_own(client, user, other_user):
    # Escaping must not become a way to probe another user's data: a payload
    # stored by alice is invisible to bob, who gets a 404 for her topic.
    topic = Topic.objects.create(text='<script>alert(1)</script>', owner=user)
    client.force_login(other_user)
    assert client.get(reverse('learning_logs:topic', args=[topic.id])).status_code == 404
