# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from collections import defaultdict
from enum import StrEnum

from django.db.models import Count, QuerySet

from cvat.apps.engine.models import (
    Job,
    JobType,
    Label,
    LabeledImage,
    LabeledInterval,
    LabeledShape,
    LabeledTrack,
    Task,
)


class GroupBy(StrEnum):
    SOURCE = "source"


UNKNOWN_SOURCE = "unknown"


def _labelled_annotations(task: Task) -> list[QuerySet]:
    """
    One queryset per annotation table that carries a label.

    Only regular annotation jobs are counted, the same jobs the task export reads, so
    ground truth and consensus replica jobs do not inflate the numbers. Skeleton points
    and track elements (parent is set) belong to their parent object and are not counted
    separately. Shapes and tags on deleted frames are skipped, as in the export.
    """
    job_ids = Job.objects.filter(segment__task_id=task.id, type=JobType.ANNOTATION).values("id")
    deleted_frames = task.data.deleted_frames if task.data_id else []

    return [
        LabeledShape.objects.filter(job_id__in=job_ids, parent__isnull=True).exclude(
            frame__in=deleted_frames
        ),
        LabeledTrack.objects.filter(job_id__in=job_ids, parent__isnull=True),
        LabeledImage.objects.filter(job_id__in=job_ids).exclude(frame__in=deleted_frames),
        LabeledInterval.objects.filter(job_id__in=job_ids),
    ]


def _task_labels(task: Task) -> QuerySet:
    labels = Label.objects.filter(parent__isnull=True)
    if task.project_id:
        labels = labels.filter(project_id=task.project_id)
    else:
        labels = labels.filter(task_id=task.id)

    return labels.order_by("id").values("id", "name", "color")


def count_annotations_by_label(task: Task, *, group_by: GroupBy | None = None) -> dict:
    group_fields = ["label_id"]
    if group_by == GroupBy.SOURCE:
        group_fields.append("source")

    totals = defaultdict(int)
    groups = defaultdict(lambda: defaultdict(int))
    for annotations in _labelled_annotations(task):
        rows = annotations.values(*group_fields).annotate(count=Count("id")).order_by()
        for row in rows:
            totals[row["label_id"]] += row["count"]
            if group_by == GroupBy.SOURCE:
                groups[row["label_id"]][row["source"] or UNKNOWN_SOURCE] += row["count"]

    labels = []
    for label in _task_labels(task):
        entry = {**label, "count": totals[label["id"]]}
        if group_by:
            entry["groups"] = dict(groups[label["id"]])
        labels.append(entry)

    labels.sort(key=lambda entry: (-entry["count"], entry["name"]))

    return {
        "task_id": task.id,
        "group_by": group_by,
        "total": sum(entry["count"] for entry in labels),
        "labels": labels,
    }
