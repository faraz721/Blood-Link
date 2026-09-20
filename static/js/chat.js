document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("chatForm");
  const input = document.getElementById("chatInput");
  const messages = document.getElementById("chatMessages");
  if (!form) return;

  const append = (text, who) => {
    const div = document.createElement("div");
    div.className = `msg msg-${who}`;
    div.textContent = text;
    messages.appendChild(div);
    messages.scrollTop = messages.scrollHeight;
  };

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const q = (input.value || "").trim();
    if (!q) return;

    append(q, "user");
    input.value = "";
    input.disabled = true;

    const loading = document.createElement("div");
    loading.className = "msg msg-ai";
    loading.textContent = "Thinking...";
    messages.appendChild(loading);
    messages.scrollTop = messages.scrollHeight;

    try {
      const res = await fetch("/api/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: q }),
      });
      const data = await res.json();
      loading.remove();
      if (data.ok) {
        append(data.answer, "ai");
      } else {
        append(data.error || "Something went wrong.", "ai");
      }
    } catch (err) {
      loading.remove();
      append("Unable to reach AI service. Please try again later.", "ai");
    } finally {
      input.disabled = false;
      input.focus();
    }
  });
});