"""CSRF enforcement for the authentication endpoints (Phase 8).

Plan §9 requires that "Forms use CSRF protection". Phase 6 asserted only that
the rendered login and register pages contain a ``csrfmiddlewaretoken`` field.
That proves a token is emitted, not that a request without one is refused, and
Django's test client disables CSRF checks by default: those assertions would
keep passing even if ``CsrfViewMiddleware`` were deleted from ``MIDDLEWARE``.

These tests build a client with ``enforce_csrf_checks=True``, which turns the
checks back on, and pin both directions for every state-changing auth endpoint:

* a POST with no token is answered 403 and leaves no trace (no session key, no
  user row, the session still live for logout), and
* a POST carrying the token the page issued is accepted.

Delete the middleware and the first assertion of each pair fails; drop
``{% csrf_token %}`` from a template and the second fails.
"""

import pytest
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username='alice', password='alice-pass-123')


def _csrf_client():
    """A client that actually enforces CSRF (the default test client does not)."""
    return Client(enforce_csrf_checks=True)


def _issued_token(client, url):
    """Load a page so the CSRF cookie is set, then return the token it issued."""
    response = client.get(url)
    assert response.status_code == 200
    return client.cookies['csrftoken'].value


# --- Login ------------------------------------------------------------------


def test_login_without_a_csrf_token_is_rejected_with_403(user):
    client = _csrf_client()
    response = client.post(
        reverse('accounts:login'),
        {'username': 'alice', 'password': 'alice-pass-123'},
    )
    assert response.status_code == 403
    assert SESSION_KEY not in client.session


def test_login_with_a_forged_csrf_token_is_rejected_with_403(user):
    # A token the server never issued must not be accepted even when the CSRF
    # cookie is present: the posted token is checked against the cookie secret,
    # so a well-formed-but-wrong token is refused (distinct from sending none).
    client = _csrf_client()
    _issued_token(client, reverse('accounts:login'))  # sets the csrftoken cookie
    response = client.post(
        reverse('accounts:login'),
        {
            'username': 'alice',
            'password': 'alice-pass-123',
            'csrfmiddlewaretoken': 'not-a-real-token',
        },
    )
    assert response.status_code == 403
    assert SESSION_KEY not in client.session


def test_login_with_the_issued_csrf_token_succeeds(user):
    client = _csrf_client()
    token = _issued_token(client, reverse('accounts:login'))
    response = client.post(
        reverse('accounts:login'),
        {
            'username': 'alice',
            'password': 'alice-pass-123',
            'csrfmiddlewaretoken': token,
        },
    )
    assert response.status_code == 302
    assert client.session.get(SESSION_KEY) == str(user.pk)


# --- Register ---------------------------------------------------------------


def test_register_without_a_csrf_token_is_rejected_with_403(db):
    client = _csrf_client()
    response = client.post(
        reverse('accounts:register'),
        {
            'username': 'newcomer',
            'password1': 'a-strong-pass-456',
            'password2': 'a-strong-pass-456',
        },
    )
    assert response.status_code == 403
    assert not User.objects.filter(username='newcomer').exists()


def test_register_with_the_issued_csrf_token_creates_the_user(db):
    client = _csrf_client()
    token = _issued_token(client, reverse('accounts:register'))
    response = client.post(
        reverse('accounts:register'),
        {
            'username': 'newcomer',
            'password1': 'a-strong-pass-456',
            'password2': 'a-strong-pass-456',
            'csrfmiddlewaretoken': token,
        },
    )
    assert response.status_code == 302
    assert User.objects.filter(username='newcomer').exists()


# --- Logout -----------------------------------------------------------------


def test_logout_without_a_csrf_token_is_rejected_and_keeps_the_session(user):
    client = _csrf_client()
    client.force_login(user)
    response = client.post(reverse('accounts:logout'))
    assert response.status_code == 403
    assert client.session.get(SESSION_KEY) == str(user.pk)


def test_logout_with_the_issued_csrf_token_ends_the_session(user):
    client = _csrf_client()
    client.force_login(user)
    # The logout control lives in the navbar (base.html) of every authenticated
    # page, so any of them issues the cookie the form posts back.
    token = _issued_token(client, reverse('learning_logs:topics'))
    response = client.post(
        reverse('accounts:logout'),
        {'csrfmiddlewaretoken': token},
    )
    assert response.status_code == 302
    assert SESSION_KEY not in client.session
