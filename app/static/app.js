const basePath = document.querySelector("meta[name='base-path']").content;
const chatLog = document.getElementById("chat-log");
const chatForm = document.getElementById("chat-form");
const chatInput = document.getElementById("chat-message");
const finishButton = document.getElementById("finish-interview");
const resultsSection = document.getElementById("results");
const resultsJson = document.getElementById("results-json");

let sessionId = null;

const addMessage = (role, text) => {
  const entry = document.createElement("div");
  entry.className = `chat__message chat__message--${role}`;
  entry.innerHTML = `
    <span class="chat__role">${role === "user" ? "You" : "Interviewer"}</span>
    <p>${text}</p>
  `;
  chatLog.appendChild(entry);
  chatLog.scrollTop = chatLog.scrollHeight;
};

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

const requestExtract = async () => {
  if (!sessionId) {
    resultsJson.textContent = "Start the interview before requesting results.";
    resultsSection.classList.add("results--visible");
    return;
  }
  const response = await fetch(`${basePath}/api/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!response.ok) {
    resultsJson.textContent = "Unable to extract interview profile.";
    resultsSection.classList.add("results--visible");
    return;
  }
  const data = await response.json();
  resultsJson.textContent = JSON.stringify(data, null, 2);
  resultsSection.classList.add("results--visible");
};

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = chatInput.value.trim();
  if (!message) {
    return;
  }
  addMessage("user", message);
  chatInput.value = "";
  try {
    const reply = await sendMessage(message);
    addMessage("assistant", reply);
  } catch (error) {
    addMessage("assistant", "Something went wrong sending that message.");
  }
});

finishButton.addEventListener("click", async () => {
  await requestExtract();
});

addMessage(
  "assistant",
  "Welcome. We can start with anything that has felt meaningful or energizing lately."
);
