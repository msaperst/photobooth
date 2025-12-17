import { getButtonLabel } from "./ui_logic.js";

const isBrowser = typeof window !== "undefined";

function updateButton(status) {
    const button = document.getElementById("startButton");
    button.innerText = getButtonLabel(status);
    button.disabled = !(
        status.state === "IDLE" ||
        status.state === "READY_FOR_PHOTO"
    );
}

let selectedStrips = 2;
let lastBusy = false;

/* ---------- Strip Selection ---------- */

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

/* --------- Error Messages -----*/

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

async function fetchStatus() {
    const response = await fetch("/status");
    return response.json();
}

async function fetchHealth() {
    const response = await fetch("/health");
    return response.json();
}

/* ---------- Main Button ---------- */

async function handleButtonClick() {
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

        // Immediately take first photo
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
    const img = document.getElementById("liveView");
    if (!img) return;

    try {
        const resp = await fetch(`/live-view?ts=${Date.now()}`);
        if (resp.status === 204) return;
        if (!resp.ok) return;

        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);

        // Avoid leaking object URLs
        if (lastObjectUrl) URL.revokeObjectURL(lastObjectUrl);
        lastObjectUrl = url;

        img.src = url;
    } catch (e) {
        // Silent failure is fine; next poll will retry
        console.info(e);
    }
}

/* ---------- Poll Loop ---------- */

async function poll() {
    const status = await fetchStatus();
    updateButton(status);
    enableStripSelection(!status.busy);

    const health = await fetchHealth();
    updateHealthOverlay(health);

    // Reset strip selection after session ends
    if (lastBusy && !status.busy) {
        setStripSelection(2);
    }

    lastBusy = status.busy;
}

function initUI() {
    // Wire strip buttons
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