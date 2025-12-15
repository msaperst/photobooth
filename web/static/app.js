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

// Wire strip buttons
document.querySelectorAll(".strip-option").forEach(button => {
    button.addEventListener("click", () => {
        if (button.disabled) return;
        const strips = Number.parseInt(button.dataset.strips, 10);
        setStripSelection(strips);
    });
});

/* ---------- API ---------- */

async function fetchStatus() {
    const response = await fetch("/status");
    return response.json();
}

/* ---------- Main Button ---------- */

function updateButton(status) {
console.log(status)
    const button = document.getElementById("startButton");

    button.disabled = true;

    switch (status.state) {
        case "IDLE":
        case "READY_FOR_PHOTO":
            button.innerText = `Take Photo (${status.photos_taken % 3 + 1} of ${status.total_photos})`;
            button.disabled = false;
            break;

        case "COUNTDOWN":
            button.innerText = status.countdown_remaining > 0
                ? status.countdown_remaining.toString()
                : "Smile!";
            break;

        case "CAPTURING_PHOTO":
            button.innerText = "Capturing…";
            break;

        case "PROCESSING":
            button.innerText = "Processing…";
            break;

        case "PRINTING":
            button.innerText = "Printing…";
            break;

        default:
            button.innerText = status.state;
    }
}

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

document
    .getElementById("startButton")
    .addEventListener("click", handleButtonClick);

setInterval(poll, 500);
poll();
