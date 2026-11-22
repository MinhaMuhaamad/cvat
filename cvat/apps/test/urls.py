# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.urls import include, path
from rest_framework import routers

from cvat.apps.test import views

router = routers.SimpleRouter(trailing_slash=False)
router.register("tasks", views.AnnotationCountsViewSet, basename="test_tasks")

urlpatterns = [
    path("test/", include(router.urls)),
]
