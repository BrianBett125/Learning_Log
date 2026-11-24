"""Public home page and shared-layout tests (Phase 3).

The home page is the only public page in ``learning_logs``; every other page
sits behind ``@login_required``. These tests cover what Phase 3 asks for: the
hero rendered by ``index.html``, the links between pages, responsive Bootstrap
markup, and the authentication-aware navigation in the shared ``base.html``.

Navigation assertions are scoped to the ``<nav>`` element: the home page hero
carries a "Register" call to action in every auth state, so searching the whole
document for the register URL would not test the navbar at all.
"""

import re

import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.fixture
def user(db):
    return User.objects.create_user(username='brian', password='test-pass-123')


def home_html(client):
    """Return the decoded HTML of the public home page."""
    return client.get(reverse('learning_logs:index')).content.decode()


def navbar(html):
    """Return just the ``<nav>`` element from a rendered page."""
    return html[html.index('<nav'):html.index('</nav>')]


# --- Links resolve to the reference routes ---------------------------------


def test_public_route_names_resolve_to_reference_paths():
    assert reverse('learning_logs:index') == '/'
    assert reverse('learning_logs:topics') == '/topics/'
    assert reverse('accounts:register') == '/accounts/register/'
    assert reverse('accounts:login') == '/accounts/login/'
    assert reverse('accounts:logout') == '/accounts/logout/'


# --- Home page (index.html) ------------------------------------------------


def test_home_page_is_public(client):
    assert client.get(reverse('learning_logs:index')).status_code == 200


def test_home_page_renders_index_via_base(client):
    response = client.get(reverse('learning_logs:index'))
    names = {template.name for template in response.templates if template.name}
    assert 'learning_logs/index.html' in names
    assert 'learning_logs/base.html' in names


def test_home_page_renders_maarifa_hero(client):
    html = home_html(client)
    assert '<title>Maarifa | Learn. Reflect. Understand. Grow.</title>' in html
    assert '<h1>MAARIFA</h1>' in html
    assert 'Learn. Reflect. Understand. Grow.' in html
    assert 'Your personal universe of knowledge.' in html
    assert 'class="lead mx-auto mb-4"' in html
    assert "Organize the topics you're exploring" in html
    assert 'btn btn-primary btn-lg' in html
    assert 'learning_logs/maarifa-mark.svg' in html
    assert 'learning_logs/maarifa.css' in html


def test_home_page_call_to_action_points_at_registration(client):
    html = home_html(client)
    assert f'href="{reverse("accounts:register")}">Start learning &raquo;</a>' in html


# --- Responsive layout -----------------------------------------------------


def test_layout_declares_responsive_viewport_and_navbar(client):
    html = home_html(client)
    assert 'name="viewport"' in html
    assert 'width=device-width' in html
    assert 'navbar-expand-md' in navbar(html)


def test_navbar_links_home_and_topics(client):
    nav = navbar(home_html(client))
    assert f'href="{reverse("learning_logs:index")}"' in nav
    assert f'href="{reverse("learning_logs:topics")}"' in nav
    assert 'Maarifa' in nav


# --- Shared navigation: anonymous visitor ----------------------------------


def test_navbar_shows_register_and_login_for_anonymous_visitor(client):
    nav = navbar(home_html(client))
    assert f'href="{reverse("accounts:register")}"' in nav
    assert f'href="{reverse("accounts:login")}"' in nav
    assert 'Register' in nav
    assert 'Log in' in nav
    assert 'Hello,' not in nav
    assert 'Log out' not in nav


# --- Shared navigation: authenticated user ---------------------------------


def test_navbar_shows_username_and_hides_auth_links_when_logged_in(client, user):
    client.force_login(user)
    nav = navbar(home_html(client))
    assert 'Hello, brian.' in nav
    assert 'Register' not in nav
    assert 'Log in' not in nav
    assert reverse('accounts:register') not in nav
    assert reverse('accounts:login') not in nav


def test_logout_control_is_a_post_form_with_csrf(client, user):
    client.force_login(user)
    nav = navbar(home_html(client))
    logout_url = re.escape(reverse('accounts:logout'))
    assert re.search(
        rf'<form[^>]*action="{logout_url}"[^>]*method=[\'"]post[\'"]', nav
    ), 'logout must be submitted with POST, not a plain link'
    assert 'csrfmiddlewaretoken' in nav


# --- Authentication-aware navigation ---------------------------------------


def test_topics_nav_link_leads_to_a_login_protected_route(client):
    response = client.get(reverse('learning_logs:topics'))
    assert response.status_code == 302
    assert reverse('accounts:login') in response['Location']
