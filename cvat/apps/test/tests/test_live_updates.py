# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import asyncio
import json
from functools import partial
from unittest import mock

import fakeredis
from asgiref.sync import sync_to_async
from django.conf import settings
from django.test import Client, TransactionTestCase
from rest_framework.test import APITestCase

from cvat.apps.engine.models import Label
from cvat.apps.test import live_updates
from cvat.apps.test.live_updates import annotation_counts_websocket

from .utils import add_shape, create_task, create_user, populate_hand_checked_annotations, task_jobs


class TaskChangeNotificationTest(APITestCase):
    def setUp(self):
        self.owner = create_user("owner")
        self.task = create_task(self.owner)
        self.car = Label.objects.get(task=self.task, name="car")

    def test_saving_annotations_in_the_editor_publishes_a_task_change(self):
        first_job, _, _ = task_jobs(self.task)
        shape = {
            "type": "rectangle",
            "frame": 0,
            "label_id": self.car.id,
            "points": [0, 0, 5, 5],
            "attributes": [],
        }
        self.client.force_login(self.owner)

        with (
            mock.patch("cvat.apps.test.signals.publish_task_changed") as publish,
            self.captureOnCommitCallbacks(execute=True),
        ):
            response = self.client.patch(
                f"/api/jobs/{first_job.id}/annotations?action=create",
                {"shapes": [shape]},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        publish.assert_called_once_with(self.task.id)

    def test_other_task_updates_do_not_publish(self):
        self.task.name = "renamed"

        with (
            mock.patch("cvat.apps.test.signals.publish_task_changed") as publish,
            self.captureOnCommitCallbacks(execute=True),
        ):
            self.task.save()

        publish.assert_not_called()


class _ClientSocket:
    def __init__(self, scope: dict):
        self._to_server = asyncio.Queue()
        self._to_client = asyncio.Queue()
        self._to_server.put_nowait({"type": "websocket.connect"})
        self._server = asyncio.ensure_future(
            annotation_counts_websocket(scope, self._to_server.get, self._to_client.put)
        )

    async def next_event(self) -> dict:
        return await asyncio.wait_for(self._to_client.get(), timeout=10)

    async def disconnect(self) -> None:
        await self._to_server.put({"type": "websocket.disconnect", "code": 1000})
        await asyncio.wait_for(self._server, timeout=10)


class AnnotationCountsWebSocketTest(TransactionTestCase):
    def setUp(self):
        self.owner = create_user("owner")
        self.outsider = create_user("outsider")
        self.task = create_task(self.owner)
        populate_hand_checked_annotations(self.task)

        server = fakeredis.FakeServer()
        for patcher in (
            mock.patch.object(
                live_updates.redis.asyncio,
                "Redis",
                partial(fakeredis.FakeAsyncRedis, server=server),
            ),
            mock.patch.object(
                live_updates, "_publisher", lambda: fakeredis.FakeRedis(server=server)
            ),
        ):
            patcher.start()
            self.addCleanup(patcher.stop)

    def _scope(self, user=None, *, origin: bytes = b"http://testserver") -> dict:
        headers = [(b"host", b"testserver"), (b"origin", origin)]
        if user:
            client = Client()
            client.force_login(user)
            session = client.cookies[settings.SESSION_COOKIE_NAME].value
            headers.append((b"cookie", f"{settings.SESSION_COOKIE_NAME}={session}".encode()))

        return {
            "type": "websocket",
            "scheme": "ws",
            "path": f"/api/test/tasks/{self.task.id}/annotation-counts",
            "root_path": "",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 50000),
            "server": ("testserver", 80),
        }

    def _add_car_and_touch_task(self) -> None:
        first_job, _, _ = task_jobs(self.task)
        add_shape(first_job, Label.objects.get(task=self.task, name="car"), 3)
        self.task.touch()

    async def test_cross_origin_handshake_is_rejected(self):
        socket = _ClientSocket(self._scope(origin=b"http://evil.example"))

        self.assertEqual(await socket.next_event(), {"type": "websocket.close"})

    async def test_socket_without_login_is_closed_with_4401(self):
        socket = _ClientSocket(self._scope())

        self.assertEqual((await socket.next_event())["type"], "websocket.accept")
        self.assertEqual((await socket.next_event())["code"], 4401)

    async def test_socket_without_task_access_is_closed_with_4403(self):
        socket = _ClientSocket(await sync_to_async(self._scope)(self.outsider))

        self.assertEqual((await socket.next_event())["type"], "websocket.accept")
        self.assertEqual((await socket.next_event())["code"], 4403)

    async def test_socket_pushes_a_snapshot_and_then_every_change(self):
        socket = _ClientSocket(await sync_to_async(self._scope)(self.owner))

        self.assertEqual((await socket.next_event())["type"], "websocket.accept")
        snapshot = json.loads((await socket.next_event())["text"])
        self.assertEqual(snapshot["total"], 6)

        await sync_to_async(self._add_car_and_touch_task)()

        update = json.loads((await socket.next_event())["text"])
        self.assertEqual(update["total"], 7)
        await socket.disconnect()
