"""Entry workflow tests (Phase 5): create and edit, with parent-topic ownership.

Phase 5 closes the authorization hole the original project shipped: the
reference ``new_entry`` view looked a topic up with an unscoped
``Topic.objects.get(id=topic_id)``, so any logged-in user could read and write
entries under any other user's topic by URL. Plan §4.4/§4.5/§9 require the parent
topic to belong to the current user on every entry path.

Both entry views now scope their lookup through the owner (and use
``get_object_or_404``), so a cross-user id and a nonexistent id both return 404
rather than serving data or raising a 500.
"""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

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
def other_topic(other_user):
    return Topic.objects.create(text='Rockets', owner=other_user)


# --- Routes -----------------------------------------------------------------


def test_entry_route_names_resolve_to_reference_paths():
    # Regression: new_entry used to be bound to 'new_topic/<int:topic_id>/'.
    assert reverse('learning_logs:new_entry', args=[7]) == '/new_entry/7/'
    assert reverse('learning_logs:edit_entry', args=[7]) == '/edit_entry/7/'


@pytest.mark.parametrize(
    'name,args',
    [
        ('learning_logs:new_entry', [1]),
        ('learning_logs:edit_entry', [1]),
    ],
)
def test_entry_routes_require_login(client, name, args):
    response = client.get(reverse(name, args=args))
    assert response.status_code == 302
    assert reverse('accounts:login') in response['Location']


# --- New entry (new_entry.html) ---------------------------------------------


def test_new_entry_page_links_back_to_the_topic(client, user, topic):
    client.force_login(user)
    response = client.get(reverse('learning_logs:new_entry', args=[topic.id]))
    html = response.content.decode()
    assert response.status_code == 200
    assert 'Add a new entry:' in html
    assert f'href="{reverse("learning_logs:topic", args=[topic.id])}"' in html
    assert 'csrfmiddlewaretoken' in html


def test_new_entry_page_starts_with_the_doctype(client, user, topic):
    # Regression: a stray 'i' used to precede {% extends %} and leak into the body.
    client.force_login(user)
    html = client.get(reverse('learning_logs:new_entry', args=[topic.id])).content.decode()
    assert html.startswith('<!doctype html>')


def test_new_entry_post_creates_an_entry_in_the_topic(client, user, topic):
    client.force_login(user)
    response = client.post(
        reverse('learning_logs:new_entry', args=[topic.id]),
        {'text': 'Learned about en passant.'},
    )
    assert response.status_code == 302
    assert response['Location'] == reverse('learning_logs:topic', args=[topic.id])
    assert Entry.objects.get(text='Learned about en passant.').topic == topic


def test_new_entry_requires_text(client, user, topic):
    client.force_login(user)
    response = client.post(reverse('learning_logs:new_entry', args=[topic.id]), {'text': ''})
    assert response.status_code == 200
    assert Entry.objects.count() == 0
    assert 'This field is required' in response.content.decode()


def test_new_entry_appears_on_the_topic_page(client, user, topic):
    client.force_login(user)
    client.post(reverse('learning_logs:new_entry', args=[topic.id]), {'text': 'Visible entry.'})
    html = client.get(reverse('learning_logs:topic', args=[topic.id])).content.decode()
    assert 'Visible entry.' in html


def test_user_cannot_open_another_users_new_entry_form(client, user, other_topic):
    client.force_login(user)
    response = client.get(reverse('learning_logs:new_entry', args=[other_topic.id]))
    assert response.status_code == 404
    assert other_topic.text.encode() not in response.content


def test_user_cannot_post_an_entry_into_another_users_topic(client, user, other_topic):
    # The original IDOR: /new_entry/<other_id>/ let any user write into any topic.
    client.force_login(user)
    response = client.post(
        reverse('learning_logs:new_entry', args=[other_topic.id]),
        {'text': 'Injected'},
    )
    assert response.status_code == 404
    assert Entry.objects.filter(text='Injected').count() == 0
    assert other_topic.entry_set.count() == 0


def test_new_entry_with_an_unknown_topic_returns_404_not_500(client, user):
    client.force_login(user)
    response = client.get(reverse('learning_logs:new_entry', args=[999999]))
    assert response.status_code == 404


# --- Edit entry (edit_entry.html) -------------------------------------------


def test_owner_can_open_the_edit_form_prefilled(client, user, topic):
    entry = Entry.objects.create(topic=topic, text='Original text.')
    client.force_login(user)
    response = client.get(reverse('learning_logs:edit_entry', args=[entry.id]))
    html = response.content.decode()
    assert response.status_code == 200
    assert 'Edit entry:' in html
    assert 'Original text.' in html
    assert f'href="{reverse("learning_logs:topic", args=[topic.id])}"' in html


def test_edit_entry_post_updates_the_entry(client, user, topic):
    entry = Entry.objects.create(topic=topic, text='Before.')
    client.force_login(user)
    response = client.post(reverse('learning_logs:edit_entry', args=[entry.id]), {'text': 'After.'})
    assert response.status_code == 302
    assert response['Location'] == reverse('learning_logs:topic', args=[topic.id])
    entry.refresh_from_db()
    assert entry.text == 'After.'


def test_edit_entry_requires_text(client, user, topic):
    entry = Entry.objects.create(topic=topic, text='Keep me.')
    client.force_login(user)
    response = client.post(reverse('learning_logs:edit_entry', args=[entry.id]), {'text': ''})
    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.text == 'Keep me.'


def test_edit_entry_cannot_reassign_the_topic(client, user, topic, other_topic):
    entry = Entry.objects.create(topic=topic, text='Mine.')
    client.force_login(user)
    client.post(
        reverse('learning_logs:edit_entry', args=[entry.id]),
        {'text': 'Still mine.', 'topic': other_topic.id},
    )
    entry.refresh_from_db()
    assert entry.topic == topic
    assert entry.text == 'Still mine.'


def test_user_cannot_open_another_users_entry_for_edit(client, user, other_topic):
    other_entry = Entry.objects.create(topic=other_topic, text='Bob secret.')
    client.force_login(user)
    response = client.get(reverse('learning_logs:edit_entry', args=[other_entry.id]))
    assert response.status_code == 404
    assert b'Bob secret.' not in response.content


def test_user_cannot_post_to_another_users_entry(client, user, other_topic):
    other_entry = Entry.objects.create(topic=other_topic, text='Bob secret.')
    client.force_login(user)
    response = client.post(
        reverse('learning_logs:edit_entry', args=[other_entry.id]),
        {'text': 'Hijacked'},
    )
    assert response.status_code == 404
    other_entry.refresh_from_db()
    assert other_entry.text == 'Bob secret.'


def test_edit_entry_with_an_unknown_id_returns_404_not_500(client, user):
    client.force_login(user)
    response = client.get(reverse('learning_logs:edit_entry', args=[999999]))
    assert response.status_code == 404
