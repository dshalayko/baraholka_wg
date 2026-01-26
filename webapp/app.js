const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
}

const state = {
  ads: [],
  editingId: null,
  photoFileIds: [],
  photoPreviews: [],
  languageCode: tg?.initDataUnsafe?.user?.language_code || "ru",
};

function hexToRgb(hex) {
  if (!hex) return null;
  const value = hex.replace("#", "");
  if (value.length !== 6) return null;
  const r = parseInt(value.slice(0, 2), 16);
  const g = parseInt(value.slice(2, 4), 16);
  const b = parseInt(value.slice(4, 6), 16);
  return { r, g, b };
}

function isLightColor(hex) {
  const rgb = hexToRgb(hex);
  if (!rgb) return false;
  const { r, g, b } = rgb;
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.6;
}

function applyTelegramTheme() {
  if (!tg?.themeParams) return false;
  const p = tg.themeParams;
  const root = document.documentElement.style;
  const bg = p.bg_color || "#ffffff";
  const isLight = isLightColor(bg);
  const secondary = p.secondary_bg_color || (isLightColor(bg) ? "#ffffff" : "#1a1f2b");
  const text = p.text_color || (isLightColor(bg) ? "#101418" : "#f3f5f7");
  const hint = p.hint_color || (isLightColor(bg) ? "rgba(16,20,24,0.5)" : "rgba(243,245,247,0.62)");
  const link = p.link_color || (isLightColor(bg) ? "#1a73e8" : "#5aa7ff");
  const button = p.button_color || (isLightColor(bg) ? "#2481cc" : "#3f8cff");
  const buttonText = p.button_text_color || "#ffffff";
  const border = isLightColor(bg) ? "rgba(16,20,24,0.08)" : "rgba(255,255,255,0.12)";

  root.setProperty("--bg", bg);
  root.setProperty("--secondary-bg", secondary);
  root.setProperty("--ink", text);
  root.setProperty("--muted", hint);
  root.setProperty("--meta-text", isLight ? "#000000" : "rgba(243, 247, 252, 0.86)");
  root.setProperty("--link", link);
  root.setProperty("--button", button);
  root.setProperty("--button-text", buttonText);
  root.setProperty("--border", border);
  document.documentElement.dataset.theme = isLight ? "light" : "dark";
  return true;
}

const i18n = {
  ru: {
    title: "Объявления",
    myAds: "Мои объявления",
    create: "Создать объявление",
    yourAds: "Ваши объявления",
    refresh: "Обновить",
    description: "Описание",
    price: "Цена",
    photos: "Фотографии (максимум 10)",
    save: "Сохранить",
    cancel: "Отмена",
    noAds: "Пока нет объявлений",
    draft: "Черновик",
    published: "Опубликовано",
    edit: "Редактировать",
    publish: "Опубликовать",
    delete: "Удалить",
    open: "Открыть",
    required: "Нужно заполнить описание и цену.",
    tooManyPhotos: "Слишком много фото (макс 10).",
    uploadFailed: "Не удалось загрузить фото.",
    descPlaceholder: "Опишите товар...",
    pricePlaceholder: "Например: 50 RSD",
    preview: "Предпросмотр",
    saveDraft: "Сохранить черновик",
    back: "Назад",
    addMore: "Добавить фото",
    publishNow: "Опубликовать",
  },
  en: {
    title: "Ads",
    myAds: "My ads",
    create: "Create ad",
    yourAds: "Your ads",
    refresh: "Refresh",
    description: "Description",
    price: "Price",
    photos: "Photos (max 10)",
    save: "Save",
    cancel: "Cancel",
    noAds: "No ads yet",
    draft: "Draft",
    published: "Published",
    edit: "Edit",
    publish: "Publish",
    delete: "Delete",
    open: "Open",
    required: "Description and price are required.",
    tooManyPhotos: "Too many photos (max 10).",
    uploadFailed: "Upload failed.",
    descPlaceholder: "Describe the item...",
    pricePlaceholder: "e.g. 50 RSD",
    preview: "Preview",
    saveDraft: "Save draft",
    back: "Back",
    addMore: "Add photos",
    publishNow: "Publish",
  }
};

function t(key) {
  const lang = state.languageCode?.startsWith("ru") ? "ru" : "en";
  return i18n[lang][key] || key;
}

const elements = {
  tabMyAds: document.getElementById("tabMyAds"),
  tabCreate: document.getElementById("tabCreate"),
  themeToggle: document.getElementById("themeToggle"),
  listPanel: document.getElementById("listPanel"),
  adsList: document.getElementById("adsList"),
  emptyState: document.getElementById("emptyState"),
  formPanel: document.getElementById("formPanel"),
  cancelFormBtn: document.getElementById("cancelFormBtn"),
  saveAdBtn: document.getElementById("saveAdBtn"),
  publishBtn: document.getElementById("publishBtn"),
  descLabel: document.getElementById("descLabel"),
  description: document.getElementById("description"),
  priceLabel: document.getElementById("priceLabel"),
  price: document.getElementById("price"),
  photosLabel: document.getElementById("photosLabel"),
  photos: document.getElementById("photos"),
  addMorePhotosBtn: document.getElementById("addMorePhotosBtn"),
  photoChips: document.getElementById("photoChips"),
  photoGrid: document.getElementById("photoGrid"),
  uploadSpinner: document.getElementById("uploadSpinner"),
};

function applyTranslations() {
  document.documentElement.lang = state.languageCode?.startsWith("ru") ? "ru" : "en";
  elements.tabMyAds.textContent = t("myAds");
  elements.tabCreate.textContent = t("create");
  elements.cancelFormBtn.textContent = t("cancel");
  elements.descLabel.textContent = t("description");
  elements.priceLabel.textContent = t("price");
  elements.photosLabel.textContent = t("photos");
  elements.emptyState.textContent = t("noAds");
  elements.description.placeholder = t("descPlaceholder");
  elements.price.placeholder = t("pricePlaceholder");
  elements.themeToggle.textContent = isDarkTheme() ? "◐" : "◑";
  elements.saveAdBtn.textContent = t("saveDraft");
  elements.publishBtn.textContent = t("publishNow");
  elements.addMorePhotosBtn.textContent = t("addMore");
}

function showTab(tab) {
  const isList = tab === "list";
  elements.listPanel.hidden = !isList;
  elements.formPanel.hidden = isList;
  elements.tabMyAds.classList.toggle("active", isList);
  elements.tabCreate.classList.toggle("active", !isList);
}



function resetForm() {
  state.editingId = null;
  state.photoFileIds = [];
  state.photoPreviews.forEach((item) => {
    if (item.source === "local") {
      URL.revokeObjectURL(item.url);
    }
  });
  state.photoPreviews = [];
  elements.description.value = "";
  elements.price.value = "";
  elements.photos.value = "";
  elements.photoChips.innerHTML = "";
  elements.photoGrid.innerHTML = "";
  updateCounts();
  autoResizeDescription();
}

function updateCounts() {
  // Counters removed from UI; keep placeholder for future metrics if needed.
}

function autoResizeDescription() {
  if (!elements.description) return;
  elements.description.style.height = "auto";
  elements.description.style.height = `${elements.description.scrollHeight}px`;
}

async function apiFetch(path, options = {}) {
  const headers = options.headers || {};
  headers["Content-Type"] = headers["Content-Type"] || "application/json";
  headers["ngrok-skip-browser-warning"] = "1";
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  const response = await fetch(path, { ...options, headers });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

async function refreshAds() {
  const data = await apiFetch("/api/announcements");
  state.ads = (data.items || []).slice().sort((a, b) => (b.id || 0) - (a.id || 0));
  renderAds();
}

function renderAds() {
  elements.adsList.innerHTML = "";
  if (!state.ads.length) {
    elements.adsList.appendChild(elements.emptyState);
    elements.emptyState.hidden = false;
    return;
  }
  elements.emptyState.hidden = true;
  state.ads.forEach((ad) => {
    const card = document.createElement("div");
    card.className = "ad-card";

    if (ad.photo_file_ids && ad.photo_file_ids.length && tg?.initData) {
      const img = document.createElement("img");
      img.className = "ad-photo";
      const fileId = ad.photo_file_ids[0];
      const initData = encodeURIComponent(tg.initData);
      img.src = `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`;
      img.alt = ad.description || "photo";
      card.appendChild(img);
    }

    const title = document.createElement("h3");
    title.className = "ad-description";
    title.textContent = ad.description || "(no description)";

    const meta = document.createElement("div");
    meta.className = "ad-meta";
    meta.textContent = `${ad.price || ""}`;

    const status = document.createElement("div");
    status.className = "ad-meta";
    status.textContent = ad.is_published ? t("published") : t("draft");

    const actions = document.createElement("div");
    actions.className = "ad-actions";

    const editBtn = document.createElement("button");
    editBtn.className = "ghost";
    editBtn.textContent = t("edit");
    editBtn.onclick = () => startEdit(ad);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "danger";
    deleteBtn.textContent = t("delete");
    deleteBtn.onclick = () => deleteAd(ad.id);

    actions.append(editBtn, deleteBtn);

    if (!ad.is_published) {
      const publishBtn = document.createElement("button");
      publishBtn.className = "primary";
      publishBtn.textContent = t("publish");
      publishBtn.onclick = () => publishAd(ad.id);
      actions.append(publishBtn);
    }

    if (ad.post_link) {
      const openBtn = document.createElement("button");
      openBtn.className = "ghost";
      openBtn.textContent = t("open");
      openBtn.onclick = () => tg?.openTelegramLink?.(ad.post_link);
      actions.append(openBtn);
    }

    card.append(title, meta, status, actions);
    elements.adsList.appendChild(card);
  });
}

function updatePreview() {}

function setUploading(isUploading) {
  elements.uploadSpinner.classList.toggle("active", isUploading);
  elements.photos.disabled = isUploading;
  elements.saveAdBtn.disabled = isUploading;
}

function renderPhotoPreviews() {
  elements.photoChips.innerHTML = "";
  elements.photoGrid.innerHTML = "";

  if (state.photoPreviews.length === 0) {
    elements.addMorePhotosBtn.hidden = true;
    return;
  }

  const grid = document.createDocumentFragment();
  state.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      removePhotoAt(index);
    };

    photoItem.append(img, remove);
    grid.appendChild(photoItem);

  });

  elements.photoGrid.appendChild(grid);
  elements.addMorePhotosBtn.hidden = false;
}

function removePhotoAt(index) {
  const removed = state.photoPreviews.splice(index, 1)[0];
  state.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderPhotoPreviews();
}

async function appendPhotos(files) {
  if (!files.length) {
    return;
  }
  if (state.photoFileIds.length + files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setUploading(true);
  const startIndex = state.photoPreviews.length;
  const newPreviews = files.map((file, idx) => ({
    source: "local",
    url: URL.createObjectURL(file),
    label: `#${startIndex + idx + 1}`,
  }));
  state.photoPreviews = [...state.photoPreviews, ...newPreviews];
  renderPhotoPreviews();
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const headers = {};
  headers["ngrok-skip-browser-warning"] = "1";
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  const response = await fetch("/api/uploads", {
    method: "POST",
    headers,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    setUploading(false);
    throw new Error(text || `HTTP ${response.status}`);
  }
  const data = await response.json();
  const newFileIds = data.file_ids || [];
  state.photoFileIds = [...state.photoFileIds, ...newFileIds];
  setUploading(false);
}

async function uploadPhotos(files) {
  if (!files.length) {
    return [];
  }
  if (files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setUploading(true);
  state.photoPreviews = files.map((file, idx) => ({
    source: "local",
    url: URL.createObjectURL(file),
    label: `#${idx + 1}`,
  }));
  renderPhotoPreviews();
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  const headers = {};
  headers["ngrok-skip-browser-warning"] = "1";
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  const response = await fetch("/api/uploads", {
    method: "POST",
    headers,
    body: formData,
  });
  if (!response.ok) {
    const text = await response.text();
    setUploading(false);
    throw new Error(text || `HTTP ${response.status}`);
  }
  const data = await response.json();
  setUploading(false);
  return data.file_ids || [];
}

async function saveAd() {
  const description = elements.description.value.trim();
  const price = elements.price.value.trim();
  if (!description || !price) {
    tg?.showAlert?.(t("required"));
    return;
  }

  const payload = {
    description,
    price,
    photo_file_ids: state.photoFileIds,
  };

  if (state.editingId) {
    await apiFetch(`/api/announcements/${state.editingId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  } else {
    await apiFetch("/api/announcements", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  resetForm();
  showTab("list");
  await refreshAds();
}

function startEdit(ad) {
  state.editingId = ad.id;
  state.photoFileIds = ad.photo_file_ids || [];
  state.photoPreviews = (ad.photo_file_ids || []).map((fileId, idx) => {
    const initData = encodeURIComponent(tg?.initData || "");
    return {
      source: "remote",
      url: `/api/announcements/${ad.id}/photo?file_id=${encodeURIComponent(fileId)}&initData=${initData}`,
      label: `#${idx + 1}`,
    };
  });
  elements.description.value = ad.description || "";
  elements.price.value = ad.price || "";
  autoResizeDescription();
  renderPhotoPreviews();
  showTab("form");
  updateCounts();
}

async function deleteAd(id) {
  await apiFetch(`/api/announcements/${id}`, { method: "DELETE" });
  await refreshAds();
}

async function publishAd(id) {
  const data = await apiFetch(`/api/announcements/${id}/publish`, { method: "POST" });
  if (data.post_link) {
    tg?.openTelegramLink?.(data.post_link);
  }
  await refreshAds();
}

function handlePhotoInput() {
  const files = Array.from(elements.photos.files || []);
  elements.photos.value = "";
  if (!files.length) return;
  const hasExisting = state.photoFileIds.length > 0;
  const uploader = hasExisting ? appendPhotos : uploadPhotos;
  uploader(files)
    .then((fileIds) => {
      if (!hasExisting) {
        state.photoFileIds = fileIds;
      }
      state.photoPreviews = state.photoPreviews.map((item, idx) => ({
        ...item,
        label: `#${idx + 1}`,
      }));
      renderPhotoPreviews();
    })
    .catch((err) => {
      console.error(err);
      tg?.showAlert?.(err.message || t("uploadFailed"));
      setUploading(false);
    });
}

function bindEvents() {
  elements.tabMyAds.addEventListener("click", () => {
    showTab("list");
  });

  elements.tabCreate.addEventListener("click", () => {
    resetForm();
    showTab("form");
  });

  elements.cancelFormBtn.addEventListener("click", () => {
    resetForm();
    showTab("list");
  });

  elements.saveAdBtn.addEventListener("click", saveAd);
  elements.publishBtn.addEventListener("click", async () => {
    const description = elements.description.value.trim();
    const price = elements.price.value.trim();
    if (!description || !price) {
      tg?.showAlert?.(t("required"));
      return;
    }
    if (!state.editingId) {
      const created = await apiFetch("/api/announcements", {
        method: "POST",
        body: JSON.stringify({
          description,
          price,
          photo_file_ids: state.photoFileIds,
        }),
      });
      if (created && created.id) {
        await publishAd(created.id);
      }
    } else {
      await publishAd(state.editingId);
    }
    await refreshAds();
    showTab("list");
  });
  elements.description.addEventListener("input", () => {
    updateCounts();
    autoResizeDescription();
  });
  elements.price.addEventListener("input", updateCounts);
  elements.addMorePhotosBtn.addEventListener("click", (event) => {
    event.preventDefault();
    elements.photos.click();
  });
  elements.photos.addEventListener("change", handlePhotoInput);
  elements.themeToggle.addEventListener("click", toggleTheme);
}

function isDarkTheme() {
  return document.documentElement.dataset.theme === "dark";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  if (tg?.themeParams) {
    tg.setBackgroundColor?.(tg.themeParams.bg_color || (theme === "dark" ? "#0f1116" : "#f2f5f9"));
  }
  applyTranslations();
}

function toggleTheme() {
  const next = isDarkTheme() ? "light" : "dark";
  localStorage.setItem("theme", next);
  applyTheme(next);
}

function initTheme() {
  if (applyTelegramTheme()) {
    if (elements.themeToggle) {
      elements.themeToggle.hidden = true;
    }
    tg?.setBackgroundColor?.(tg.themeParams.bg_color || "#ffffff");
    tg?.onEvent?.("themeChanged", () => {
      applyTelegramTheme();
      applyTranslations();
    });
    return;
  }
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") {
    applyTheme(saved);
    return;
  }
  if (tg?.colorScheme === "light") {
    applyTheme("light");
  } else {
    applyTheme("dark");
  }
}

applyTranslations();
bindEvents();
updateCounts();
showTab("list");
refreshAds();
initTheme();
