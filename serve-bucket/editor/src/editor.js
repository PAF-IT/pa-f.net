// pa-f editor — Quill 2.0 inside Vite bundle
import Quill from 'quill';

const $ = (sel) => document.querySelector(sel);
const META_COLLAPSED_KEY = 'paf-editor-meta-collapsed';

const state = {
  username: null,
  pages: {},
  originalPaths: new Map(),
  initialJson: '',
  activePath: null,
  quill: null,
  dirtyPaths: new Set(),
  pathValid: true,
  editingImage: null, // {imgEl, captionEl|null} while modal is open
};

// ---------- Utilities ----------

function slugify(s) {
  const slug = (s || '')
    .toLowerCase()
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);
  return slug || 'page';
}

function todayIso() { return new Date().toISOString().slice(0, 10); }

function snapshot() {
  const keys = Object.keys(state.pages).sort();
  return JSON.stringify(keys.map((k) => [k, state.pages[k]]));
}

// ---------- API ----------

async function api(path, opts = {}) {
  const res = await fetch(path, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (res.status === 401 || res.status === 403) {
    showDenied();
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  const ct = res.headers.get('Content-Type') || '';
  return ct.includes('application/json') ? res.json() : res.text();
}

async function uploadFile(file, caption = '') {
  const fd = new FormData();
  fd.append('file', file);
  fd.append('caption', caption);
  const res = await fetch('/api/editor/upload', {
    method: 'POST', credentials: 'same-origin', body: fd,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function pickImageFile() {
  return new Promise((resolve) => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/png,image/jpeg,image/gif,image/webp';
    input.onchange = () => resolve(input.files?.[0] || null);
    input.oncancel = () => resolve(null);
    input.click();
  });
}

// ---------- Access ----------

function showDenied() { $('#app-pane').hidden = true; $('#denied-pane').hidden = false; }
function showApp() { $('#denied-pane').hidden = true; $('#app-pane').hidden = false; }

// ---------- Boot ----------

async function boot() {
  try {
    const me = await api('/api/editor/me');
    state.username = me.username;
  } catch { return; }
  $('#who').textContent = state.username;
  showApp();
  initQuill();
  initMetaPane();
  await loadSitemap();
}

async function loadSitemap() {
  const data = await api('/api/editor/sitemap');
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
    $('#page-editor').hidden = true;
    $('#placeholder').hidden = false;
  }
}

// ---------- Sidebar ----------

function renderPageList() {
  const filter = ($('#page-filter').value || '').toLowerCase();
  const ul = $('#page-list');
  ul.innerHTML = '';
  for (const path of Object.keys(state.pages).sort()) {
    const page = state.pages[path];
    if (filter && !path.toLowerCase().includes(filter) &&
        !(page.title || '').toLowerCase().includes(filter)) continue;
    const li = document.createElement('li');
    li.textContent = `${page.title || '(untitled)'} — ${path}`;
    li.dataset.path = path;
    if (path === state.activePath) li.classList.add('active');
    if (state.dirtyPaths.has(path)) li.classList.add('dirty');
    if (!state.originalPaths.has(path)) li.classList.add('new');
    li.addEventListener('click', () => showPage(path));
    ul.appendChild(li);
  }
}

$('#page-filter').addEventListener('input', renderPageList);

// ---------- Quill setup ----------

let suppressEditorEvents = false;

function initQuill() {
  if (state.quill) return;
  state.quill = new Quill('#quill-editor', {
    theme: 'snow',
    modules: {
      toolbar: {
        container: '#quill-toolbar',
        handlers: { image: insertNewImageHandler, link: handleLinkInsertion },
      },
    },
  });
  state.quill.on('text-change', () => {
    if (suppressEditorEvents || !state.activePath) return;
    state.pages[state.activePath].html = state.quill.root.innerHTML;
    markDirty(state.activePath);
  });

  // Delegated click on inline images opens the edit modal.
  state.quill.root.addEventListener('click', (e) => {
    const img = e.target.closest('img');
    if (!img || !state.quill.root.contains(img)) return;
    e.preventDefault();
    openImageModal(img);
  });
}

// Canonicalize a link the user typed into the link prompt.
// Returns { url, resolved }: url is what we store in the href, resolved is
// whether it points at a known sitemap page (so we can warn for misses).
function canonicalizeLink(raw) {
  const input = (raw || '').trim();
  if (!input) return { url: '', resolved: true };
  // Absolute / special schemes and pure fragments / queries: pass through.
  if (/^(https?:|mailto:|tel:|\/\/|#|\?)/i.test(input)) {
    return { url: input, resolved: true };
  }
  // Split off query/fragment so we only normalize the path.
  const m = input.match(/^([^?#]*)([?#].*)?$/);
  let path = m[1];
  const tail = m[2] || '';
  path = path.replace(/^\/+/, '');
  // Don't touch index.html; otherwise strip trailing .html
  if (!(path === 'index.html' || path.endsWith('/index.html')) && path.endsWith('.html')) {
    path = path.slice(0, -'.html'.length);
  }
  const resolved = Object.prototype.hasOwnProperty.call(state.pages, path);
  return { url: `/${path}${tail}`, resolved };
}

function handleLinkInsertion(value) {
  if (!value) {
    this.quill.format('link', false);
    return;
  }
  const range = this.quill.getSelection(true);
  // Pre-fill with the current link's href, if any.
  let existing = '';
  if (range) {
    const fmt = this.quill.getFormat(range);
    if (typeof fmt.link === 'string') existing = fmt.link;
  }
  const raw = window.prompt('Link URL (or page path):', existing);
  if (raw === null) return; // user cancelled
  if (!raw.trim()) {
    this.quill.format('link', false);
    return;
  }
  const { url, resolved } = canonicalizeLink(raw);
  this.quill.format('link', url);
  if (!resolved) toast(`Warning: "${url}" does not match any known page.`, true);
}

function showPage(path) {
  state.activePath = path;
  const page = state.pages[path];
  if (!page) return;

  $('#placeholder').hidden = true;
  $('#page-editor').hidden = false;
  $('#page-title').value = page.title || '';
  $('#page-date').value = page.date || '';
  $('#page-path').value = path;
  updateHeroDisplay();

  validatePath(path);

  suppressEditorEvents = true;
  state.quill.setContents([], 'silent');
  if (page.html) state.quill.clipboard.dangerouslyPasteHTML(0, page.html, 'silent');
  suppressEditorEvents = false;

  renderPageList();
}

// ---------- Meta inputs ----------

$('#page-title').addEventListener('input', (e) => {
  if (!state.activePath) return;
  state.pages[state.activePath].title = e.target.value;
  markDirty(state.activePath);
  renderPageList();
});

$('#page-date').addEventListener('input', (e) => {
  if (!state.activePath) return;
  state.pages[state.activePath].date = e.target.value;
  markDirty(state.activePath);
});

// Hero image
function updateHeroDisplay() {
  const page = state.pages[state.activePath];
  const url = page?.image || '';
  const thumb = $('#hero-thumb');
  const clear = $('#hero-clear-btn');
  const btn = $('#hero-upload-btn');
  if (url) {
    thumb.src = url;
    thumb.hidden = false;
    clear.hidden = false;
    btn.textContent = 'Replace hero image…';
  } else {
    thumb.removeAttribute('src');
    thumb.hidden = true;
    clear.hidden = true;
    btn.textContent = 'Upload hero image…';
  }
}

$('#hero-upload-btn').addEventListener('click', async () => {
  if (!state.activePath) return;
  const file = await pickImageFile();
  if (!file) return;
  toast('Uploading…');
  try {
    const data = await uploadFile(file, '');
    state.pages[state.activePath].image = data.url;
    markDirty(state.activePath);
    updateHeroDisplay();
    toast('Hero image set.');
  } catch (err) {
    toast(`Upload failed: ${err.message}`, true);
  }
});

$('#hero-clear-btn').addEventListener('click', () => {
  if (!state.activePath) return;
  state.pages[state.activePath].image = '';
  markDirty(state.activePath);
  updateHeroDisplay();
});

// ---------- Meta pane collapse ----------

function initMetaPane() {
  const pane = $('#meta-pane');
  const toggle = $('#meta-toggle');
  const collapsed = localStorage.getItem(META_COLLAPSED_KEY) === '1';
  pane.classList.toggle('collapsed', collapsed);
  toggle.textContent = collapsed ? '‹' : '›';
  toggle.addEventListener('click', () => {
    const nowCollapsed = !pane.classList.contains('collapsed');
    pane.classList.toggle('collapsed', nowCollapsed);
    toggle.textContent = nowCollapsed ? '‹' : '›';
    localStorage.setItem(META_COLLAPSED_KEY, nowCollapsed ? '1' : '0');
  });
}

// ---------- Path editing ----------

function validatePath(value) {
  const input = $('#page-path');
  const err = $('#path-error');
  const reasons = [];
  if (!value) reasons.push('path required');
  if (value.startsWith('/')) reasons.push('no leading slash');
  if (value.endsWith('/')) reasons.push('no trailing slash');
  if (/\s/.test(value)) reasons.push('no whitespace');
  // Extensionless paths only (URL canonical form). `index.html` is the one
  // exception — it's the home-page key the backend preserves.
  const lastSeg = value.split('/').pop() || '';
  const isIndex = value === 'index.html' || value.endsWith('/index.html');
  if (!isIndex && lastSeg.includes('.')) reasons.push('no file extension');
  for (const other of Object.keys(state.pages)) {
    if (other !== state.activePath && other === value) {
      reasons.push('collides with another page');
      break;
    }
  }
  const ok = reasons.length === 0;
  input.classList.toggle('invalid', !ok);
  err.textContent = ok ? '' : reasons.join('; ');
  state.pathValid = ok;
  updateSaveButton();
  return ok;
}

$('#page-path').addEventListener('input', (e) => {
  if (!state.activePath) return;
  const newPath = e.target.value;
  validatePath(newPath);
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

$('#new-page-btn').addEventListener('click', () => {
  const title = prompt('Title for the new page:');
  if (!title) return;
  const trimmed = title.trim();
  if (!trimmed) return;
  let path = slugify(trimmed);
  let i = 2;
  while (state.pages[path]) { path = `${slugify(trimmed)}-${i}`; i++; }
  state.pages[path] = { title: trimmed, date: todayIso(), image: '', html: '' };
  markDirty(path);
  showPage(path);
});

$('#delete-page-btn').addEventListener('click', () => {
  if (!state.activePath) return;
  if (!confirm(`Delete page "${state.activePath}"? This removes it from the sitemap on next save.`)) return;
  const path = state.activePath;
  delete state.pages[path];
  state.originalPaths.delete(path);
  state.dirtyPaths.delete(path);
  state.activePath = null;
  $('#page-editor').hidden = true;
  $('#placeholder').hidden = false;
  updateSaveButton();
  renderPageList();
});

// ---------- Dirty / Save ----------

function markDirty(path) { state.dirtyPaths.add(path); updateSaveButton(); }

function isDirty() { return snapshot() !== state.initialJson; }

function updateSaveButton() {
  const dirty = isDirty();
  $('#save-btn').disabled = !dirty || !state.pathValid;
  $('#status').textContent = !state.pathValid
    ? 'Fix path before saving'
    : dirty ? `${state.dirtyPaths.size || '•'} unsaved` : 'All changes saved';
}

function renameMap() {
  const out = {};
  for (const [cur, orig] of state.originalPaths.entries()) {
    if (cur !== orig) out[cur] = orig;
  }
  return out;
}

$('#save-btn').addEventListener('click', async () => {
  if (!state.pathValid) return;
  $('#save-btn').disabled = true;
  $('#status').textContent = 'Saving…';
  try {
    await api('/api/editor/sitemap', {
      method: 'PUT',
      body: JSON.stringify({ pages: state.pages, rename_map: renameMap() }),
    });
    state.originalPaths = new Map(Object.keys(state.pages).map((p) => [p, p]));
    state.initialJson = snapshot();
    state.dirtyPaths.clear();
    renderPageList();
    updateSaveButton();
    toast('Saved.');
  } catch (err) {
    toast(`Save failed: ${err.message}`, true);
    updateSaveButton();
  }
});

// ---------- Image insertion (toolbar) ----------

async function insertNewImageHandler() {
  const file = await pickImageFile();
  if (!file) return;
  const caption = prompt('Caption (optional):', '') || '';
  toast('Uploading…');
  try {
    const data = await uploadFile(file, caption);
    insertImageAtCursor(data.url, data.caption || caption);
    toast('Image uploaded.');
  } catch (err) {
    toast(`Upload failed: ${err.message}`, true);
  }
}

function insertImageAtCursor(url, caption) {
  const range = state.quill.getSelection(true);
  const index = range ? range.index : state.quill.getLength();
  state.quill.insertEmbed(index, 'image', url, 'user');
  let next = index + 1;
  if (caption) {
    state.quill.insertText(next, '\n', 'user');
    state.quill.insertText(next + 1, caption, { italic: true }, 'user');
    next += 1 + caption.length;
  }
  state.quill.setSelection(next, 0);
}

// ---------- Image edit modal ----------

const imageModal = $('#image-modal');
const imageModalPreview = $('#image-modal-preview');
const imageModalCaption = $('#image-modal-caption');

function isCaptionBlock(el) {
  // <p><em>caption text</em></p> — exactly one <em> child, no other content.
  if (!el || el.tagName !== 'P') return false;
  const kids = Array.from(el.childNodes).filter((n) =>
    !(n.nodeType === Node.TEXT_NODE && !n.textContent.trim())
  );
  if (kids.length !== 1) return false;
  const only = kids[0];
  return only.nodeType === Node.ELEMENT_NODE && only.tagName === 'EM';
}

function findCaptionEl(imgEl) {
  // Walk up to the block parent inside the editor root.
  let block = imgEl;
  while (block && block.parentElement !== state.quill.root) block = block.parentElement;
  if (!block) return null;
  const next = block.nextElementSibling;
  return isCaptionBlock(next) ? next : null;
}

function openImageModal(imgEl) {
  state.editingImage = { imgEl, captionEl: findCaptionEl(imgEl) };
  imageModalPreview.src = imgEl.getAttribute('src') || '';
  imageModalCaption.value = state.editingImage.captionEl?.textContent.trim() || '';
  imageModal.hidden = false;
  setTimeout(() => imageModalCaption.focus(), 0);
}

function closeImageModal() {
  imageModal.hidden = true;
  state.editingImage = null;
}

function getBlotIndex(el) {
  const blot = Quill.find(el);
  if (!blot) return null;
  return state.quill.getIndex(blot);
}

function getBlockLength(el) {
  // Length of the block (paragraph) in the Quill document, including its trailing \n.
  const blot = Quill.find(el);
  if (!blot) return 0;
  return blot.length();
}

function applyCaptionEdit(newCaption) {
  const { imgEl, captionEl } = state.editingImage;
  newCaption = (newCaption || '').trim();
  const quill = state.quill;

  // Find the image's block to know where the caption block would go.
  let imgBlock = imgEl;
  while (imgBlock && imgBlock.parentElement !== quill.root) imgBlock = imgBlock.parentElement;
  if (!imgBlock) return;
  const imgBlockIdx = getBlotIndex(imgBlock);
  const imgBlockLen = getBlockLength(imgBlock);
  const afterImgBlock = imgBlockIdx + imgBlockLen; // start of the next block

  // Delete the existing caption block (text + trailing \n) if present.
  if (captionEl) {
    const capIdx = getBlotIndex(captionEl);
    const capLen = getBlockLength(captionEl);
    if (capIdx !== null) quill.deleteText(capIdx, capLen, 'user');
  }

  // Insert a fresh caption block if non-empty.
  if (newCaption) {
    const insertAt = afterImgBlock; // same position whether or not we just deleted
    quill.insertText(insertAt, newCaption, { italic: true }, 'user');
    quill.insertText(insertAt + newCaption.length, '\n', 'user');
  }
}

function applyImageReplace(newUrl) {
  const { imgEl } = state.editingImage;
  const idx = getBlotIndex(imgEl);
  if (idx === null) return;
  state.quill.deleteText(idx, 1, 'user');
  state.quill.insertEmbed(idx, 'image', newUrl, 'user');
}

function applyImageRemove() {
  const { imgEl, captionEl } = state.editingImage;
  const quill = state.quill;
  // Delete caption first (positions of earlier ops would shift otherwise).
  if (captionEl) {
    const capIdx = getBlotIndex(captionEl);
    const capLen = getBlockLength(captionEl);
    if (capIdx !== null) quill.deleteText(capIdx, capLen, 'user');
  }
  const idx = getBlotIndex(imgEl);
  if (idx !== null) quill.deleteText(idx, 1, 'user');
}

$('#image-modal-save').addEventListener('click', () => {
  if (!state.editingImage) return;
  applyCaptionEdit(imageModalCaption.value);
  closeImageModal();
});

$('#image-modal-cancel').addEventListener('click', closeImageModal);

imageModal.addEventListener('click', (e) => {
  if (e.target.dataset.close === '1') closeImageModal();
});

document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && !imageModal.hidden) closeImageModal();
});

$('#image-modal-replace').addEventListener('click', async () => {
  if (!state.editingImage) return;
  const file = await pickImageFile();
  if (!file) return;
  toast('Uploading…');
  try {
    const data = await uploadFile(file, '');
    // Apply caption first (uses current editingImage references), then swap image.
    applyCaptionEdit(imageModalCaption.value);
    // After caption edit, the captionEl reference may be stale; re-locate.
    state.editingImage.captionEl = findCaptionEl(state.editingImage.imgEl);
    applyImageReplace(data.url);
    toast('Image replaced.');
    closeImageModal();
  } catch (err) {
    toast(`Upload failed: ${err.message}`, true);
  }
});

$('#image-modal-remove').addEventListener('click', () => {
  if (!state.editingImage) return;
  if (!confirm('Remove this image (and its caption)?')) return;
  applyImageRemove();
  closeImageModal();
});

// ---------- Toast + unload guard ----------

let toastTimer = null;
function toast(msg, isError = false) {
  const el = $('#toast');
  el.textContent = msg;
  el.classList.toggle('error', isError);
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 2500);
}

window.addEventListener('beforeunload', (e) => {
  if (isDirty()) { e.preventDefault(); e.returnValue = ''; }
});

// ---------- Go ----------

boot().catch(() => showDenied());
