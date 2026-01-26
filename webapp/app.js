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

const i18n = {
  ru: {
    title: "Объявления",
    myAds: "Мои объявления",
    create: "Создать объявление",
    yourAds: "Ваши объявления",
    refresh: "Обновить",
    description: "Описание",
    price: "Цена",
    photos: "Фотографии (макс 10)",
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
    pricePlaceholder: "Например: 50 BYN",
    preview: "Предпросмотр",
    saveDraft: "Сохранить черновик",
    back: "Назад",
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
    pricePlaceholder: "e.g. 50 BYN",
    preview: "Preview",
    saveDraft: "Save draft",
    back: "Back",
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
  listTitle: document.getElementById("listTitle"),
  refreshBtn: document.getElementById("refreshBtn"),
  adsList: document.getElementById("adsList"),
  emptyState: document.getElementById("emptyState"),
  previewPage: document.getElementById("previewPage"),
  previewPageTitle: document.getElementById("previewPageTitle"),
  previewPageText: document.getElementById("previewPageText"),
  previewPagePhotos: document.getElementById("previewPagePhotos"),
  closePreviewBtn: document.getElementById("closePreviewBtn"),
  publishFromPreviewBtn: document.getElementById("publishFromPreviewBtn"),
  formPanel: document.getElementById("formPanel"),
  formTitle: document.getElementById("formTitle"),
  cancelFormBtn: document.getElementById("cancelFormBtn"),
  previewBtn: document.getElementById("previewBtn"),
  saveAdBtn: document.getElementById("saveAdBtn"),
  descLabel: document.getElementById("descLabel"),
  description: document.getElementById("description"),
  priceLabel: document.getElementById("priceLabel"),
  price: document.getElementById("price"),
  photosLabel: document.getElementById("photosLabel"),
  photos: document.getElementById("photos"),
  photoChips: document.getElementById("photoChips"),
  uploadSpinner: document.getElementById("uploadSpinner"),
  previewPanel: document.getElementById("previewPanel"),
  previewText: document.getElementById("previewText"),
  previewPhotos: document.getElementById("previewPhotos"),
  previewTitle: document.getElementById("previewTitle"),
};

function applyTranslations() {
  document.documentElement.lang = state.languageCode?.startsWith("ru") ? "ru" : "en";
  elements.tabMyAds.textContent = t("myAds");
  elements.tabCreate.textContent = t("create");
  elements.listTitle.textContent = t("yourAds");
  elements.refreshBtn.textContent = t("refresh");
  elements.formTitle.textContent = t("create");
  elements.cancelFormBtn.textContent = t("cancel");
  elements.saveAdBtn.textContent = t("save");
  elements.descLabel.textContent = t("description");
  elements.priceLabel.textContent = t("price");
  elements.photosLabel.textContent = t("photos");
  elements.emptyState.textContent = t("noAds");
  elements.description.placeholder = t("descPlaceholder");
  elements.price.placeholder = t("pricePlaceholder");
  elements.themeToggle.textContent = isDarkTheme() ? "◐" : "◑";
  elements.previewBtn.textContent = t("preview");
  elements.previewTitle.textContent = t("preview");
  elements.previewPageTitle.textContent = t("preview");
  elements.publishFromPreviewBtn.textContent = t("publish");
  elements.closePreviewBtn.textContent = t("back");
  elements.saveAdBtn.textContent = t("saveDraft");
}

function showTab(tab) {
  const isList = tab === "list";
  elements.listPanel.hidden = !isList;
  elements.formPanel.hidden = isList;
  elements.previewPage.hidden = true;
  elements.tabMyAds.classList.toggle("active", isList);
  elements.tabCreate.classList.toggle("active", !isList);
}

function showPreviewPage() {
  elements.listPanel.hidden = true;
  elements.formPanel.hidden = true;
  elements.previewPage.hidden = false;
  elements.tabMyAds.classList.remove("active");
  elements.tabCreate.classList.remove("active");
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
  elements.formTitle.textContent = t("create");
  elements.previewPanel.hidden = true;
  elements.previewText.textContent = "";
  elements.previewPhotos.innerHTML = "";
  elements.previewPageText.textContent = "";
  elements.previewPagePhotos.innerHTML = "";
  updateCounts();
}

function updateCounts() {
  // Counters removed from UI; keep placeholder for future metrics if needed.
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
  state.ads = data.items || [];
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

    const publishBtn = document.createElement("button");
    publishBtn.className = "primary";
    publishBtn.textContent = t("publish");
    publishBtn.onclick = () => publishAd(ad.id);

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "danger";
    deleteBtn.textContent = t("delete");
    deleteBtn.onclick = () => deleteAd(ad.id);

    actions.append(editBtn, publishBtn, deleteBtn);

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

function setUploading(isUploading) {
  elements.uploadSpinner.classList.toggle("active", isUploading);
  elements.photos.disabled = isUploading;
  elements.saveAdBtn.disabled = isUploading;
  elements.previewBtn.disabled = isUploading;
}

function renderPhotoPreviews() {
  elements.photoChips.innerHTML = "";
  elements.previewPhotos.innerHTML = "";

  if (state.photoPreviews.length === 0) {
    return;
  }

  const grid = document.createElement("div");
  grid.className = "photo-grid";
  state.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";

    const remove = document.createElement("button");
    remove.type = "button";
    remove.textContent = "×";
    remove.onclick = () => removePhotoAt(index);

    photoItem.append(img, remove);
    grid.appendChild(photoItem);

    const chip = document.createElement("div");
    chip.className = "chip";
    chip.textContent = item.label;
    const chipRemove = document.createElement("button");
    chipRemove.type = "button";
    chipRemove.textContent = "×";
    chipRemove.onclick = () => removePhotoAt(index);
    chip.appendChild(chipRemove);
    elements.photoChips.appendChild(chip);
  });

  elements.previewPhotos.appendChild(grid);
}

function removePhotoAt(index) {
  const removed = state.photoPreviews.splice(index, 1)[0];
  state.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderPhotoPreviews();
  updatePreview();
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
  renderPhotoPreviews();
  elements.formTitle.textContent = t("edit");
  showTab("form");
  updateCounts();
  updatePreview();
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
  if (!files.length) return;
  uploadPhotos(files)
    .then((fileIds) => {
      state.photoFileIds = fileIds;
      state.photoPreviews = state.photoPreviews.map((item, idx) => ({
        ...item,
        label: `#${idx + 1}`,
        fileId: fileIds[idx],
      }));
      renderPhotoPreviews();
      updatePreview();
    })
    .catch((err) => {
      console.error(err);
      tg?.showAlert?.(err.message || t("uploadFailed"));
      setUploading(false);
    });
}

function updatePreview() {
  const description = elements.description.value.trim();
  const price = elements.price.value.trim();
  const text = `${description || "-"}\n\n${t("price")}\n${price || "-"}`;
  elements.previewText.textContent = text;
  elements.previewPanel.hidden = true;
  elements.previewPageText.textContent = text;
  elements.previewPagePhotos.innerHTML = elements.previewPhotos.innerHTML;
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

  elements.previewBtn.addEventListener("click", () => {
    updatePreview();
    showPreviewPage();
  });

  elements.saveAdBtn.addEventListener("click", saveAd);
  elements.refreshBtn.addEventListener("click", refreshAds);
  elements.description.addEventListener("input", updateCounts);
  elements.description.addEventListener("input", () => {
    if (!elements.previewPage.hidden) {
      updatePreview();
    }
  });
  elements.price.addEventListener("input", updateCounts);
  elements.price.addEventListener("input", () => {
    if (!elements.previewPage.hidden) {
      updatePreview();
    }
  });
  elements.photos.addEventListener("change", handlePhotoInput);
  elements.themeToggle.addEventListener("click", toggleTheme);
  elements.closePreviewBtn.addEventListener("click", () => {
    showTab("form");
  });
  elements.publishFromPreviewBtn.addEventListener("click", async () => {
    if (!state.editingId) {
      const description = elements.description.value.trim();
      const price = elements.price.value.trim();
      if (!description || !price) {
        tg?.showAlert?.(t("required"));
        return;
      }
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
      await refreshAds();
      showTab("list");
      return;
    }
    if (state.editingId) {
      await publishAd(state.editingId);
      showTab("list");
    }
  });
}

function isDarkTheme() {
  return document.documentElement.dataset.theme === "dark";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  if (tg?.themeParams) {
    const bg = theme === "dark" ? "#0f1116" : "#f2f5f9";
    tg.setBackgroundColor?.(bg);
  }
  applyTranslations();
}

function toggleTheme() {
  const next = isDarkTheme() ? "light" : "dark";
  localStorage.setItem("theme", next);
  applyTheme(next);
}

function initTheme() {
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
