// web/static/ui_logic.js

export function getButtonLabel(status) {
    const { state, photos_taken, total_photos, countdown_remaining } = status;

    if (state === "IDLE" || state === "READY_FOR_PHOTO") {
        return `Take Photo (${photos_taken % total_photos + 1} of ${total_photos})`;
    }

    if (state === "COUNTDOWN") {
        return countdown_remaining > 0
            ? countdown_remaining.toString()
            : "Smile!";
    }

    if (state === "CAPTURING_PHOTO") return "Capturing…";
    if (state === "PROCESSING") return "Processing…";
    if (state === "PRINTING") return "Printing…";

    return state;
}
