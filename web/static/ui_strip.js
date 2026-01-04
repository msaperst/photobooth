// web/static/recent_strip_logic.js

export function computeRecentStripUpdate({
    status,
    lastMostRecentStripUrl,
    lastBusy,
    shouldAutoScrollToStrip,
    nowMs,
}) {
    const url = status.most_recent_strip_url || null;

    if (!url) {
        return {
            show: false,
            stripSrc: null,
            qrSrc: null,
            shouldScroll: false,
            nextLastMostRecentStripUrl: null,
            nextShouldAutoScrollToStrip: false,
        };
    }

    let nextLastUrl = lastMostRecentStripUrl;
    let nextShouldAuto = shouldAutoScrollToStrip;

    let stripSrc = null;
    let qrSrc = null;

    // If URL changed, update the image sources and arm auto-scroll
    if (url !== lastMostRecentStripUrl) {
        const cacheBuster = `v=${nowMs}`;
        stripSrc = `${url}?${cacheBuster}`;
        qrSrc = `/qr/most-recent-strip.png?${cacheBuster}`;
        nextLastUrl = url;
        nextShouldAuto = true;
    }

    const shouldScroll = nextShouldAuto && lastBusy && !status.busy;

    return {
        show: true,
        stripSrc,
        qrSrc,
        shouldScroll,
        nextLastMostRecentStripUrl: nextLastUrl,
        // Disarm after we scroll; otherwise keep armed
        nextShouldAutoScrollToStrip: shouldScroll ? false : nextShouldAuto,
    };
}
