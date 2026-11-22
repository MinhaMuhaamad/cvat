# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.contrib.auth.models import Group, User

from cvat.apps.engine.models import (
    Data,
    Job,
    JobType,
    Label,
    LabeledImage,
    LabeledShape,
    LabeledTrack,
    Project,
    Segment,
    SegmentType,
    ShapeType,
    SourceType,
    Task,
    TrackedShape,
)


def create_user(username: str) -> User:
    user = User.objects.create_user(username=username, password=username)
    user.groups.add(Group.objects.get_or_create(name="user")[0])
    return user


def create_task(owner: User, *, project: Project | None = None, labels=("car", "person")) -> Task:
    """
    A 10-frame image task split into two annotation jobs (frames 0-4 and 5-9),
    plus a ground truth job over frames 0-1. Frame 9 is deleted.
    """
    data = Data.objects.create(size=10, stop_frame=9, image_quality=70, deleted_frames=[9])
    task = Task.objects.create(
        name="annotation counts", owner=owner, project=project, data=data, segment_size=5
    )
    if project is None:
        for name in labels:
            Label.objects.create(task=task, name=name)

    for start, stop in ((0, 4), (5, 9)):
        segment = Segment.objects.create(task=task, start_frame=start, stop_frame=stop)
        Job.objects.create(segment=segment)

    gt_segment = Segment.objects.create(
        task=task, start_frame=0, stop_frame=9, type=SegmentType.SPECIFIC_FRAMES, frames=[0, 1]
    )
    Job.objects.create(segment=gt_segment, type=JobType.GROUND_TRUTH)

    return task


def task_jobs(task: Task) -> tuple[Job, Job, Job]:
    first, second = Job.objects.filter(segment__task=task, type=JobType.ANNOTATION).order_by("id")
    ground_truth = Job.objects.get(segment__task=task, type=JobType.GROUND_TRUTH)
    return first, second, ground_truth


def add_shape(job: Job, label: Label, frame: int, *, source=SourceType.MANUAL, **kwargs):
    return LabeledShape.objects.create(
        job=job,
        label=label,
        frame=frame,
        source=source,
        type=kwargs.pop("type", ShapeType.RECTANGLE),
        points=[0, 0, 10, 10],
        **kwargs,
    )


def populate_hand_checked_annotations(task: Task) -> None:
    """
    Expected counts, by hand:
      car    = 2 boxes + 1 polygon + 1 tag              = 4  (manual 2, file 2)
      person = 1 box + 1 track (3 keyframes count once) = 2  (manual 1, auto 1)
    Not counted: the box on deleted frame 9 and the 3 boxes in the ground truth job.
    """
    car = Label.objects.get(task=task, name="car")
    person = Label.objects.get(task=task, name="person")
    first, second, ground_truth = task_jobs(task)

    add_shape(first, car, 0)
    add_shape(first, car, 0)
    add_shape(first, car, 1, type=ShapeType.POLYGON, source=SourceType.FILE)
    add_shape(first, person, 2)

    track = LabeledTrack.objects.create(job=second, label=person, frame=5, source=SourceType.AUTO)
    for frame in (5, 6, 7):
        TrackedShape.objects.create(
            track=track, frame=frame, type=ShapeType.RECTANGLE, points=[0, 0, 10, 10]
        )

    LabeledImage.objects.create(job=second, label=car, frame=6, source=SourceType.FILE)
    add_shape(second, car, 9)

    for _ in range(3):
        add_shape(ground_truth, car, 0)
