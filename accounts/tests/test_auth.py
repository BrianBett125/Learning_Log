"""Authentication journey tests (Phase 6): register, login, and logout.

Phase 6 asks for three things the previous phases did not cover: the login page
must render (it used to raise ``TemplateSyntaxError`` and return 500), register
and logout must behave as the reference does, and every private route must send
an anonymous visitor to the login page rather than leaking content.

Route and redirect targets are asserted against ``settings`` and ``reverse``
rather than hard-coded strings, so a rename in ``ll_project/settings.py`` shows
up here as a failure instead of silently passing.
"""

import re
from urllib.parse import urljoin, urlsplit

import pytest
from django.conf import settings
from django.contrib.auth import SESSION_KEY
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username='brian', password='test-pass-123')


# --- Routes -----------------------------------------------------------------


def test_auth_routes_resolve_to_reference_paths():
    assert reverse('accounts:register') == '/accounts/register/'
    assert reverse('accounts:login') == '/accounts/login/'
    assert reverse('accounts:logout') == '/accounts/logout/'


# --- Login page (login.html) ------------------------------------------------


def test_login_page_renders(client):
    # Regression guard: login.html was truncated mid-tag, so building the page
    # raised TemplateSyntaxError ("Unclosed tag on line 3: 'block'") and the
    # route returned 500. Rendering at all is the proof the tag tree is closed.
    response = client.get(reverse('accounts:login'))
    assert response.status_code == 200


def test_login_page_uses_reference_markup(client):
    html = client.get(reverse('accounts:login')).content.decode()
    assert 'Log in to your account.' in html
    # Reference renders the form via django-bootstrap5, not a bare {{ form.as_div }}.
    assert 'csrfmiddlewaretoken' in html
    assert f'action="{reverse("accounts:login")}"' in html
    # The submit control must be the bootstrap button, not a bare <button>.
    assert re.search(
        r'<button[^>]*type="submit"[^>]*>\s*Log in\s*</button>', html
    ), 'the login form must render a submit button labelled "Log in"'
    assert 'btn btn-primary' in html


# --- Login: valid and invalid credentials -----------------------------------


def test_login_with_valid_credentials_authenticates_and_redirects(client, user):
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': 'test-pass-123'},
    )
    assert response.status_code == 302
    assert response['Location'] == reverse(settings.LOGIN_REDIRECT_URL)
    assert client.session.get(SESSION_KEY) == str(user.pk)


def test_login_with_bad_password_does_not_authenticate(client, user):
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': 'wrong-password-999'},
    )
    assert response.status_code == 200
    assert SESSION_KEY not in client.session
    assert 'Please enter a correct' in response.content.decode()


def test_login_with_unknown_username_does_not_authenticate(client, db):
    response = client.post(
        reverse('accounts:login'),
        {'username': 'nobody', 'password': 'whatever-123'},
    )
    assert response.status_code == 200
    assert SESSION_KEY not in client.session


def test_failed_login_does_not_echo_the_password(client, user):
    secret = 'sup3r-secret-do-not-echo'
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': secret},
    )
    assert secret not in response.content.decode()


def test_login_honours_the_next_parameter(client, user):
    target = reverse('learning_logs:topics')
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': 'test-pass-123', 'next': target},
    )
    assert response.status_code == 302
    assert response['Location'] == target


@pytest.mark.parametrize(
    'next_value',
    [
        'https://evil.example.com/steal',
        'http://evil.example.com/steal',
        '//evil.example.com/steal',  # protocol-relative
        '\\/\\/evil.example.com/steal',  # backslash-smuggled protocol-relative
        '/\\evil.example.com/steal',  # slash-backslash
        '\\\\evil.example.com/steal',  # leading backslash pair
        '\\\\/evil.example.com/steal',
        '///evil.example.com/',  # three slashes
        'javascript:alert(1)',
        'HTTPS://evil.example.com/',
    ],
)
def test_login_rejects_offsite_next_targets(client, user, next_value):
    # Django drops external ``next`` targets (see url_has_allowed_host_and_scheme)
    # so login cannot be used as an open redirect. These shapes all fail the
    # check and fall back to LOGIN_REDIRECT_URL rather than leaking an off-site
    # Location. Each shape is asserted separately so a refactor that reopens one
    # of them fails this test instead of slipping through a single payload.
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': 'test-pass-123', 'next': next_value},
    )
    assert response.status_code == 302
    assert response['Location'] == reverse(settings.LOGIN_REDIRECT_URL)
    assert 'evil.example.com' not in response['Location']


@pytest.mark.parametrize(
    'next_value',
    [
        '\\evil.example.com/steal',  # single backslash: kept as a same-host path
        'https://evil.example.com/steal',
        '//evil.example.com/steal',
        'javascript:alert(1)',
        '/topics/',
        '/topics/7/',
        '',
    ],
)
def test_login_never_redirects_to_another_host(client, user, next_value):
    # The real security property is not "always fall back to /", it is "never
    # send the browser off-site". A single leading backslash survives Django's
    # check as a relative path (Location '%5Cevil.example.com/steal'); resolving
    # it against the login URL must stay on this host. This test pins that
    # invariant for every shape, including the ones Django rejects outright.
    response = client.post(
        reverse('accounts:login'),
        {'username': 'brian', 'password': 'test-pass-123', 'next': next_value},
    )
    assert response.status_code == 302
    resolved = urlsplit(urljoin('http://testserver/accounts/login/', response['Location']))
    assert resolved.netloc == 'testserver', (
        f'next={next_value!r} redirected off-site to {response["Location"]!r}'
    )


# --- Register page and view (register.html) ---------------------------------


def test_register_page_renders_the_form(client):
    response = client.get(reverse('accounts:register'))
    html = response.content.decode()
    assert response.status_code == 200
    assert f'action="{reverse("accounts:register")}"' in html
    assert 'csrfmiddlewaretoken' in html
    assert 'Register' in html


def test_register_is_public(client):
    assert client.get(reverse('accounts:register')).status_code == 200


def test_register_creates_a_user_logs_in_and_redirects(client, db):
    response = client.post(
        reverse('accounts:register'),
        {
            'username': 'newcomer',
            'password1': 'a-strong-pass-456',
            'password2': 'a-strong-pass-456',
        },
    )
    assert response.status_code == 302
    assert response['Location'] == reverse(settings.LOGIN_REDIRECT_URL)
    new_user = User.objects.get(username='newcomer')
    assert client.session.get(SESSION_KEY) == str(new_user.pk)


def test_register_rejects_mismatched_passwords(client, db):
    response = client.post(
        reverse('accounts:register'),
        {
            'username': 'mismatch',
            'password1': 'a-strong-pass-456',
            'password2': 'a-different-pass-789',
        },
    )
    assert response.status_code == 200
    assert not User.objects.filter(username='mismatch').exists()
    assert SESSION_KEY not in client.session
    assert 'didn' in response.content.decode()  # "The two password fields didn't match."


def test_register_rejects_a_short_password(client, db):
    response = client.post(
        reverse('accounts:register'),
        {'username': 'shorty', 'password1': 'abc', 'password2': 'abc'},
    )
    assert response.status_code == 200
    assert not User.objects.filter(username='shorty').exists()


def test_register_rejects_a_duplicate_username(client, user):
    response = client.post(
        reverse('accounts:register'),
        {
            'username': 'brian',
            'password1': 'a-strong-pass-456',
            'password2': 'a-strong-pass-456',
        },
    )
    assert response.status_code == 200
    assert User.objects.filter(username='brian').count() == 1


# --- Password handling ------------------------------------------------------


def test_password_is_stored_hashed_not_in_plaintext(client, db):
    client.post(
        reverse('accounts:register'),
        {
            'username': 'hashed',
            'password1': 'a-strong-pass-456',
            'password2': 'a-strong-pass-456',
        },
    )
    stored = User.objects.get(username='hashed')
    assert stored.password != 'a-strong-pass-456'
    assert stored.password.startswith('pbkdf2_')
    assert stored.check_password('a-strong-pass-456')


# --- Logout -----------------------------------------------------------------


def test_logout_is_post_only(client, user):
    # Django's LogoutView allows POST (and OPTIONS) only; a GET must not end the
    # session, otherwise a stray link or image could log the user out.
    client.force_login(user)
    response = client.get(reverse('accounts:logout'))
    assert response.status_code == 405
    assert client.session.get(SESSION_KEY) == str(user.pk)


def test_logout_via_post_ends_the_session_and_redirects(client, user):
    client.force_login(user)
    response = client.post(reverse('accounts:logout'))
    assert response.status_code == 302
    assert response['Location'] == reverse(settings.LOGOUT_REDIRECT_URL)
    assert SESSION_KEY not in client.session


# --- Private routes require authentication ----------------------------------


@pytest.mark.parametrize(
    'name,args',
    [
        ('learning_logs:topics', []),
        ('learning_logs:topic', [1]),
        ('learning_logs:new_topic', []),
        ('learning_logs:new_entry', [1]),
        ('learning_logs:edit_entry', [1]),
    ],
)
def test_private_routes_redirect_anonymous_visitors_to_login(client, name, args):
    response = client.get(reverse(name, args=args))
    assert response.status_code == 302
    assert reverse('accounts:login') in response['Location']
    assert 'next=' in response['Location']


def test_private_route_redirect_carries_the_intended_destination(client):
    target = reverse('learning_logs:new_topic')
    response = client.get(target)
    assert response['Location'] == f'{reverse("accounts:login")}?next={target}'


def test_authenticated_user_reaches_a_private_route(client, user):
    client.force_login(user)
    assert client.get(reverse('learning_logs:topics')).status_code == 200
