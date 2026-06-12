const apiKeyInput = document.querySelector("#apiKey");
const userIdInput = document.querySelector("#userId");
const questionInput = document.querySelector("#question");
const askButton = document.querySelector("#askButton");
const clearButton = document.querySelector("#clearButton");
const healthDot = document.querySelector("#healthDot");
const healthText = document.querySelector("#healthText");
const answerText = document.querySelector("#answerText");
const responseMeta = document.querySelector("#responseMeta");
const sourcesEl = document.querySelector("#sources");
const sourceCount = document.querySelector("#sourceCount");

apiKeyInput.value = localStorage.getItem("agentApiKey") || "";

function setStatus(kind, text) {
  healthDot.className = `dot ${kind}`;
  healthText.textContent = text;
}

function renderSources(sources) {
  sourceCount.textContent = String(sources.length);
  sourcesEl.innerHTML = "";
  for (const source of sources) {
    const metadata = source.metadata || {};
    const item = document.createElement("article");
    item.className = "source-item";

    const title = document.createElement("p");
    title.className = "source-title";
    title.textContent = metadata.source || "Unknown source";

    const meta = document.createElement("p");
    meta.className = "source-meta";
    meta.textContent = `${metadata.path || "local corpus"} · score ${source.score ?? "n/a"}`;

    const snippet = document.createElement("p");
    snippet.className = "source-snippet";
    snippet.textContent = (source.content || "").slice(0, 280);

    item.append(title, meta, snippet);
    sourcesEl.appendChild(item);
  }
}

async function checkService() {
  try {
    const health = await fetch("/health");
    const ready = await fetch("/ready");
    if (health.ok && ready.ok) {
      const data = await ready.json();
      setStatus("ok", `Ready · ${data.storage}`);
    } else if (health.ok) {
      setStatus("bad", "Service online · Redis not ready");
    } else {
      setStatus("bad", "Service unavailable");
    }
  } catch (_error) {
    setStatus("bad", "Service unreachable");
  }
}

async function ask() {
  const apiKey = apiKeyInput.value.trim();
  const userId = userIdInput.value.trim();
  const question = questionInput.value.trim();

  localStorage.setItem("agentApiKey", apiKey);
  askButton.disabled = true;
  askButton.textContent = "Asking";
  responseMeta.textContent = "Waiting for response";

  try {
    const response = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-API-Key": apiKey,
      },
      body: JSON.stringify({ user_id: userId, question }),
    });
    const data = await response.json();
    if (!response.ok) {
      answerText.textContent = data.detail ? JSON.stringify(data.detail, null, 2) : "Request failed";
      responseMeta.textContent = `HTTP ${response.status}`;
      renderSources([]);
      return;
    }
    answerText.textContent = data.answer;
    responseMeta.textContent = `${data.model} · ${data.served_by}`;
    renderSources(data.sources || []);
  } catch (error) {
    answerText.textContent = error.message;
    responseMeta.textContent = "Request error";
    renderSources([]);
  } finally {
    askButton.disabled = false;
    askButton.textContent = "Ask";
    checkService();
  }
}

askButton.addEventListener("click", ask);
clearButton.addEventListener("click", () => {
  questionInput.value = "";
  answerText.textContent = "";
  responseMeta.textContent = "Cleared";
  renderSources([]);
});

checkService();
