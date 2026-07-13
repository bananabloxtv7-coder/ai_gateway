// AI Gateway dashboard — talks to the local gateway (OpenAI-compatible).
const $ = (id) => document.getElementById(id);
const state = { base: "", key: "", models: [] };

function headers() {
  const h = { "Content-Type": "application/json" };
  if (state.key) h["Authorization"] = "Bearer " + state.key;
  return h;
}

function setBadge(ok, text) {
  const b = $("conn-badge");
  b.innerHTML =
    `<span class="h-2 w-2 rounded-full ${ok ? "bg-emerald-500" : "bg-gray-400"}"></span> ${text}`;
}

function addBubble(kind, text) {
  const el = document.createElement("div");
  el.className = "bubble " + (kind === "user" ? "bubble-user" : kind === "err" ? "bubble-err" : "bubble-ai");
  el.textContent = text;
  $("chat").appendChild(el);
  $("chat").scrollTop = $("chat").scrollHeight;
  return el;
}

async function connect() {
  state.base = $("baseUrl").value.replace(/\/$/, "");
  state.key = $("gwKey").value.trim();
  $("conn-msg").textContent = "جاري الاتصال…";
  try {
    const r = await fetch(state.base + "/v1/models", { headers: headers() });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    state.models = (data.data || []).map((m) => m.id);
    const sel = $("modelSelect");
    sel.innerHTML = '<option value="">— اختر نموذجاً —</option>' +
      state.models.map((m) => `<option value="${m}">${m}</option>`).join("");
    if (state.models[0]) sel.value = state.models[0];
    setBadge(true, "متصل");
    $("conn-msg").textContent = `تم تحميل ${state.models.length} نموذجاً.`;
    loadStats();
  } catch (e) {
    setBadge(false, "فشل الاتصال");
    $("conn-msg").textContent = "تعذّر الاتصال: " + e.message + " — تأكد أن الخادم يعمل وأن CORS مفعّل.";
  }
}

async function loadStats() {
  if (!state.base) return;
  const box = $("stats");
  try {
    const r = await fetch(state.base + "/admin/stats", { headers: headers() });
    if (!r.ok) throw new Error("HTTP " + r.status);
    const data = await r.json();
    box.innerHTML = "";
    (data.providers || []).forEach((p) => {
      const card = document.createElement("div");
      card.className = "rounded-xl border border-gray-200 p-3 dark:border-gray-800";
      const keyDots = p.usage.map((u, i) => {
        const err = p.errors[i] || 0;
        const color = err > u ? "#ef4444" : u > 0 ? "#10b981" : "#9ca3af";
        return `<span class="keydot" style="background:${color}" title="مفتاح ${i}: ${u} نجاح / ${err} خطأ"></span>`;
      }).join(" ");
      card.innerHTML = `
        <div class="mb-1 flex items-center justify-between">
          <span class="font-medium" dir="ltr">${p.provider}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400">${p.keys} مفاتيح</span>
        </div>
        <div class="mb-2 flex flex-wrap gap-1">${keyDots}</div>
        <div class="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span>نجاح: <b class="text-emerald-600">${p.total_usage}</b></span>
          <span>أخطاء: <b class="text-red-500">${p.total_errors}</b></span>
          <span>نماذج: ${p.models.length}</span>
        </div>`;
      box.appendChild(card);
    });
    if (!box.children.length) box.innerHTML = '<p class="text-xs text-gray-500">لا يوجد مزوّدون.</p>';
  } catch (e) {
    box.innerHTML = `<p class="text-xs text-red-500">تعذّر جلب الإحصائيات: ${e.message}</p>`;
  }
}

async function send() {
  const model = $("modelSelect").value;
  const text = $("prompt").value.trim();
  if (!state.base) return addBubble("err", "اتصل بالبوابة أولاً.");
  if (!model) return addBubble("err", "اختر نموذجاً.");
  if (!text) return;

  addBubble("user", text);
  $("prompt").value = "";
  $("sendBtn").disabled = true;
  const stream = $("streamToggle").checked;
  const body = JSON.stringify({ model, messages: [{ role: "user", content: text }], stream });

  try {
    const r = await fetch(state.base + "/v1/chat/completions", { method: "POST", headers: headers(), body });
    if (!r.ok) {
      const t = await r.text();
      addBubble("err", "خطأ " + r.status + ": " + t.slice(0, 300));
    } else if (stream) {
      const aiEl = addBubble("ai", "");
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        const lines = buf.split("\n");
        buf = lines.pop();
        for (const line of lines) {
          const s = line.trim();
          if (!s.startsWith("data:")) continue;
          const payload = s.slice(5).trim();
          if (payload === "[DONE]") continue;
          try {
            const j = JSON.parse(payload);
            const delta = j.choices?.[0]?.delta?.content || "";
            aiEl.textContent += delta;
            $("chat").scrollTop = $("chat").scrollHeight;
          } catch (_) {}
        }
      }
    } else {
      const j = await r.json();
      addBubble("ai", j.choices?.[0]?.message?.content || "(لا يوجد رد)");
    }
  } catch (e) {
    addBubble("err", "تعذّر الإرسال: " + e.message);
  } finally {
    $("sendBtn").disabled = false;
    loadStats();
  }
}

$("connectBtn").addEventListener("click", connect);
$("refreshStats").addEventListener("click", loadStats);
$("sendBtn").addEventListener("click", send);
$("prompt").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
});
