# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APITestCase

from cvat.apps.engine.models import Label, LabelType, Project, ShapeType, Task
from cvat.apps.test.counts import GroupBy, count_annotations_by_label

from .utils import add_shape, create_task, create_user, populate_hand_checked_annotations, task_jobs


def _url(task_id: int) -> str:
    return f"/api/test/tasks/{task_id}/annotation-counts"


class CountAnnotationsByLabelTest(TestCase):
    def setUp(self):
        self.task = create_task(create_user("owner"))
        self.car = Label.objects.get(task=self.task, name="car")
        self.person = Label.objects.get(task=self.task, name="person")

    def _counts(self, **kwargs) -> dict:
        task = Task.objects.select_related("data").get(id=self.task.id)
        return count_annotations_by_label(task, **kwargs)

    def test_counts_match_hand_checked_values(self):
        populate_hand_checked_annotations(self.task)

        self.assertEqual(
            self._counts(),
            {
                "task_id": self.task.id,
                "group_by": None,
                "total": 6,
                "labels": [
                    {"id": self.car.id, "name": "car", "color": "", "count": 4},
                    {"id": self.person.id, "name": "person", "color": "", "count": 2},
                ],
            },
        )

    def test_group_by_source_splits_each_label(self):
        populate_hand_checked_annotations(self.task)

        counts = self._counts(group_by=GroupBy.SOURCE)

        self.assertEqual(counts["group_by"], "source")
        self.assertEqual(
            {label["name"]: label["groups"] for label in counts["labels"]},
            {"car": {"manual": 2, "file": 2}, "person": {"manual": 1, "auto": 1}},
        )

    def test_task_without_annotations_lists_every_label_with_zero(self):
        counts = self._counts()

        self.assertEqual(counts["total"], 0)
        self.assertEqual(
            [(label["name"], label["count"]) for label in counts["labels"]],
            [("car", 0), ("person", 0)],
        )

    def test_skeleton_counts_once_and_its_points_are_not_listed(self):
        body = Label.objects.create(task=self.task, name="body", type=LabelType.SKELETON)
        head = Label.objects.create(task=self.task, name="head", parent=body)
        first_job, _, _ = task_jobs(self.task)
        skeleton = add_shape(first_job, body, 0, type=ShapeType.SKELETON)
        add_shape(first_job, head, 0, type=ShapeType.POINTS, parent=skeleton)

        counts = {label["name"]: label["count"] for label in self._counts()["labels"]}

        self.assertEqual(counts, {"body": 1, "car": 0, "person": 0})

    def test_task_in_project_uses_project_labels(self):
        project = Project.objects.create(name="project", owner=self.task.owner)
        tree = Label.objects.create(project=project, name="tree")
        self.task = create_task(self.task.owner, project=project)
        first_job, _, _ = task_jobs(self.task)
        add_shape(first_job, tree, 0)

        counts = self._counts()

        self.assertEqual(
            counts["labels"], [{"id": tree.id, "name": "tree", "color": "", "count": 1}]
        )

    def test_number_of_queries_does_not_depend_on_annotation_count(self):
        task = Task.objects.select_related("data").get(id=self.task.id)
        populate_hand_checked_annotations(self.task)
        with self.assertNumQueries(5):
            count_annotations_by_label(task)

        first_job, _, _ = task_jobs(self.task)
        for frame in range(5):
            add_shape(first_job, self.car, frame)
        with self.assertNumQueries(5):
            count_annotations_by_label(task)


class AnnotationCountsApiTest(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = create_user("owner")
        cls.assignee = create_user("assignee")
        cls.outsider = create_user("outsider")
        cls.task = create_task(cls.owner)
        cls.task.assignee = cls.assignee
        cls.task.save()
        populate_hand_checked_annotations(cls.task)

    def test_request_without_login_is_refused_with_401(self):
        response = self.client.get(_url(self.task.id))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_without_access_to_the_task_is_refused_with_403(self):
        self.client.force_login(self.outsider)

        response = self.client.get(_url(self.task.id))

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_task_owner_gets_the_counts(self):
        self.client.force_login(self.owner)

        response = self.client.get(_url(self.task.id))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["total"], 6)

    def test_task_assignee_gets_the_counts(self):
        self.client.force_login(self.assignee)

        response = self.client.get(_url(self.task.id), {"group_by": "source"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["labels"][0]["groups"], {"manual": 2, "file": 2})

    def test_unknown_grouping_is_rejected_with_400(self):
        self.client.force_login(self.owner)

        response = self.client.get(_url(self.task.id), {"group_by": "colour"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_task_returns_404(self):
        self.client.force_login(self.owner)

        response = self.client.get(_url(self.task.id + 1000))

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
