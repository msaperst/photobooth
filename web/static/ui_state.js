// web/static/ui_state.js

export function getConnectionHealth(serverReachable) {
    if (serverReachable) {
        return { level: "OK" };
    }

    return {
        level: "ERROR",
        message: "Photobooth connection lost",
        instructions: [
            "Please wait while we reconnect",
            "If this does not recover, ask an attendant"
        ]
    };
}
