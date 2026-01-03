import { getButtonLabel } from "./ui_logic.js";
import { getConnectionHealth } from "./ui_state.js";
import { computeRecentStripUpdate } from "./ui_strip.js";

const isBrowser = typeof window !== "undefined";

/* ---------- Connection State ---------- */

let serverReachable = true;
let clickLock = null;

/* ---------- UI Helpers ---------- */

function updateButton(status) {
    const button = document.getElementById("startButton");
    button.innerText = getButtonLabel(status);

    const statusAllowsClick =
        status.state === "IDLE" ||
        status.state === "READY_FOR_PHOTO";

    button.disabled = !!clickLock || !statusAllowsClick;
}

function syncConnectionOverlay() {
    updateHealthOverlay(
        getConnectionHealth(serverReachable)
    );
}

/* ---------- Strip Selection ---------- */

let selectedStrips = 2;
let lastBusy = false;

function setStripSelection(strips) {
    selectedStrips = strips;

    document.querySelectorAll(".strip-option").forEach(btn => {
        const btnStrips = Number.parseInt(btn.dataset.strips, 10);
        btn.classList.toggle("active", btnStrips === strips);
    });
}

function enableStripSelection(enabled) {
    document.querySelectorAll(".strip-option").forEach(btn => {
        btn.disabled = !enabled;
    });
}

/* ---------- Error Overlay ---------- */

function updateHealthOverlay(health) {
    const overlay = document.getElementById("healthOverlay");
    const message = document.getElementById("healthMessage");
    const instructions = document.getElementById("healthInstructions");

    if (health.level === "OK") {
        overlay.classList.add("hidden");
        return;
    }

    message.textContent = health.message || "System error";
    instructions.innerHTML = "";

    (health.instructions || []).forEach(text => {
        const li = document.createElement("li");
        li.textContent = text;
        instructions.appendChild(li);
    });

    overlay.classList.remove("hidden");
}

/* -------Last Strip ------- */

let lastMostRecentStripUrl = null;
let shouldAutoScrollToStrip = false;

function updateMostRecentStrip(status) {
    const section = document.getElementById("recentStripSection");
    if (!section) return;

    const stripImg = document.getElementById("recentStripImage");
    const qrImg = document.getElementById("recentStripQr");

    const out = computeRecentStripUpdate({
        status,
        lastMostRecentStripUrl,
        lastBusy,
        shouldAutoScrollToStrip,
        nowMs: Date.now(),
    });

    // visibility
    if (!out.show) {
        section.classList.add("hidden");
    } else {
        section.classList.remove("hidden");
    }

    // update sources only when provided (URL changed)
    if (out.stripSrc) stripImg.src = out.stripSrc;
    if (out.qrSrc) qrImg.src = out.qrSrc;

    // scroll if requested
    if (out.shouldScroll) {
        section.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // persist state
    lastMostRecentStripUrl = out.nextLastMostRecentStripUrl;
    shouldAutoScrollToStrip = out.nextShouldAutoScrollToStrip;
}

/* ---------- API ---------- */

async function fetchJson(url) {
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
    }
    return response.json();
}

async function fetchStatus() {
    return fetchJson("/status");
}

async function fetchHealth() {
    return fetchJson("/health");
}

/* ---------- Main Button ---------- */

async function handleButtonClick() {
    if (!serverReachable) return;
    if (clickLock) return;

    const button = document.getElementById("startButton");
    button.disabled = true; // immediate UX response

    let initialStatus;
    try {
        initialStatus = await fetchStatus();
    } catch (e) {
        // If we can't even fetch status, don't lock the UI.
        button.disabled = false;
        throw e;
    }

    clickLock = {
        fromState: initialStatus.state,
        requestDone: false,
        startedAtMs: Date.now(),
    };

    try {
        if (initialStatus.state === "IDLE") {
            await fetch("/start-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    print_count: selectedStrips / 2,
                    image_count: 3
                })
            });

            await fetch("/take-photo", { method: "POST" });
        } else if (initialStatus.state === "READY_FOR_PHOTO") {
            await fetch("/take-photo", { method: "POST" });
        }

        // Mark that the network round-trip completed.
        clickLock.requestDone = true;

    } catch (err) {
        // On request failure, unlock immediately so operator can retry.
        clickLock = null;
        button.disabled = false;
        throw err;
    }
}

/* ---------- Poll Loop ---------- */

async function poll() {
    try {
        const [status, health] = await Promise.all([
            fetchStatus(),
            fetchHealth()
        ]);

        if (!serverReachable) {
            serverReachable = true;
            syncConnectionOverlay();
        }

        if (clickLock) {
            const elapsedMs = Date.now() - clickLock.startedAtMs;

            // Only unlock once the request finished AND we observe backend progress.
            // Progress = state changed away from the state we clicked from OR busy turned true.
            if (clickLock.requestDone && (status.busy || status.state !== clickLock.fromState)) {
                clickLock = null;
            }

            // Failsafe: if backend never progresses, unlock after 10s.
            if (elapsedMs > 10_000) {
                clickLock = null;
            }
        }

        updateButton(status);
        enableStripSelection(!status.busy);
        updateMostRecentStrip(status);
        updateHealthOverlay(health);

        if (lastBusy && !status.busy) {
            setStripSelection(2);
        }
        lastBusy = status.busy;

    } catch (err) {
        if (serverReachable) {
            serverReachable = false;
            syncConnectionOverlay();
        }
    }
}


/* ---------- Init ---------- */

function initUI() {
    document.querySelectorAll(".strip-option").forEach(button => {
        button.addEventListener("click", () => {
            if (button.disabled) return;
            const strips = Number.parseInt(button.dataset.strips, 10);
            setStripSelection(strips);
        });
    });

    document
        .getElementById("startButton")
        .addEventListener("click", handleButtonClick);

    setInterval(poll, 500);
    poll();
}

if (isBrowser) {
    initUI();
}
