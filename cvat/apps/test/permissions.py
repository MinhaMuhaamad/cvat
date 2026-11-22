# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from cvat.apps.engine.models import Task
from cvat.apps.engine.permissions import TaskPermission
from cvat.apps.engine.types import ExtendedRequest


class AnnotationCountsPermission:
    """
    Counts are derived from a task's annotations, so reading them requires the same
    OPA decision as GET /api/tasks/{id}/annotations: the tasks policy, "view:annotations".
    """

    @classmethod
    def create(cls, request: ExtendedRequest, view, obj: Task, iam_context: dict):
        return [
            TaskPermission.create_base_perm(
                request, view, TaskPermission.Scopes.VIEW_ANNOTATIONS, iam_context, obj
            )
        ]
