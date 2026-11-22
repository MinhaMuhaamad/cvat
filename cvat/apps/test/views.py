# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiTypes, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from cvat.apps.engine.models import Task
from cvat.apps.engine.types import ExtendedRequest
from cvat.apps.test.counts import GroupBy, count_annotations_by_label
from cvat.apps.test.permissions import AnnotationCountsPermission
from cvat.apps.test.serializers import AnnotationCountsQuerySerializer, AnnotationCountsSerializer


@extend_schema(tags=["test"])
class AnnotationCountsViewSet(viewsets.GenericViewSet):
    iam_permission_class = AnnotationCountsPermission

    @extend_schema(
        summary="Get the number of annotations per label in a task",
        parameters=[
            OpenApiParameter("id", OpenApiTypes.INT, OpenApiParameter.PATH, description="Task id"),
            AnnotationCountsQuerySerializer,
        ],
        responses={"200": AnnotationCountsSerializer},
    )
    @action(detail=True, methods=["GET"], url_path="annotation-counts")
    def annotation_counts(self, request: ExtendedRequest, pk: int):
        task = get_object_or_404(Task.objects.select_related("data", "project"), pk=pk)
        self.check_object_permissions(request, task)

        query = AnnotationCountsQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        group_by = query.validated_data.get("group_by")

        counts = count_annotations_by_label(task, group_by=GroupBy(group_by) if group_by else None)
        return Response(AnnotationCountsSerializer(counts).data)
