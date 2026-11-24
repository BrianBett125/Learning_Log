"""Topic workflow tests (Phase 4): list, detail, and creation.

Phase 4 requires every topic query to be scoped to the authenticated user, with
authorization enforced server side rather than by hiding links.

The reference implementation raised ``Http404`` after an unscoped
``Topic.objects.get``. The plan (§4.3, §4.5, §7) requires ownership-scoped
lookups and a deliberate 404, so ``topic`` uses
``get_object_or_404(Topic, id=..., owner=request.user)``. That is a deliberate,
documented divergence: another user's topic and a nonexistent id both return
404, so the view never confirms that a private resource exists, and a stale id
can no longer produce a 500.
"""

from datetime import datetime, timezone as dt_timezone

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


def test_topic_detail_route_has_a_trailing_slash():
    # Regression guard: the route used to be 'topics/<int:topic_id>' (no slash),
    # which diverged from the reference and from every reverse() call.
    assert reverse('learning_logs:topic', args=[7]) == '/topics/7/'


@pytest.mark.parametrize(
    'name,args',
    [
        ('learning_logs:topics', []),
        ('learning_logs:topic', [1]),
        ('learning_logs:new_topic', []),
    ],
)
def test_topic_routes_require_login(client, name, args):
    response = client.get(reverse(name, args=args))
    assert response.status_code == 302
    assert reverse('accounts:login') in response['Location']


# --- Topic list (topics.html) -----------------------------------------------


def test_topics_list_shows_only_the_current_users_topics(client, user, topic, other_topic):
    client.force_login(user)
    html = client.get(reverse('learning_logs:topics')).content.decode()
    assert topic.text in html
    assert other_topic.text not in html


def test_topics_list_links_to_each_topic_detail(client, user, topic):
    client.force_login(user)
    html = client.get(reverse('learning_logs:topics')).content.decode()
    assert f'href="{reverse("learning_logs:topic", args=[topic.id])}"' in html


def test_topics_list_shows_reference_empty_state(client, user):
    client.force_login(user)
    html = client.get(reverse('learning_logs:topics')).content.decode()
    assert 'No topics have been added yet.' in html
    assert f'href="{reverse("learning_logs:new_topic")}"' in html


def test_topics_list_orders_oldest_first(client, user):
    first = Topic.objects.create(text='First', owner=user)
    second = Topic.objects.create(text='Second', owner=user)
    # Force a definite order so the assertion does not depend on clock resolution.
    Topic.objects.filter(pk=first.pk).update(
        date_added=datetime(2020, 1, 1, tzinfo=dt_timezone.utc)
    )
    Topic.objects.filter(pk=second.pk).update(
        date_added=datetime(2021, 1, 1, tzinfo=dt_timezone.utc)
    )
    client.force_login(user)
    html = client.get(reverse('learning_logs:topics')).content.decode()
    assert html.index('First') < html.index('Second')


# --- Topic detail (topic.html) ----------------------------------------------


def test_owner_sees_the_topic_heading_and_its_entries(client, user, topic):
    Entry.objects.create(topic=topic, text='Learned about openings.')
    client.force_login(user)
    response = client.get(reverse('learning_logs:topic', args=[topic.id]))
    html = response.content.decode()
    assert response.status_code == 200
    assert topic.text in html
    assert 'Learned about openings.' in html
    # Asserted by URL name so Phase 5's route rename cannot break this test.
    assert reverse('learning_logs:new_entry', args=[topic.id]) in html


def test_topic_detail_shows_reference_empty_state(client, user, topic):
    client.force_login(user)
    html = client.get(reverse('learning_logs:topic', args=[topic.id])).content.decode()
    assert 'There are no entries for this topic yet.' in html


def test_user_cannot_open_another_users_topic(client, user, other_topic):
    client.force_login(user)
    response = client.get(reverse('learning_logs:topic', args=[other_topic.id]))
    assert response.status_code == 404
    assert other_topic.text.encode() not in response.content


def test_unknown_topic_id_returns_404_not_500(client, user):
    client.force_login(user)
    response = client.get(reverse('learning_logs:topic', args=[999999]))
    assert response.status_code == 404


# --- New topic (new_topic.html) ---------------------------------------------


def test_new_topic_page_renders_the_form(client, user):
    client.force_login(user)
    response = client.get(reverse('learning_logs:new_topic'))
    html = response.content.decode()
    assert response.status_code == 200
    assert 'Add a new topic:' in html
    assert 'csrfmiddlewaretoken' in html


def test_new_topic_post_creates_a_topic_owned_by_the_user(client, user):
    client.force_login(user)
    response = client.post(reverse('learning_logs:new_topic'), {'text': 'Astronomy'})
    assert response.status_code == 302
    assert response['Location'] == reverse('learning_logs:topics')
    assert Topic.objects.get(text='Astronomy').owner == user


def test_new_topic_requires_text(client, user):
    client.force_login(user)
    response = client.post(reverse('learning_logs:new_topic'), {'text': ''})
    assert response.status_code == 200
    assert Topic.objects.count() == 0
    assert 'This field is required' in response.content.decode()


def test_new_topic_cannot_assign_a_different_owner(client, user, other_user):
    # ``owner`` is not a form field, so a crafted POST cannot reassign the topic.
    client.force_login(user)
    client.post(
        reverse('learning_logs:new_topic'),
        {'text': 'Sneaky', 'owner': other_user.id},
    )
    assert Topic.objects.get(text='Sneaky').owner == user
