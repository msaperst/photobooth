import { describe, it, expect } from "vitest";
import { getButtonLabel } from "../../web/static/ui_logic.js";
import { getConnectionHealth } from "../../web/static/ui_state.js";

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
        expect(getButtonLabel({ state: "CAPTURING_PHOTO" })).toBe("Capturing…");
        expect(getButtonLabel({ state: "PROCESSING" })).toBe("Processing…");
        expect(getButtonLabel({ state: "PRINTING" })).toBe("Printing…");
    });

    it("falls back to state string for unknown states", () => {
        expect(getButtonLabel({ state: "UNKNOWN_STATE" })).toBe("UNKNOWN_STATE");
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