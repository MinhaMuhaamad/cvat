# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from functools import partial

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from cvat.apps.engine.models import Task
from cvat.apps.test.live_updates import publish_task_changed


@receiver(post_save, sender=Task, dispatch_uid=__name__ + ".notify_task_touched")
def notify_task_touched(instance: Task, update_fields=None, **kwargs):
    # Every annotation write, from the editor or from an import worker, ends in
    # JobAnnotation._set_updated_date(), which calls task.touch(), i.e.
    # save(update_fields=["updated_date"]).
    if update_fields != frozenset({"updated_date"}):
        return

    transaction.on_commit(partial(publish_task_changed, instance.id))
