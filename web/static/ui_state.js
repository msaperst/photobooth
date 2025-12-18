// web/static/ui_state.js

export function getConnectionHealth(serverReachable) {
    if (serverReachable) {
        return { level: "OK" };
    }

    return {
        level: "ERROR",
        message: "Photobooth connection lost",
        instructions: [
            "Check that the photobooth computer is powered on",
            "Confirm this screen is connected to the photobooth Wi-Fi network",
            "Wait a few seconds — the system will reconnect automatically",
            "If the issue persists, restart the photobooth system",
        ]
    };
}
