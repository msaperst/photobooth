// web/static/ui_action.js
//
// Pure logic for preventing double-taps on the primary action button.
// No DOM access. No network access.
// Intended to be easy to unit test.

export function createActionLatch({ timeoutMs = 10_000 } = {}) {
    return {
        pending: false,
        fromState: null,
        sinceMs: 0,
        timeoutMs,
    };
}

export function markActionPending(latch, { fromState, nowMs }) {
    return {
        ...latch,
        pending: true,
        fromState,
        sinceMs: nowMs,
    };
}

export function clearActionPending(latch) {
    return {
        ...latch,
        pending: false,
        fromState: null,
        sinceMs: 0,
    };
}

export function statusAllowsPrimaryAction(status) {
    return status.state === "IDLE" || status.state === "READY_FOR_PHOTO";
}

/**
 * Compute whether the primary action button should be disabled.
 * We intentionally do NOT use status.busy here, because "busy" may be true for
 * long stretches of an active session and is not a reliable indicator that we
 * should disable the button.
 */
export function isPrimaryActionDisabled(latch, status) {
    return latch.pending || !statusAllowsPrimaryAction(status);
}

/**
 * Called on each status poll to potentially clear the latch once we observe
 * backend progress.
 */
export function updateLatchFromPoll(latch, { status, nowMs }) {
    if (!latch.pending) return latch;

    const stateChanged = latch.fromState !== null && status.state !== latch.fromState;
    if (stateChanged) return clearActionPending(latch);

    if (nowMs - latch.sinceMs > latch.timeoutMs) return clearActionPending(latch);

    return latch;
}
