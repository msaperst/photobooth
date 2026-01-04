import {describe, expect, it} from "vitest";
import {getButtonLabel} from "../../web/static/ui_logic.js";
import {getConnectionHealth} from "../../web/static/ui_state.js";
import {computeRecentStripUpdate} from "../../web/static/ui_strip.js";
import {
    clearActionPending,
    createActionLatch,
    isPrimaryActionDisabled,
    markActionPending,
    statusAllowsPrimaryAction,
    updateLatchFromPoll,
} from "../../web/static/ui_action.js";

describe("getButtonLabel", () => {
    it("shows Take Photo when idle", () => {
        const status = {
            state: "IDLE",
            photos_taken: 0,
            total_photos: 3,
            countdown_remaining: 0,
        };

        expect(getButtonLabel(status)).toBe("Take Photo (1 of 3)");
    });

    it("shows correct photo number when ready", () => {
        const status = {
            state: "READY_FOR_PHOTO",
            photos_taken: 1,
            total_photos: 3,
            countdown_remaining: 0,
        };

        expect(getButtonLabel(status)).toBe("Take Photo (2 of 3)");
    });

    it("shows numeric countdown", () => {
        const status = {
            state: "COUNTDOWN",
            photos_taken: 0,
            total_photos: 3,
            countdown_remaining: 2,
        };

        expect(getButtonLabel(status)).toBe("2");
    });

    it("shows Smile at zero countdown", () => {
        const status = {
            state: "COUNTDOWN",
            photos_taken: 0,
            total_photos: 3,
            countdown_remaining: 0,
        };

        expect(getButtonLabel(status)).toBe("Smile!");
    });

    it("shows processing states", () => {
        expect(getButtonLabel({state: "CAPTURING_PHOTO"})).toBe("Capturing…");
        expect(getButtonLabel({state: "PROCESSING"})).toBe("Processing…");
        expect(getButtonLabel({state: "PRINTING"})).toBe("Printing…");
    });

    it("falls back to state string for unknown states", () => {
        expect(getButtonLabel({state: "UNKNOWN_STATE"})).toBe("UNKNOWN_STATE");
    });
});

describe("getConnectionHealth", () => {
    it("returns OK when server is reachable", () => {
        expect(getConnectionHealth(true)).toEqual({
            level: "OK"
        });
    });

    it("returns error overlay data when server is unreachable", () => {
        expect(getConnectionHealth(false)).toEqual({
            level: "ERROR",
            message: "Photobooth connection lost",
            instructions: [
                "Check that the photobooth computer is powered on",
                "Confirm this screen is connected to the photobooth Wi-Fi network",
                "Wait a few seconds — the system will reconnect automatically",
                "If the issue persists, restart the photobooth system",
            ]
        });
    });
});

describe("computeRecentStripUpdate", () => {
    it("hides when no URL", () => {
        const out = computeRecentStripUpdate({
            status: {busy: false},
            lastMostRecentStripUrl: "/sessions/x/strip.jpg",
            lastBusy: true,
            shouldAutoScrollToStrip: true,
            nowMs: 123,
        });

        expect(out.show).toBe(false);
        expect(out.shouldScroll).toBe(false);
        expect(out.nextLastMostRecentStripUrl).toBe(null);
        expect(out.nextShouldAutoScrollToStrip).toBe(false);
    });

    it("sets srcs and arms auto-scroll when URL changes", () => {
        const out = computeRecentStripUpdate({
            status: {busy: true, most_recent_strip_url: "/sessions/a/strip.jpg"},
            lastMostRecentStripUrl: null,
            lastBusy: true,
            shouldAutoScrollToStrip: false,
            nowMs: 999,
        });

        expect(out.show).toBe(true);
        expect(out.stripSrc).toBe("/sessions/a/strip.jpg?v=999");
        expect(out.qrSrc).toBe("/qr/most-recent-strip.png?v=999");
        expect(out.shouldScroll).toBe(false);
        expect(out.nextLastMostRecentStripUrl).toBe("/sessions/a/strip.jpg");
        expect(out.nextShouldAutoScrollToStrip).toBe(true);
    });

    it("scrolls exactly once after busy true->false when armed", () => {
        const out = computeRecentStripUpdate({
            status: {busy: false, most_recent_strip_url: "/sessions/a/strip.jpg"},
            lastMostRecentStripUrl: "/sessions/a/strip.jpg",
            lastBusy: true,
            shouldAutoScrollToStrip: true,
            nowMs: 111,
        });

        expect(out.shouldScroll).toBe(true);
        expect(out.nextShouldAutoScrollToStrip).toBe(false);
    });

    it("does not re-scroll when not armed", () => {
        const out = computeRecentStripUpdate({
            status: {busy: false, most_recent_strip_url: "/sessions/a/strip.jpg"},
            lastMostRecentStripUrl: "/sessions/a/strip.jpg",
            lastBusy: true,
            shouldAutoScrollToStrip: false,
            nowMs: 222,
        });

        expect(out.shouldScroll).toBe(false);
        expect(out.nextShouldAutoScrollToStrip).toBe(false);
    });
});

describe("action button enabling and disabling", () => {

    it("statusAllowsPrimaryAction: IDLE and READY_FOR_PHOTO are clickable", () => {
        expect(statusAllowsPrimaryAction({state: "IDLE"})).toBe(true);
        expect(statusAllowsPrimaryAction({state: "READY_FOR_PHOTO"})).toBe(true);
        expect(statusAllowsPrimaryAction({state: "COUNTDOWN"})).toBe(false);
        expect(statusAllowsPrimaryAction({state: "PROCESSING"})).toBe(false);
    });

    it("isPrimaryActionDisabled: pending latch forces disabled", () => {
        let latch = createActionLatch({timeoutMs: 10_000});
        const status = {state: "READY_FOR_PHOTO"};

        expect(isPrimaryActionDisabled(latch, status)).toBe(false);

        latch = markActionPending(latch, {fromState: "READY_FOR_PHOTO", nowMs: 1000});
        expect(isPrimaryActionDisabled(latch, status)).toBe(true);

        latch = clearActionPending(latch);
        expect(isPrimaryActionDisabled(latch, status)).toBe(false);
    });

    it("updateLatchFromPoll returns latch unchanged when not pending", () => {
        const latch = createActionLatch({timeoutMs: 10_000});

        const out = updateLatchFromPoll(latch, {
            status: {state: "READY_FOR_PHOTO"},
            nowMs: 1234,
        });

        // Exact same object back (pure no-op)
        expect(out).toBe(latch);
        expect(out.pending).toBe(false);
        expect(out.fromState).toBe(null);
        expect(out.sinceMs).toBe(0);
    });

    it("updateLatchFromPoll clears when state changes from the clicked-from state", () => {
        let latch = createActionLatch({timeoutMs: 10_000});
        latch = markActionPending(latch, {fromState: "READY_FOR_PHOTO", nowMs: 1000});

        // Same state -> still pending
        latch = updateLatchFromPoll(latch, {status: {state: "READY_FOR_PHOTO"}, nowMs: 1200});
        expect(latch.pending).toBe(true);

        // State changes -> clears
        latch = updateLatchFromPoll(latch, {status: {state: "COUNTDOWN"}, nowMs: 1500});
        expect(latch.pending).toBe(false);
        expect(latch.fromState).toBe(null);
    });

    it("updateLatchFromPoll clears after timeout even without state change", () => {
        let latch = createActionLatch({timeoutMs: 500});
        latch = markActionPending(latch, {fromState: "READY_FOR_PHOTO", nowMs: 1000});

        latch = updateLatchFromPoll(latch, {status: {state: "READY_FOR_PHOTO"}, nowMs: 1200});
        expect(latch.pending).toBe(true);

        latch = updateLatchFromPoll(latch, {status: {state: "READY_FOR_PHOTO"}, nowMs: 1600});
        expect(latch.pending).toBe(false);
    });
});
