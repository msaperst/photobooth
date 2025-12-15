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

/* ---------- API ---------- */

async function fetchStatus() {
    const response = await fetch("/status");
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

/* ---------- Poll Loop ---------- */

async function poll() {
    const status = await fetchStatus();

    updateButton(status);

    // Disable strip selection once session starts
    enableStripSelection(!status.busy);

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
}

if (isBrowser) {
    initUI();
}