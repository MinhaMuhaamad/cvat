// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import {
    useCallback, useEffect, useRef, useState,
} from 'react';
import {
    AnnotationCounts, GroupBy, annotationCountsSocketURL, fetchAnnotationCounts,
} from './annotation-counts-api';

export type LiveStatus = 'connecting' | 'live' | 'reconnecting' | 'unavailable';

const FIRST_RETRY_DELAY_MS = 1000;
const MAX_RETRY_DELAY_MS = 30000;

// The server closes with 4000 + HTTP status when the request itself is refused
// (no login, no access, task deleted). Reconnecting cannot fix those.
function isRefusedByServer(closeCode: number): boolean {
    return closeCode >= 4400 && closeCode < 4500;
}

function retryDelay(attempt: number): number {
    const exponential = Math.min(MAX_RETRY_DELAY_MS, FIRST_RETRY_DELAY_MS * 2 ** attempt);
    // Jitter, so that clients dropped together by a server restart do not reconnect together
    return exponential / 2 + Math.random() * (exponential / 2);
}

interface LiveAnnotationCounts {
    counts: AnnotationCounts | null;
    fetching: boolean;
    error: Error | null;
    liveStatus: LiveStatus;
    reload: () => void;
}

export function useLiveAnnotationCounts(taskId: number, groupBy: GroupBy | null): LiveAnnotationCounts {
    const [counts, setCounts] = useState<AnnotationCounts | null>(null);
    const [fetching, setFetching] = useState(true);
    const [error, setError] = useState<Error | null>(null);
    const [liveStatus, setLiveStatus] = useState<LiveStatus>('connecting');
    const [reloadKey, setReloadKey] = useState(0);
    const hasLiveData = useRef(false);

    useEffect(() => {
        let cancelled = false;
        setFetching(true);
        setError(null);

        fetchAnnotationCounts(taskId, groupBy).then((data) => {
            // A pushed snapshot is at least as fresh as this response
            if (!cancelled && !hasLiveData.current) {
                setCounts(data);
            }
        }).catch((fetchError: Error) => {
            if (!cancelled) {
                setError(fetchError);
            }
        }).finally(() => {
            if (!cancelled) {
                setFetching(false);
            }
        });

        return () => {
            cancelled = true;
        };
    }, [taskId, groupBy, reloadKey]);

    useEffect(() => {
        let socket: WebSocket | null = null;
        let attempt = 0;
        let retryTimer: number | undefined;
        let refused = false;
        let stopped = false;

        const connect = (): void => {
            socket = new WebSocket(annotationCountsSocketURL(taskId, groupBy));

            // Every (re)connection starts with a full snapshot from the server,
            // so nothing missed while offline needs to be replayed.
            socket.onmessage = (event: MessageEvent<string>) => {
                attempt = 0;
                hasLiveData.current = true;
                setCounts(JSON.parse(event.data));
                setError(null);
                setLiveStatus('live');
            };

            socket.onclose = (event: CloseEvent) => {
                if (stopped) {
                    return;
                }

                if (isRefusedByServer(event.code)) {
                    refused = true;
                    setLiveStatus('unavailable');
                    return;
                }

                setLiveStatus('reconnecting');
                retryTimer = window.setTimeout(connect, retryDelay(attempt));
                attempt += 1;
            };
        };

        // When the browser reports the network is back, skip the remaining backoff wait
        const reconnectNow = (): void => {
            if (!refused && socket?.readyState === WebSocket.CLOSED) {
                window.clearTimeout(retryTimer);
                attempt = 0;
                connect();
            }
        };

        hasLiveData.current = false;
        setLiveStatus('connecting');
        connect();
        window.addEventListener('online', reconnectNow);

        return () => {
            stopped = true;
            window.clearTimeout(retryTimer);
            window.removeEventListener('online', reconnectNow);
            socket?.close();
        };
    }, [taskId, groupBy]);

    const reload = useCallback(() => setReloadKey((key) => key + 1), []);

    return {
        counts, fetching, error, liveStatus, reload,
    };
}
