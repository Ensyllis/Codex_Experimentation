const basePath = document.querySelector("meta[name='base-path']").content;
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-message");
const finishButton = document.getElementById("finish-interview");
const resultsSection = document.getElementById("results");
const resultsProfile = document.getElementById("results-profile");
const resultsJson = document.getElementById("results-json");
const themeToggle = document.getElementById("theme-toggle");

let sessionId = null;

/* ─── Dark mode ─── */
const applyTheme = (theme) => {
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("lpi-theme", theme);
};

themeToggle.addEventListener("click", () => {
  const current = document.documentElement.getAttribute("data-theme");
  applyTheme(current === "dark" ? "light" : "dark");
});

// Restore saved preference or respect system preference
const saved = localStorage.getItem("lpi-theme");
if (saved) {
  applyTheme(saved);
} else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
  applyTheme("dark");
}

/* ─── Chat helpers ─── */
const addMessage = (role, text) => {
  const entry = document.createElement("div");
  entry.className = `chat__message chat__message--${role}`;
  const p = document.createElement("p");
  p.textContent = text;
  entry.appendChild(p);
  chatLog.appendChild(entry);
  chatLog.scrollTop = chatLog.scrollHeight;
};

const showTyping = () => {
  const el = document.createElement("div");
  el.className = "chat__typing";
  el.id = "typing-indicator";
  el.innerHTML =
    '<span class="chat__typing-dot"></span>' +
    '<span class="chat__typing-dot"></span>' +
    '<span class="chat__typing-dot"></span>';
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
};

const hideTyping = () => {
  const el = document.getElementById("typing-indicator");
  if (el) el.remove();
};

/* ─── API calls ─── */
const sendMessage = async (message) => {
  const response = await fetch(`${basePath}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  if (!response.ok) {
    throw new Error("Unable to send message.");
  }
  const data = await response.json();
  sessionId = data.session_id;
  return data.message;
};

/* ─── Profile rendering ─── */
const DIMENSION_LABELS = {
  relationship_with_family: "Relationship with Family",
  relationship_with_self: "Relationship with Self",
  sources_of_escape_and_fun: "Where They Go to Escape & Have Fun",
  what_makes_them_happy: "What Makes Them Happy",
  what_makes_them_sad: "What Makes Them Sad",
  what_they_value_in_people: "What They Value in Other People",
  values_above_average: "Values They Hold More Than Most",
  values_below_average: "Values They Care Less About Than Most",
  emotional_awareness: "How They Handle Their Emotions",
  identity_and_self_image: "How They See Themselves",
  moral_framework: "Their Sense of Right and Wrong",
  response_to_adversity: "How They Handle Adversity",
  need_for_control: "Their Need for Control & Predictability",
  hidden_drivers: "What Drives Them Under the Surface",
};

const confidenceLabel = (val) => {
  if (val >= 0.7) return { text: "High confidence", cls: "confidence-high" };
  if (val >= 0.4) return { text: "Moderate confidence", cls: "confidence-med" };
  return { text: "Low confidence", cls: "confidence-low" };
};

const renderProfile = (data) => {
  const dims = data.dimensions;
  if (!dims || typeof dims !== "object") {
    resultsJson.style.display = "block";
    resultsJson.textContent = JSON.stringify(data, null, 2);
    return;
  }

  // Group dimensions into sections
  const sections = [
    {
      title: "Relationships & Connection",
      keys: ["relationship_with_family", "relationship_with_self", "what_they_value_in_people"],
    },
    {
      title: "Emotional Landscape",
      keys: ["what_makes_them_happy", "what_makes_them_sad", "emotional_awareness"],
    },
    {
      title: "Values & Worldview",
      keys: ["values_above_average", "values_below_average", "moral_framework"],
    },
    {
      title: "Inner World & Drivers",
      keys: [
        "sources_of_escape_and_fun",
        "identity_and_self_image",
        "response_to_adversity",
        "need_for_control",
        "hidden_drivers",
      ],
    },
  ];

  let html = "";

  for (const section of sections) {
    let cards = "";
    for (const key of section.keys) {
      const dim = dims[key];
      if (!dim || !dim.assessment) continue;

      const conf = confidenceLabel(dim.confidence || 0);
      let evidenceHtml = "";
      if (dim.supporting_evidence && dim.supporting_evidence.length > 0) {
        const quotes = dim.supporting_evidence
          .map((q) => `<p class="profile-card__quote">"${q}"</p>`)
          .join("");
        evidenceHtml = `<div class="profile-card__evidence">${quotes}</div>`;
      }

      cards += `
        <div class="profile-card">
          <div class="profile-card__label">${DIMENSION_LABELS[key] || key}</div>
          <p class="profile-card__text">${dim.assessment}</p>
          ${evidenceHtml}
          <span class="profile-card__confidence ${conf.cls}">${conf.text}</span>
        </div>`;
    }
    if (cards) {
      html += `
        <div class="profile-section">
          <div class="profile-section__title">${section.title}</div>
          ${cards}
        </div>`;
    }
  }

  // Render any remaining dimensions not in sections
  const sectionKeys = new Set(sections.flatMap((s) => s.keys));
  let extras = "";
  for (const [key, dim] of Object.entries(dims)) {
    if (sectionKeys.has(key) || !dim || !dim.assessment) continue;
    const conf = confidenceLabel(dim.confidence || 0);
    extras += `
      <div class="profile-card">
        <div class="profile-card__label">${DIMENSION_LABELS[key] || key}</div>
        <p class="profile-card__text">${dim.assessment}</p>
        <span class="profile-card__confidence ${conf.cls}">${conf.text}</span>
      </div>`;
  }
  if (extras) {
    html += `
      <div class="profile-section">
        <div class="profile-section__title">Additional Observations</div>
        ${extras}
      </div>`;
  }

  if (html) {
    resultsProfile.innerHTML = html;
  } else {
    resultsJson.style.display = "block";
    resultsJson.textContent = JSON.stringify(data, null, 2);
  }
};

const requestExtract = async () => {
  if (!sessionId) {
    resultsProfile.innerHTML =
      '<p class="profile-card__text">Start the interview before requesting results.</p>';
    resultsSection.classList.add("results--visible");
    return;
  }

  finishButton.disabled = true;
  finishButton.textContent = "Analyzing...";

  try {
    const response = await fetch(`${basePath}/api/extract`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId }),
    });
    if (!response.ok) {
      resultsProfile.innerHTML =
        '<p class="profile-card__text">Unable to extract interview profile.</p>';
      resultsSection.classList.add("results--visible");
      return;
    }
    const data = await response.json();
    renderProfile(data);
    resultsSection.classList.add("results--visible");
  } finally {
    finishButton.disabled = false;
    finishButton.textContent = "Finish Interview";
  }
};

/* ─── Event listeners ─── */
chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) return;

  addMessage("user", message);
  chatInput.value = "";
  chatInput.disabled = true;
  showTyping();

  try {
    const reply = await sendMessage(message);
    hideTyping();
    addMessage("assistant", reply);
  } catch {
    hideTyping();
    addMessage("assistant", "Something went wrong. Please try again.");
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
  }
});

finishButton.addEventListener("click", async () => {
  await requestExtract();
});

/* ─── Opening message ─── */
addMessage(
  "assistant",
  "Hey, welcome. There are no right or wrong answers here \u2014 just talk to me like you would a friend. What\u2019s been on your mind lately?"
);
