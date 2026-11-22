# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import serializers

from cvat.apps.test.counts import GroupBy


class AnnotationCountsQuerySerializer(serializers.Serializer):
    group_by = serializers.ChoiceField(choices=[g.value for g in GroupBy], required=False)


class LabelAnnotationCountSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    color = serializers.CharField()
    count = serializers.IntegerField()
    groups = serializers.DictField(child=serializers.IntegerField(), required=False)


class AnnotationCountsSerializer(serializers.Serializer):
    task_id = serializers.IntegerField()
    group_by = serializers.ChoiceField(choices=[g.value for g in GroupBy], allow_null=True)
    total = serializers.IntegerField()
    labels = LabelAnnotationCountSerializer(many=True)
