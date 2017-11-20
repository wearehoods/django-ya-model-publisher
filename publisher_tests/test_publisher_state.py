
import datetime
import logging
import time

from django import test
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from django_tools.unittest_utils.user import create_user
from publisher_test_project.publisher_test_app.models import PublisherTestModel

from publisher.models import PublisherStateModel

log = logging.getLogger(__name__)
User = get_user_model()


class PublisherStateTests(test.TestCase):

    @classmethod
    def setUpTestData(cls):
        super(PublisherStateTests, cls).setUpTestData()

        cls.draft = PublisherTestModel.objects.create(title="publisher test")

        cls.user_no_permissions = User.objects.create(username="user_with_no_permissions")

        def create_test_user(username, permission):
            content_type = ContentType.objects.get_for_model(PublisherStateModel)
            permission = Permission.objects.get(content_type=content_type, codename=permission)

            group = Group.objects.create(name="%s_group" % username)
            group.permissions.add(permission)

            user = create_user(
                username=username,
                password="unittest",
                groups=(group,),
            )
            return user

        cls.ask_permission_user = create_test_user(
            username="ask_permission_user",
            permission="ask_publisher_request",
        )
        cls.reply_permission_user = create_test_user(
            username="reply_permission_user",
            permission="reply_publisher_request",
        )

    def test_environment(self):
        all_permissions = [
            "%s.%s" % (entry.content_type, entry.codename)
            for entry in Permission.objects.all()
        ]
        self.assertIn("publisher test model.can_publish", all_permissions)

        self.assertIn("publisher state model.direct_publisher", all_permissions)
        self.assertIn("publisher state model.ask_publisher_request", all_permissions)
        self.assertIn("publisher state model.reply_publisher_request", all_permissions)

        self.assertTrue(
            self.ask_permission_user.has_perm("publisher.ask_publisher_request")
        )

        permissions = self.ask_permission_user.get_all_permissions()
        self.assertIn("publisher.ask_publisher_request", permissions)

    def test_no_ask_request_permission(self):
        self.assertRaises(
            PermissionDenied,
            PublisherStateModel.objects.request_publishing,
            user=self.user_no_permissions,
            publisher_instance=self.draft,
        )

    def assert_timestamp(self, timestamp, diff=1):
        now = timezone.now()
        self.assertGreaterEqual(timestamp, now - datetime.timedelta(seconds=diff))
        self.assertLessEqual(timestamp, now + datetime.timedelta(seconds=diff))

    def test_ask_request(self):
        self.draft.title = "test_ask_request"
        self.draft.save()
        self.assertTrue(self.draft.is_dirty)
        self.assertEqual(PublisherTestModel.objects.all().count(), 1)

        self.assertEqual(PublisherStateModel.objects.all().count(), 0)
        state_instance = PublisherStateModel.objects.request_publishing(
            user=self.ask_permission_user,
            publisher_instance=self.draft,
            note="test ask request",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)
        self.assertIsInstance(state_instance, PublisherStateModel)

        state_instance = PublisherStateModel.objects.get(pk=state_instance.pk)

        self.assertEqual(str(state_instance.state_name), "request")
        self.assertEqual(str(state_instance.action_name), "publish")

        self.assertTrue(state_instance.is_open)

        self.assertEqual(state_instance.publisher_instance, self.draft)
        self.assertTrue(state_instance.publisher_instance.is_draft)

        self.assert_timestamp(state_instance.request_timestamp)
        self.assertEqual(state_instance.request_user, self.ask_permission_user)
        self.assertEqual(state_instance.request_note, "test ask request")

        self.assertEqual(state_instance.response_timestamp, None)
        self.assertEqual(state_instance.response_user, None)
        self.assertEqual(state_instance.response_note, None)

    def test_accept_publish_request(self):
        self.draft.title = "test_accept_publish_request"
        self.draft.save()
        self.assertTrue(self.draft.is_dirty)
        self.assertEqual(PublisherTestModel.objects.all().count(), 1)

        self.assertEqual(PublisherStateModel.objects.all().count(), 0)
        state_instance = PublisherStateModel.objects.request_publishing(
            user=self.ask_permission_user,
            publisher_instance=self.draft,
            note="test_accept_publish_request request",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)

        time.sleep(0.01) # assert request timestamp < response timestamp ;)

        state_instance.accept(
            response_user=self.reply_permission_user,
            response_note="test_accept_publish_request response",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)
        self.assertEqual(PublisherTestModel.objects.all().count(), 2)
        self.assertIsInstance(state_instance, PublisherStateModel)

        state_instance = PublisherStateModel.objects.get(pk=state_instance.pk)

        instance = state_instance.publisher_instance
        self.assertTrue(instance.is_published)

        draft = PublisherTestModel.objects.get(pk=self.draft.pk)
        self.assertEqual(instance, draft.publisher_linked)

        self.assertEqual(str(state_instance.state_name), "accepted")
        self.assertEqual(str(state_instance.action_name), "publish")

        self.assertFalse(state_instance.is_open)

        self.assert_timestamp(state_instance.request_timestamp)
        self.assertLessEqual(
            state_instance.request_timestamp,
            state_instance.response_timestamp,
        )
        self.assertEqual(state_instance.request_user, self.ask_permission_user)
        self.assertEqual(state_instance.request_note, "test_accept_publish_request request")

        self.assert_timestamp(state_instance.response_timestamp)
        self.assertEqual(state_instance.response_user, self.reply_permission_user)
        self.assertEqual(state_instance.response_note, "test_accept_publish_request response")

    def test_reject_request(self):
        self.draft.title = "test_reject_request"
        self.draft.save()
        self.assertTrue(self.draft.is_dirty)
        self.assertEqual(PublisherTestModel.objects.all().count(), 1)

        self.assertEqual(PublisherStateModel.objects.all().count(), 0)
        state_instance = PublisherStateModel.objects.request_publishing(
            user=self.ask_permission_user,
            publisher_instance=self.draft,
            note="test_reject_request request",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)
        self.assertIsInstance(state_instance, PublisherStateModel)

        time.sleep(0.01) # assert request timestamp < response timestamp ;)

        print(state_instance.reject)
        state_instance.reject(
            response_user=self.reply_permission_user,
            response_note="test_reject_request response",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)

        state_instance = PublisherStateModel.objects.get(pk=state_instance.pk)

        # assert was not published:
        self.assertEqual(PublisherTestModel.objects.all().count(), 1)
        self.assertFalse(state_instance.publisher_instance.is_published)

        draft = PublisherTestModel.objects.get(pk=self.draft.pk)
        self.assertEqual(state_instance.publisher_instance, draft)

        self.assertEqual(str(state_instance.state_name), "rejected")
        self.assertEqual(str(state_instance.action_name), "publish")

        self.assertFalse(state_instance.is_open)

        self.assert_timestamp(state_instance.request_timestamp)
        self.assertLessEqual(
            state_instance.request_timestamp,
            state_instance.response_timestamp,
        )
        self.assertEqual(state_instance.request_user, self.ask_permission_user)
        self.assertEqual(state_instance.request_note, "test_reject_request request")

        self.assert_timestamp(state_instance.response_timestamp)
        self.assertEqual(state_instance.response_user, self.reply_permission_user)
        self.assertEqual(state_instance.response_note, "test_reject_request response")

    def test_accept_unpublish_request(self):
        self.draft.title = "test_accept_unpublish_request"
        self.draft.save()
        publish_instance = self.draft.publish()
        self.assertTrue(publish_instance.is_published)
        self.assertFalse(publish_instance.is_dirty)
        self.assertFalse(self.draft.is_dirty)
        self.assertEqual(PublisherTestModel.objects.all().count(), 2)

        self.assertEqual(PublisherStateModel.objects.all().count(), 0)
        state_instance = PublisherStateModel.objects.request_unpublishing(
            user=self.ask_permission_user,
            publisher_instance=publish_instance,
            note="test_accept_unpublish_request request",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)

        time.sleep(0.01) # assert request timestamp < response timestamp ;)

        state_instance.accept(
            response_user=self.reply_permission_user,
            response_note="test_accept_unpublish_request response",
        )
        self.assertEqual(PublisherStateModel.objects.all().count(), 1)
        self.assertEqual(PublisherTestModel.objects.all().count(), 1)
        self.assertIsInstance(state_instance, PublisherStateModel)

        state_instance = PublisherStateModel.objects.get(pk=state_instance.pk)

        instance = state_instance.publisher_instance
        self.assertTrue(instance.is_draft)

        draft = PublisherTestModel.objects.get(pk=self.draft.pk)
        self.assertEqual(draft.publisher_linked, None)

        self.assertEqual(str(state_instance.state_name), "accepted")
        self.assertEqual(str(state_instance.action_name), "unpublish")

        self.assertFalse(state_instance.is_open)

        self.assert_timestamp(state_instance.request_timestamp)
        self.assertLessEqual(
            state_instance.request_timestamp,
            state_instance.response_timestamp,
        )
        self.assertEqual(state_instance.request_user, self.ask_permission_user)
        self.assertEqual(state_instance.request_note, "test_accept_unpublish_request request")

        self.assert_timestamp(state_instance.response_timestamp)
        self.assertEqual(state_instance.response_user, self.reply_permission_user)
        self.assertEqual(state_instance.response_note, "test_accept_unpublish_request response")
