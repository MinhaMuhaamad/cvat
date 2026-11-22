// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import 'chart.js/auto';
import React from 'react';
import { Bar } from 'react-chartjs-2';
import { ChartData, ChartOptions } from 'chart.js';
import { AnnotationCounts } from './annotation-counts-api';

const BAR_HEIGHT_PX = 22;
const AXES_HEIGHT_PX = 60;
const TOTAL_COLOR = '#2a78d6';
const OTHER_SOURCE_COLOR = '#8c8b86';

// Fixed per source, so a source keeps its colour whatever else is on the chart
const SOURCE_COLORS: Record<string, string> = {
    manual: '#2a78d6',
    file: '#eb6834',
    auto: '#1baf7a',
    'semi-auto': '#eda100',
    consensus: '#e87ba4',
};

function sourcesIn(counts: AnnotationCounts): string[] {
    const sources = new Set<string>();
    counts.labels.forEach((label) => Object.keys(label.groups ?? {}).forEach((source) => sources.add(source)));
    return [...sources].sort();
}

function chartData(counts: AnnotationCounts): ChartData<'bar'> {
    const labels = counts.labels.map((label) => label.name);
    const barStyle = { borderRadius: 4, borderSkipped: 'start' as const, maxBarThickness: 16 };

    if (counts.group_by === 'source') {
        return {
            labels,
            datasets: sourcesIn(counts).map((source) => ({
                ...barStyle,
                label: source,
                data: counts.labels.map((label) => label.groups?.[source] ?? 0),
                backgroundColor: SOURCE_COLORS[source] ?? OTHER_SOURCE_COLOR,
                borderColor: '#ffffff',
                borderWidth: { right: 2 },
            })),
        };
    }

    return {
        labels,
        datasets: [{
            ...barStyle,
            label: 'Annotations',
            data: counts.labels.map((label) => label.count),
            backgroundColor: TOTAL_COLOR,
        }],
    };
}

interface Props {
    counts: AnnotationCounts;
}

export default function AnnotationCountsChart(props: Readonly<Props>): JSX.Element {
    const { counts } = props;
    const stacked = counts.group_by === 'source';
    const options: ChartOptions<'bar'> = {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        scales: {
            x: {
                stacked, beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#ececea' },
            },
            y: { stacked, grid: { display: false } },
        },
        plugins: {
            legend: { display: stacked, position: 'top', align: 'start' },
            tooltip: { mode: 'index', intersect: false },
        },
    };

    return (
        <div
            className='cvat-annotation-counts-chart'
            style={{ height: counts.labels.length * BAR_HEIGHT_PX + AXES_HEIGHT_PX }}
        >
            <Bar data={chartData(counts)} options={options} />
        </div>
    );
}
