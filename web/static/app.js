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

    setInterval(() => {
        const img = document.getElementById("liveView");
        img.src = `/live-view?ts=${Date.now()}`;
    }, 250);
}

if (isBrowser) {
    initUI();
}