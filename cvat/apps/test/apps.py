# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.apps import AppConfig


class AnnotationAnalyticsConfig(AppConfig):
    name = "cvat.apps.test"
    verbose_name = "Annotation analytics"

    def ready(self) -> None:
        from . import signals  # pylint: disable=unused-import
