import { getButtonLabel } from "./ui_logic.js";
import { getConnectionHealth } from "./ui_state.js";

const isBrowser = typeof window !== "undefined";

/* ---------- Connection State ---------- */

let serverReachable = true;

/* ---------- UI Helpers ---------- */

function updateButton(status) {
    const button = document.getElementById("startButton");
    button.innerText = getButtonLabel(status);
    button.disabled = !(
        status.state === "IDLE" ||
        status.state === "READY_FOR_PHOTO"
    );
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

    const status = await fetchStatus();

    if (status.state === "IDLE") {
        await fetch("/start-session", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                print_count: selectedStrips / 2,
                image_count: 3
            })
        });

        await fetch("/take-photo", { method: "POST" });
        return;
    }

    if (status.state === "READY_FOR_PHOTO") {
        await fetch("/take-photo", { method: "POST" });
    }
}

/* ---------- Live View ---------- */

let lastObjectUrl = null;

async function pollLiveView() {
    if (!serverReachable) return;

    const img = document.getElementById("liveView");
    if (!img) return;

    try {
        const resp = await fetch(`/live-view?ts=${Date.now()}`);
        if (resp.status === 204 || !resp.ok) return;

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);

        if (lastObjectUrl) URL.revokeObjectURL(lastObjectUrl);
        lastObjectUrl = url;

        img.src = url;
    } catch {
        // Connection loss is handled by main poll loop
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

        updateButton(status);
        enableStripSelection(!status.busy);
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

    setInterval(pollLiveView, 400);
    pollLiveView();
}

if (isBrowser) {
    initUI();
}
