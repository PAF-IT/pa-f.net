// pa-f editor — vanilla JS + Quill 2.0

const $ = (sel) => document.querySelector(sel);

const state = {
  username: null,
  pages: {},           // path -> {title, date, image, html}
  initialJson: "",     // JSON of pages at last save (for dirty detection)
  activePath: null,
  quill: null,
  dirtyPaths: new Set(),
};

// ---------- API helpers ----------

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: "same-origin",
    headers: { "Content-Type": "application/json", ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401) {
    showLogin();
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const ct = res.headers.get("Content-Type") || "";
  return ct.includes("application/json") ? res.json() : res.text();
}

// ---------- Login flow ----------

function showLogin() {
  $("#app-pane").hidden = true;
  $("#login-pane").hidden = false;
}

function showApp() {
  $("#login-pane").hidden = true;
  $("#app-pane").hidden = false;
}

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  const fd = new FormData(e.target);
  try {
    const data = await api("/api/editor/login", {
      method: "POST",
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
      }),
    });
    state.username = data.username;
    await boot();
  } catch (err) {
    $("#login-error").textContent = "Invalid credentials.";
  }
});

$("#logout-btn").addEventListener("click", async () => {
  if (isDirty() && !confirm("You have unsaved changes. Sign out anyway?")) return;
  await fetch("/api/editor/logout", { method: "POST", credentials: "same-origin" });
  location.reload();
});

// ---------- Boot ----------

async function boot() {
  try {
    const me = await api("/api/editor/me");
    state.username = me.username;
  } catch {
    return; // showLogin already called
  }
  $("#who").textContent = state.username;
  showApp();
  initQuill();
  await loadSitemap();
}

async function loadSitemap() {
  const data = await api("/api/editor/sitemap");
  state.pages = data.pages || {};
  state.initialJson = JSON.stringify(state.pages);
  state.dirtyPaths.clear();
  renderPageList();
  updateSaveButton();
  if (state.activePath && state.pages[state.activePath]) {
    showPage(state.activePath);
  }
}

// ---------- Page list ----------

function renderPageList() {
  const filter = ($("#page-filter").value || "").toLowerCase();
  const ul = $("#page-list");
  ul.innerHTML = "";
  const paths = Object.keys(state.pages).sort();
  for (const path of paths) {
    if (filter && !path.toLowerCase().includes(filter) &&
        !(state.pages[path].title || "").toLowerCase().includes(filter)) {
      continue;
    }
    const li = document.createElement("li");
    const title = state.pages[path].title || "(untitled)";
    li.textContent = `${title} — ${path}`;
    li.dataset.path = path;
    if (path === state.activePath) li.classList.add("active");
    if (state.dirtyPaths.has(path)) li.classList.add("dirty");
    li.addEventListener("click", () => showPage(path));
    ul.appendChild(li);
  }
}

$("#page-filter").addEventListener("input", renderPageList);

// ---------- Editing ----------

let suppressEditorEvents = false;

function initQuill() {
  if (state.quill) return;
  state.quill = new Quill("#quill-editor", {
    theme: "snow",
    modules: {
      toolbar: {
        container: "#quill-toolbar",
        handlers: { image: uploadImageHandler },
      },
    },
  });
  state.quill.on("text-change", () => {
    if (suppressEditorEvents || !state.activePath) return;
    const html = state.quill.root.innerHTML;
    state.pages[state.activePath].html = html;
    markDirty(state.activePath);
  });
}

function showPage(path) {
  state.activePath = path;
  const page = state.pages[path];
  if (!page) return;

  $("#placeholder").hidden = true;
  $("#page-editor").hidden = false;
  $("#page-path").textContent = path;
  $("#page-title").value = page.title || "";
  $("#page-date").value = page.date || "";

  suppressEditorEvents = true;
  state.quill.root.innerHTML = page.html || "";
  suppressEditorEvents = false;

  renderPageList();
}

$("#page-title").addEventListener("input", (e) => {
  if (!state.activePath) return;
  state.pages[state.activePath].title = e.target.value;
  markDirty(state.activePath);
  renderPageList();
});

$("#page-date").addEventListener("input", (e) => {
  if (!state.activePath) return;
  state.pages[state.activePath].date = e.target.value;
  markDirty(state.activePath);
});

function markDirty(path) {
  state.dirtyPaths.add(path);
  updateSaveButton();
}

function isDirty() {
  return state.dirtyPaths.size > 0 ||
    JSON.stringify(state.pages) !== state.initialJson;
}

function updateSaveButton() {
  $("#save-btn").disabled = !isDirty();
  $("#status").textContent = isDirty()
    ? `${state.dirtyPaths.size} unsaved`
    : "All changes saved";
}

// ---------- Save ----------

$("#save-btn").addEventListener("click", async () => {
  $("#save-btn").disabled = true;
  $("#status").textContent = "Saving…";
  try {
    await api("/api/editor/sitemap", {
      method: "PUT",
      body: JSON.stringify({ pages: state.pages }),
    });
    state.initialJson = JSON.stringify(state.pages);
    state.dirtyPaths.clear();
    renderPageList();
    updateSaveButton();
    toast("Saved.");
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
    updateSaveButton();
  }
});

// ---------- Image upload (Quill toolbar handler) ----------

function uploadImageHandler() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = "image/png,image/jpeg,image/gif,image/webp";
  input.onchange = async () => {
    const file = input.files?.[0];
    if (!file) return;
    const caption = prompt("Caption (optional):", "") || "";
    const fd = new FormData();
    fd.append("file", file);
    fd.append("caption", caption);
    toast("Uploading…");
    try {
      const res = await fetch("/api/editor/upload", {
        method: "POST",
        credentials: "same-origin",
        body: fd,
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      insertImage(data.url, data.caption);
      toast("Image uploaded.");
    } catch (err) {
      toast(`Upload failed: ${err.message}`, true);
    }
  };
  input.click();
}

function insertImage(url, caption) {
  const range = state.quill.getSelection(true);
  const index = range ? range.index : state.quill.getLength();
  state.quill.insertEmbed(index, "image", url, "user");
  let next = index + 1;
  if (caption) {
    state.quill.insertText(next, "\n", "user");
    state.quill.insertText(next + 1, caption, { italic: true }, "user");
    next += 1 + caption.length;
  }
  state.quill.setSelection(next, 0);
}

// ---------- Toast + unload guard ----------

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.toggle("error", isError);
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 2500);
}

window.addEventListener("beforeunload", (e) => {
  if (isDirty()) {
    e.preventDefault();
    e.returnValue = "";
  }
});

// ---------- Go ----------

boot().catch(() => showLogin());
