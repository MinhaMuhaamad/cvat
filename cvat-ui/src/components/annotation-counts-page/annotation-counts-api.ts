// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import { getCore } from 'cvat-core-wrapper';

const core = getCore();

export type GroupBy = 'source';

export interface LabelAnnotationCount {
    id: number;
    name: string;
    color: string;
    count: number;
    groups?: Record<string, number>;
}

export interface AnnotationCounts {
    task_id: number;
    group_by: GroupBy | null;
    total: number;
    labels: LabelAnnotationCount[];
}

function countsPath(taskId: number): string {
    return `${core.config.backendAPI}/test/tasks/${taskId}/annotation-counts`;
}

export async function fetchAnnotationCounts(taskId: number, groupBy: GroupBy | null): Promise<AnnotationCounts> {
    const response = await core.server.request(countsPath(taskId), {
        method: 'GET',
        params: groupBy ? { group_by: groupBy } : {},
    }) as { data: AnnotationCounts };
    return response.data;
}

export function annotationCountsSocketURL(taskId: number, groupBy: GroupBy | null): string {
    const url = new URL(countsPath(taskId), window.location.href);
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    if (groupBy) {
        url.searchParams.set('group_by', groupBy);
    }
    return url.toString();
}
