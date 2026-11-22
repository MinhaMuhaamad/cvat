// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';

import React, { useState } from 'react';
import { useParams } from 'react-router';
import { Row, Col } from 'antd/lib/grid';
import Button from 'antd/lib/button';
import Empty from 'antd/lib/empty';
import Radio from 'antd/lib/radio';
import Result from 'antd/lib/result';
import Table from 'antd/lib/table';
import Tag from 'antd/lib/tag';
import Text from 'antd/lib/typography/Text';
import Title from 'antd/lib/typography/Title';
import GoBackButton from 'components/common/go-back-button';
import CVATLoadingSpinner from 'components/common/loading-spinner';
import { AnnotationCounts, GroupBy, LabelAnnotationCount } from './annotation-counts-api';
import AnnotationCountsChart from './annotation-counts-chart';
import { LiveStatus, useLiveAnnotationCounts } from './use-live-annotation-counts';

const LIVE_STATUS_TAGS: Record<LiveStatus, JSX.Element> = {
    connecting: <Tag>Connecting…</Tag>,
    live: <Tag color='green'>Live</Tag>,
    reconnecting: <Tag color='orange'>Reconnecting…</Tag>,
    unavailable: <Tag color='red'>Live updates unavailable</Tag>,
};

function countsTable(counts: AnnotationCounts): JSX.Element {
    const sources = [...new Set(counts.labels.flatMap((label) => Object.keys(label.groups ?? {})))].sort();
    const columns = [
        { title: 'Label', dataIndex: 'name', key: 'name' },
        { title: 'Annotations', dataIndex: 'count', key: 'count' },
        ...sources.map((source) => ({
            title: source,
            key: source,
            render: (_: unknown, label: LabelAnnotationCount) => label.groups?.[source] ?? 0,
        })),
    ];

    return (
        <Table
            className='cvat-annotation-counts-table'
            size='small'
            rowKey='id'
            pagination={false}
            columns={columns}
            dataSource={counts.labels}
        />
    );
}

function AnnotationCountsPage(): JSX.Element {
    const taskId = +useParams<{ tid: string }>().tid;
    const [groupBy, setGroupBy] = useState<GroupBy | null>(null);
    const {
        counts, fetching, error, liveStatus, reload,
    } = useLiveAnnotationCounts(taskId, groupBy);

    let content: JSX.Element;
    if (counts === null && error) {
        content = (
            <Result
                className='cvat-annotation-counts-error'
                status='error'
                title='Could not load annotation counts'
                subTitle={error.message}
                extra={<Button type='primary' loading={fetching} onClick={reload}>Retry</Button>}
            />
        );
    } else if (counts === null) {
        content = <CVATLoadingSpinner />;
    } else if (counts.total === 0) {
        content = (
            <Empty
                className='cvat-annotation-counts-empty'
                description='This task has no annotations yet. Counts appear here as soon as shapes are saved.'
            />
        );
    } else {
        content = (
            <>
                <AnnotationCountsChart counts={counts} />
                {countsTable(counts)}
            </>
        );
    }

    return (
        <div className='cvat-annotation-counts-page'>
            <Row justify='center'>
                <Col span={22} xl={18} xxl={14}>
                    <GoBackButton />
                    <Row justify='space-between' align='middle' className='cvat-annotation-counts-header'>
                        <Col>
                            <Title level={4}>{`Annotation counts, task #${taskId}`}</Title>
                            {counts && <Text type='secondary'>{`${counts.total} annotations in total`}</Text>}
                        </Col>
                        <Col>
                            <Radio.Group
                                value={groupBy ?? 'none'}
                                onChange={(event) => setGroupBy(event.target.value === 'none' ? null : event.target.value)}
                            >
                                <Radio.Button value='none'>Per label</Radio.Button>
                                <Radio.Button value='source'>Per label and source</Radio.Button>
                            </Radio.Group>
                            {LIVE_STATUS_TAGS[liveStatus]}
                        </Col>
                    </Row>
                    {content}
                </Col>
            </Row>
        </div>
    );
}

export default React.memo(AnnotationCountsPage);
