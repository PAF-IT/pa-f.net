// pa-f editor — Quill 2.0 inside Vite bundle
import Quill from 'quill';

const $ = (sel) => document.querySelector(sel);

const state = {
  username: null,
  pages: {},               // path -> {title, date, image, html}
  originalPaths: new Map(),// currentPath -> originalPath (load-time key). Missing => new page.
  initialJson: "",         // JSON of pages at last save (for dirty detection)
  activePath: null,
  quill: null,
  dirtyPaths: new Set(),
  pathValid: true,
};

// ---------- Utilities ----------

function slugify(s) {
  const slug = (s || "")
    .toLowerCase()
    .normalize("NFKD").replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 60);
  return slug || "page";
}

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function snapshot() {
  // Stable JSON snapshot of pages, key-sorted, used for dirty detection.
  const keys = Object.keys(state.pages).sort();
  return JSON.stringify(keys.map((k) => [k, state.pages[k]]));
}

// ---------- API ----------

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
  } catch {
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
    return;
  }
  $("#who").textContent = state.username;
  showApp();
  initQuill();
  await loadSitemap();
}

async function loadSitemap() {
  const data = await api("/api/editor/sitemap");
  state.pages = data.pages || {};
  state.originalPaths = new Map(Object.keys(state.pages).map((p) => [p, p]));
  state.initialJson = snapshot();
  state.dirtyPaths.clear();
  renderPageList();
  updateSaveButton();
  if (state.activePath && state.pages[state.activePath]) {
    showPage(state.activePath);
  } else {
    state.activePath = null;
    $("#page-editor").hidden = true;
    $("#placeholder").hidden = false;
  }
}

// ---------- Sidebar ----------

function renderPageList() {
  const filter = ($("#page-filter").value || "").toLowerCase();
  const ul = $("#page-list");
  ul.innerHTML = "";
  const paths = Object.keys(state.pages).sort();
  for (const path of paths) {
    const page = state.pages[path];
    if (filter && !path.toLowerCase().includes(filter) &&
        !(page.title || "").toLowerCase().includes(filter)) continue;
    const li = document.createElement("li");
    const title = page.title || "(untitled)";
    li.textContent = `${title} — ${path}`;
    li.dataset.path = path;
    if (path === state.activePath) li.classList.add("active");
    if (state.dirtyPaths.has(path)) li.classList.add("dirty");
    if (!state.originalPaths.has(path)) li.classList.add("new");
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
    state.pages[state.activePath].html = state.quill.root.innerHTML;
    markDirty(state.activePath);
  });
}

function showPage(path) {
  state.activePath = path;
  const page = state.pages[path];
  if (!page) return;

  $("#placeholder").hidden = true;
  $("#page-editor").hidden = false;
  $("#page-title").value = page.title || "";
  $("#page-date").value = page.date || "";
  $("#page-path").value = path;
  $("#page-image").value = page.image || "";

  validatePath(path);

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

$("#page-image").addEventListener("input", (e) => {
  if (!state.activePath) return;
  state.pages[state.activePath].image = e.target.value;
  markDirty(state.activePath);
});

// ---------- Path editing ----------

function validatePath(value) {
  const input = $("#page-path");
  const err = $("#path-error");
  const reasons = [];
  if (!value) reasons.push("path required");
  if (value.startsWith("/")) reasons.push("no leading slash");
  if (/\s/.test(value)) reasons.push("no whitespace");
  if (!/\.html?$/.test(value)) reasons.push("must end in .html");
  for (const other of Object.keys(state.pages)) {
    if (other !== state.activePath && other === value) {
      reasons.push("collides with another page");
      break;
    }
  }
  const ok = reasons.length === 0;
  input.classList.toggle("invalid", !ok);
  err.textContent = ok ? "" : reasons.join("; ");
  state.pathValid = ok;
  updateSaveButton();
  return ok;
}

$("#page-path").addEventListener("input", (e) => {
  if (!state.activePath) return;
  const newPath = e.target.value;
  validatePath(newPath);

  // Rename in place, preserving insertion order.
  const oldPath = state.activePath;
  if (newPath === oldPath) return;

  const oldOriginal = state.originalPaths.get(oldPath);
  const renamed = {};
  for (const [k, v] of Object.entries(state.pages)) {
    renamed[k === oldPath ? newPath : k] = v;
  }
  state.pages = renamed;
  state.originalPaths.delete(oldPath);
  if (oldOriginal !== undefined) state.originalPaths.set(newPath, oldOriginal);
  state.dirtyPaths.delete(oldPath);
  state.activePath = newPath;
  markDirty(newPath);
  renderPageList();
});

// ---------- New / delete page ----------

$("#new-page-btn").addEventListener("click", () => {
  const title = prompt("Title for the new page:");
  if (!title) return;
  const trimmed = title.trim();
  if (!trimmed) return;

  let path = `${slugify(trimmed)}.html`;
  let i = 2;
  while (state.pages[path]) {
    path = `${slugify(trimmed)}-${i}.html`;
    i++;
  }

  state.pages[path] = {
    title: trimmed,
    date: todayIso(),
    image: "",
    html: "",
  };
  // originalPaths intentionally does NOT include this — flags it as new.
  markDirty(path);
  showPage(path);
});

$("#delete-page-btn").addEventListener("click", () => {
  if (!state.activePath) return;
  if (!confirm(`Delete page "${state.activePath}"? This removes it from the sitemap on next save.`)) return;
  const path = state.activePath;
  delete state.pages[path];
  state.originalPaths.delete(path);
  state.dirtyPaths.delete(path);
  state.activePath = null;
  $("#page-editor").hidden = true;
  $("#placeholder").hidden = false;
  // The save itself is what triggers the bucket-side delete. Mark dirty via the snapshot diff.
  updateSaveButton();
  renderPageList();
});

// ---------- Dirty / Save ----------

function markDirty(path) {
  state.dirtyPaths.add(path);
  updateSaveButton();
}

function isDirty() {
  return snapshot() !== state.initialJson;
}

function updateSaveButton() {
  const dirty = isDirty();
  $("#save-btn").disabled = !dirty || !state.pathValid;
  $("#status").textContent = !state.pathValid
    ? "Fix path before saving"
    : dirty ? `${state.dirtyPaths.size || "•"} unsaved` : "All changes saved";
}

function renameMap() {
  // {currentPath: originalPath} for entries whose key changed.
  const out = {};
  for (const [cur, orig] of state.originalPaths.entries()) {
    if (cur !== orig) out[cur] = orig;
  }
  return out;
}

$("#save-btn").addEventListener("click", async () => {
  if (!state.pathValid) return;
  $("#save-btn").disabled = true;
  $("#status").textContent = "Saving…";
  try {
    await api("/api/editor/sitemap", {
      method: "PUT",
      body: JSON.stringify({ pages: state.pages, rename_map: renameMap() }),
    });
    // After save, the canonical state matches what's on the server.
    state.originalPaths = new Map(Object.keys(state.pages).map((p) => [p, p]));
    state.initialJson = snapshot();
    state.dirtyPaths.clear();
    renderPageList();
    updateSaveButton();
    toast("Saved.");
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
    updateSaveButton();
  }
});

// ---------- Image upload ----------

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
        method: "POST", credentials: "same-origin", body: fd,
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
  if (isDirty()) { e.preventDefault(); e.returnValue = ""; }
});

// ---------- Go ----------

boot().catch(() => showLogin());
