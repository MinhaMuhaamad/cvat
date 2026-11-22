# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import asyncio
import io
import re
from functools import cache
from urllib.parse import urlsplit

import redis
import redis.asyncio
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core import signals
from django.core.handlers.asgi import ASGIRequest
from django.core.handlers.base import BaseHandler
from django.http import HttpResponse

from cvat.apps.engine.log import ServerLogManager

logger = ServerLogManager(__name__).glob

COUNTS_PATH = re.compile(r"^/api/test/tasks/(?P<task_id>\d+)/annotation-counts$")

# An import or a large save touches the task once per job. Changes arriving within
# this window are coalesced into a single push.
DEBOUNCE_SECONDS = 0.5

# WebSocket close codes 4000-4999 are reserved for applications.
# 4000 + HTTP status lets the client tell "forbidden" from "network dropped".
CLOSE_CODE_HTTP_STATUS_BASE = 4000
CLOSE_CODE_INTERNAL_ERROR = 1011


def _channel(task_id: int) -> str:
    return f"cvat:test:tasks:{task_id}:annotations-changed"


def _redis_kwargs() -> dict:
    return {
        "host": settings.REDIS_INMEM_SETTINGS["HOST"],
        "port": settings.REDIS_INMEM_SETTINGS["PORT"],
        "password": settings.REDIS_INMEM_SETTINGS["PASSWORD"] or None,
        "socket_connect_timeout": 1,
    }


@cache
def _publisher() -> redis.Redis:
    return redis.Redis(**_redis_kwargs())


def publish_task_changed(task_id: int) -> None:
    """
    Live updates are best effort: a Redis outage must never fail an annotation save.
    Clients still get correct data from the REST endpoint and on every reconnect.
    """
    try:
        _publisher().publish(_channel(task_id), "")
    except redis.RedisError:
        logger.warning("Could not publish an annotation change for task %s", task_id, exc_info=True)


@cache
def _http_handler() -> BaseHandler:
    handler = BaseHandler()
    handler.load_middleware()
    return handler


def _get_counts(scope: dict) -> HttpResponse:
    """
    Runs the REST endpoint with the socket's own URL, cookies and headers, so the login,
    the IAM check and the count query are exactly the ones a plain GET would use.
    """
    http_scope = {
        **scope,
        "type": "http",
        "method": "GET",
        "scheme": "https" if scope.get("scheme") == "wss" else "http",
    }
    signals.request_started.send(sender=BaseHandler, scope=http_scope)
    response = _http_handler().get_response(ASGIRequest(http_scope, io.BytesIO()))
    response.close()
    return response


def _is_same_origin(scope: dict) -> bool:
    # Browsers attach cookies to cross-site WebSocket handshakes, so a foreign page
    # could otherwise read the counts with the victim's session.
    headers = dict(scope["headers"])
    origin = headers.get(b"origin")
    if origin is None:
        return True

    return urlsplit(origin.decode("latin-1")).netloc == headers.get(b"host", b"").decode("latin-1")


async def _push_counts(scope: dict, send) -> bool:
    # _get_counts opens and closes its own DB connection through the request signals,
    # so it can run on any pool thread instead of queueing behind other sockets.
    response = await sync_to_async(_get_counts, thread_sensitive=False)(scope)
    if response.status_code != 200:
        await send(
            {
                "type": "websocket.close",
                "code": CLOSE_CODE_HTTP_STATUS_BASE + response.status_code,
                "reason": response.reason_phrase,
            }
        )
        return False

    await send({"type": "websocket.send", "text": response.content.decode()})
    return True


async def _wait_for_disconnect(receive) -> None:
    while (await receive())["type"] != "websocket.disconnect":
        pass


async def _wait_for_change(pubsub: redis.asyncio.client.PubSub) -> None:
    while await pubsub.get_message(ignore_subscribe_messages=True, timeout=None) is None:
        pass

    await asyncio.sleep(DEBOUNCE_SECONDS)
    while await pubsub.get_message(ignore_subscribe_messages=True, timeout=0) is not None:
        pass


async def _push_on_change(scope: dict, receive, send, pubsub) -> None:
    disconnected = asyncio.ensure_future(_wait_for_disconnect(receive))
    try:
        while True:
            changed = asyncio.ensure_future(_wait_for_change(pubsub))
            await asyncio.wait({disconnected, changed}, return_when=asyncio.FIRST_COMPLETED)
            if disconnected.done():
                changed.cancel()
                return

            changed.result()
            if not await _push_counts(scope, send):
                return
    finally:
        disconnected.cancel()


async def annotation_counts_websocket(scope: dict, receive, send) -> None:
    if (await receive())["type"] != "websocket.connect":
        return

    match = COUNTS_PATH.match(scope["path"])
    if not match or not _is_same_origin(scope):
        await send({"type": "websocket.close"})
        return

    await send({"type": "websocket.accept"})

    client = redis.asyncio.Redis(**_redis_kwargs())
    pubsub = client.pubsub()
    try:
        # Subscribe before the first snapshot, so a change made in between is not lost.
        await pubsub.subscribe(_channel(int(match["task_id"])))
        if await _push_counts(scope, send):
            await _push_on_change(scope, receive, send, pubsub)
    except redis.RedisError:
        logger.exception("Live annotation counts stopped for %s", scope["path"])
        await send({"type": "websocket.close", "code": CLOSE_CODE_INTERNAL_ERROR})
    finally:
        await pubsub.aclose()
        await client.aclose()


def with_websocket_routes(http_application):
    async def application(scope, receive, send):
        if scope["type"] == "websocket":
            await annotation_counts_websocket(scope, receive, send)
        else:
            await http_application(scope, receive, send)

    return application
