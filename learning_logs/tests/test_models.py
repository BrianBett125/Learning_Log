"""Model tests: relationships, required fields, and string representations."""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from learning_logs.models import Entry, Topic


@pytest.fixture
def user(db):
    """A persisted user that can own topics."""
    return User.objects.create_user(username='brian', password='test-pass-123')


@pytest.fixture
def topic(user):
    """A persisted topic owned by ``user``."""
    return Topic.objects.create(text='Python Crash Course', owner=user)


# --- Topic -----------------------------------------------------------------


def test_topic_str_returns_text(topic):
    assert str(topic) == 'Python Crash Course'


def test_topic_belongs_to_owner(topic, user):
    assert topic.owner == user
    assert topic in user.topic_set.all()


def test_topic_requires_text(user):
    topic = Topic(text='', owner=user)
    with pytest.raises(ValidationError):
        topic.full_clean()


def test_topic_requires_owner():
    topic = Topic(text='No owner')
    with pytest.raises(ValidationError):
        topic.full_clean()


def test_topic_date_added_is_automatic(topic):
    assert topic.date_added is not None


# --- Entry -----------------------------------------------------------------


def test_entry_str_truncates_long_text_to_50_chars(topic):
    entry = Entry.objects.create(topic=topic, text='x' * 80)
    assert str(entry) == f"{'x' * 50}..."


def test_entry_str_appends_ellipsis_to_short_text(topic):
    entry = Entry.objects.create(topic=topic, text='short note')
    assert str(entry) == 'short note...'


def test_entry_str_does_not_split_text_at_exactly_50_chars(topic):
    entry = Entry.objects.create(topic=topic, text='y' * 50)
    assert str(entry) == f"{'y' * 50}..."


def test_entry_str_truncates_at_51_chars(topic):
    entry = Entry.objects.create(topic=topic, text='y' * 51)
    assert str(entry) == f"{'y' * 50}..."


def test_entry_str_is_defined_on_the_class():
    # Regression guard. __str__ used to live inside ``class Meta``, so Entry had
    # no working __str__ and str(entry) fell back to object.__repr__.
    assert '__str__' in Entry.__dict__


def test_entry_belongs_to_topic(topic):
    entry = Entry.objects.create(topic=topic, text='Learned about models.')
    assert entry.topic == topic
    assert entry in topic.entry_set.all()


def test_entry_requires_text(topic):
    entry = Entry(topic=topic, text='')
    with pytest.raises(ValidationError):
        entry.full_clean()


def test_entry_verbose_name_plural_is_entries():
    assert Entry._meta.verbose_name_plural == 'entries'


def test_entry_date_added_is_automatic(topic):
    entry = Entry.objects.create(topic=topic, text='Timestamped.')
    assert entry.date_added is not None


# --- Cascade deletes -------------------------------------------------------


def test_deleting_topic_cascades_to_entries(topic):
    Entry.objects.create(topic=topic, text='One')
    Entry.objects.create(topic=topic, text='Two')
    topic.delete()
    assert Entry.objects.count() == 0


def test_deleting_user_cascades_to_topics(user, topic):
    user.delete()
    assert Topic.objects.count() == 0
