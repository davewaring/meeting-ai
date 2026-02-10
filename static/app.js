// Meeting AI — Frontend logic

let ws = null;
let timerInterval = null;
let startTime = null;

const transcript = document.getElementById("transcript");
const statusBadge = document.getElementById("status-badge");
const timerEl = document.getElementById("timer");
const entryCount = document.getElementById("entry-count");
const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");

// --- WebSocket ---

function connectWebSocket() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${protocol}//${location.host}/ws/transcript`);

    ws.onopen = () => console.log("WebSocket connected");

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "transcript") {
            addTranscriptEntry(data.entry);
        }
    };

    ws.onclose = () => {
        console.log("WebSocket closed");
        ws = null;
    };

    ws.onerror = (err) => console.error("WebSocket error:", err);
}

function disconnectWebSocket() {
    if (ws) {
        ws.close();
        ws = null;
    }
}

// --- Transcript display ---

let entryTotal = 0;

function addTranscriptEntry(entry) {
    // Remove placeholder on first entry
    const placeholder = transcript.querySelector(".placeholder");
    if (placeholder) placeholder.remove();

    const div = document.createElement("div");
    div.className = "transcript-entry";

    const ts = document.createElement("span");
    ts.className = "timestamp";
    ts.textContent = formatMs(entry.start_ms);

    const text = document.createElement("span");
    text.className = "text";
    text.textContent = entry.text;

    div.appendChild(ts);
    div.appendChild(text);
    transcript.appendChild(div);

    // Auto-scroll to bottom
    transcript.scrollTop = transcript.scrollHeight;

    // Update count
    entryTotal++;
    entryCount.textContent = `${entryTotal} entries`;
}

function formatMs(ms) {
    const totalSec = Math.floor(ms / 1000);
    const min = Math.floor(totalSec / 60);
    const sec = totalSec % 60;
    return `${String(min).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

// --- Timer ---

function startTimer() {
    startTime = Date.now();
    timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const hrs = Math.floor(elapsed / 3600);
        const min = Math.floor((elapsed % 3600) / 60);
        const sec = elapsed % 60;
        timerEl.textContent =
            String(hrs).padStart(2, "0") + ":" +
            String(min).padStart(2, "0") + ":" +
            String(sec).padStart(2, "0");
    }, 1000);
}

function stopTimer() {
    if (timerInterval) {
        clearInterval(timerInterval);
        timerInterval = null;
    }
}

// --- UI State ---

function setUIState(state) {
    statusBadge.textContent = state.charAt(0).toUpperCase() + state.slice(1);
    statusBadge.className = `badge badge-${state}`;

    if (state === "recording") {
        btnStart.disabled = true;
        btnStop.disabled = false;
    } else if (state === "processing") {
        btnStart.disabled = true;
        btnStop.disabled = true;
    } else {
        btnStart.disabled = false;
        btnStop.disabled = true;
    }
}

// --- API calls ---

async function startRecording() {
    try {
        const res = await fetch("/api/start", { method: "POST" });
        if (!res.ok) {
            const err = await res.json();
            alert(err.error || "Failed to start");
            return;
        }

        // Clear previous transcript
        transcript.innerHTML = "";
        entryTotal = 0;
        entryCount.textContent = "0 entries";
        timerEl.textContent = "00:00:00";

        setUIState("recording");
        startTimer();
        connectWebSocket();
    } catch (e) {
        alert("Error starting: " + e.message);
    }
}

async function stopRecording() {
    setUIState("processing");
    stopTimer();
    disconnectWebSocket();

    try {
        const res = await fetch("/api/stop", { method: "POST" });
        const data = await res.json();
        setUIState("idle");

        if (data.vtt_path) {
            const info = document.createElement("div");
            info.className = "transcript-entry";
            info.innerHTML = `<span class="timestamp">--:--</span><span class="text" style="color:#4ecca3;">Transcript saved: ${data.vtt_path}</span>`;
            transcript.appendChild(info);
            transcript.scrollTop = transcript.scrollHeight;
        }
    } catch (e) {
        setUIState("idle");
        alert("Error stopping: " + e.message);
    }
}

// --- Init ---

// Check initial status
fetch("/api/status")
    .then(r => r.json())
    .then(data => setUIState(data.state))
    .catch(() => setUIState("idle"));
