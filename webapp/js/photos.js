function updateCounts() {
  // Counters removed from UI; keep placeholder for future metrics if needed.
}

function buildUploadHeaders() {
  const headers = { "ngrok-skip-browser-warning": "1" };
  if (tg?.initData) {
    headers["X-Telegram-Init-Data"] = tg.initData;
  }
  return headers;
}

const PHOTO_COMPRESS_TARGET_BYTES = 300 * 1024;
const PHOTO_COMPRESS_THRESHOLD_BYTES = PHOTO_COMPRESS_TARGET_BYTES;
const PHOTO_COMPRESS_MAX_EDGE = 1080;
const PHOTO_COMPRESS_QUALITY = 0.74;
const PHOTO_COMPRESS_MIN_EDGE = 720;
const PHOTO_COMPRESS_MIN_QUALITY = 0.58;

function loadImageForCompression(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      resolve(img);
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Failed to prepare image"));
    };
    img.src = url;
  });
}

function canvasToBlob(canvas, quality) {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob);
          return;
        }
        reject(new Error("Failed to compress image"));
      },
      "image/jpeg",
      quality,
    );
  });
}

async function compressPhotoForUpload(file) {
  if (!file?.type?.startsWith("image/") || file.type === "image/gif" || file.size <= PHOTO_COMPRESS_THRESHOLD_BYTES) {
    return file;
  }

  try {
    const img = await loadImageForCompression(file);
    const maxSourceEdge = Math.max(img.width, img.height);
    const attempts = [
      { edge: PHOTO_COMPRESS_MAX_EDGE, quality: PHOTO_COMPRESS_QUALITY },
      { edge: 960, quality: 0.68 },
      { edge: 840, quality: 0.62 },
      { edge: PHOTO_COMPRESS_MIN_EDGE, quality: PHOTO_COMPRESS_MIN_QUALITY },
    ];
    let bestBlob = null;

    for (const attempt of attempts) {
      const scale = Math.min(1, attempt.edge / maxSourceEdge);
      const width = Math.max(1, Math.round(img.width * scale));
      const height = Math.max(1, Math.round(img.height * scale));

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d");
      if (!ctx) return file;

      ctx.drawImage(img, 0, 0, width, height);
      const blob = await canvasToBlob(canvas, attempt.quality);
      if (blob && (!bestBlob || blob.size < bestBlob.size)) {
        bestBlob = blob;
      }
      if (blob && blob.size <= PHOTO_COMPRESS_TARGET_BYTES) {
        bestBlob = blob;
        break;
      }
    }

    if (!bestBlob || bestBlob.size >= file.size) {
      return file;
    }

    const baseName = (file.name || "photo").replace(/\.[^.]+$/, "");
    const compressedName = `${baseName}.jpg`;
    try {
      return new File([bestBlob], compressedName, { type: "image/jpeg", lastModified: Date.now() });
    } catch (err) {
      bestBlob.name = compressedName;
      return bestBlob;
    }
  } catch (err) {
    console.warn("photo compression failed", err);
    return file;
  }
}

async function parseUploadErrorMessage(response) {
  const fallback = `HTTP ${response.status}`;
  const text = await response.text();
  if (!text) return fallback;
  try {
    const data = JSON.parse(text);
    const detail = data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object" && typeof detail.message === "string" && detail.message.trim()) {
      return detail.message;
    }
  } catch (err) {
    // keep raw text as fallback
  }
  return text;
}

async function uploadFilesSequentially(files) {
  const fileIds = [];
  const headers = buildUploadHeaders();
  const total = files.length;

  for (let index = 0; index < total; index += 1) {
    const preparedPercent = Math.round((index / total) * 100);
    setBusyProgress({
      percent: preparedPercent,
      detail: `${index}/${total} • ${preparedPercent}%`,
    });
    const uploadFile = await compressPhotoForUpload(files[index]);
    const uploadingPercent = Math.round(((index + 0.35) / total) * 100);
    setBusyProgress({
      percent: uploadingPercent,
      detail: `${index}/${total} • ${uploadingPercent}%`,
    });
    const formData = new FormData();
    formData.append("files", uploadFile);

    const response = await fetch("/api/uploads", {
      method: "POST",
      headers,
      body: formData,
    });

    if (!response.ok) {
      const base = await parseUploadErrorMessage(response);
      throw new Error(`${base} (file ${index + 1}/${files.length})`);
    }

    const data = await response.json();
    const uploaded = data.file_ids || [];
    if (!uploaded.length || !uploaded[0]) {
      throw new Error(`Invalid upload response (file ${index + 1}/${files.length})`);
    }

    fileIds.push(uploaded[0]);
    const donePercent = Math.round(((index + 1) / total) * 100);
    setBusyProgress({
      percent: donePercent,
      detail: `${index + 1}/${total} • ${donePercent}%`,
    });
  }

  return fileIds;
}

function setUploading(isUploading) {
  elements.uploadSpinner.classList.toggle("active", isUploading);
  elements.photos.disabled = isUploading;
  elements.saveAdBtn.disabled = isUploading;
}

function setEditUploading(isUploading) {
  elements.editUploadSpinner.classList.toggle("active", isUploading);
  elements.editPhotos.disabled = isUploading;
  elements.editPublishBtn.disabled = isUploading;
}

function moveItem(items, fromIndex, toIndex) {
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= items.length || toIndex >= items.length) {
    return;
  }
  const [item] = items.splice(fromIndex, 1);
  items.splice(toIndex, 0, item);
}

function refreshPhotoLabels(items) {
  items.forEach((item, index) => {
    item.label = `#${index + 1}`;
  });
}

function reorderPhotos(fromIndex, toIndex, isEdit = false) {
  const photoState = isEdit ? state.editModal : state;
  const previews = photoState.photoPreviews;
  const fileIds = photoState.photoFileIds;
  if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0 || fromIndex >= previews.length || toIndex >= previews.length) {
    return;
  }

  moveItem(previews, fromIndex, toIndex);
  moveItem(fileIds, fromIndex, toIndex);
  refreshPhotoLabels(previews);
  if (isEdit) {
    renderEditPhotoPreviews();
    return;
  }
  renderPhotoPreviews();
}

function clearPhotoDropTargets() {
  document.querySelectorAll(".photo-item.drop-target").forEach((item) => item.classList.remove("drop-target"));
}

function bindPhotoReorder(photoItem, index, isEdit = false) {
  let pointerStarted = false;
  let pointerMoved = false;
  let pointerStartX = 0;
  let pointerStartY = 0;

  photoItem.draggable = true;
  photoItem.dataset.photoIndex = String(index);
  photoItem.setAttribute("aria-label", `Photo ${index + 1}`);

  photoItem.addEventListener("dragstart", (event) => {
    event.dataTransfer?.setData("text/plain", String(index));
    event.dataTransfer?.setDragImage?.(photoItem, photoItem.offsetWidth / 2, photoItem.offsetHeight / 2);
    photoItem.classList.add("dragging");
  });

  photoItem.addEventListener("dragend", () => {
    photoItem.classList.remove("dragging");
    clearPhotoDropTargets();
  });

  photoItem.addEventListener("dragover", (event) => {
    event.preventDefault();
    photoItem.classList.add("drop-target");
  });

  photoItem.addEventListener("dragleave", () => {
    photoItem.classList.remove("drop-target");
  });

  photoItem.addEventListener("drop", (event) => {
    event.preventDefault();
    const rawIndex = event.dataTransfer?.getData("text/plain");
    if (rawIndex === "") return;
    const fromIndex = Number(rawIndex);
    reorderPhotos(fromIndex, index, isEdit);
  });

  photoItem.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) return;
    pointerStarted = true;
    pointerMoved = false;
    pointerStartX = event.clientX;
    pointerStartY = event.clientY;
    photoItem.setPointerCapture?.(event.pointerId);
  });

  photoItem.addEventListener("pointermove", (event) => {
    if (!pointerStarted) return;
    if (Math.hypot(event.clientX - pointerStartX, event.clientY - pointerStartY) > 8) {
      pointerMoved = true;
      photoItem.classList.add("dragging");
    }
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".photo-item");
    clearPhotoDropTargets();
    target?.classList.add("drop-target");
  });

  photoItem.addEventListener("pointerup", (event) => {
    if (!pointerStarted) return;
    pointerStarted = false;
    photoItem.releasePointerCapture?.(event.pointerId);
    photoItem.classList.remove("dragging");
    if (!pointerMoved) {
      const photoState = isEdit ? state.editModal : state;
      openPhotoViewer(photoState.photoPreviews[index]?.url);
      clearPhotoDropTargets();
      return;
    }
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest(".photo-item");
    const toIndex = Number(target?.dataset.photoIndex);
    if (Number.isInteger(toIndex)) {
      reorderPhotos(index, toIndex, isEdit);
    }
    clearPhotoDropTargets();
  });

  photoItem.addEventListener("pointercancel", () => {
    pointerStarted = false;
    photoItem.classList.remove("dragging");
    clearPhotoDropTargets();
  });
}

function renderPhotoPreviews() {
  elements.photoChips.innerHTML = "";
  elements.photoGrid.innerHTML = "";

  if (state.photoPreviews.length === 0) {
    elements.addMorePhotosBtn.hidden = false;
    return;
  }

  const grid = document.createDocumentFragment();
  state.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";
    bindPhotoReorder(photoItem, index);

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";
    img.draggable = false;

    const dragHandle = document.createElement("div");
    dragHandle.className = "photo-drag-handle";
    dragHandle.setAttribute("aria-hidden", "true");

    const remove = document.createElement("button");
    remove.type = "button";
    remove.draggable = false;
    remove.textContent = "×";
    remove.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      removePhotoAt(index);
    };

    photoItem.append(img, dragHandle, remove);
    grid.appendChild(photoItem);
  });

  elements.photoGrid.appendChild(grid);
  elements.addMorePhotosBtn.hidden = false;
}

function renderEditPhotoPreviews() {
  elements.editPhotoGrid.innerHTML = "";

  if (state.editModal.photoPreviews.length === 0) {
    elements.editAddMorePhotosBtn.hidden = false;
    return;
  }

  const grid = document.createDocumentFragment();
  state.editModal.photoPreviews.forEach((item, index) => {
    const photoItem = document.createElement("div");
    photoItem.className = "photo-item";
    bindPhotoReorder(photoItem, index, true);

    const img = document.createElement("img");
    img.src = item.url;
    img.alt = "photo";
    img.draggable = false;

    const dragHandle = document.createElement("div");
    dragHandle.className = "photo-drag-handle";
    dragHandle.setAttribute("aria-hidden", "true");

    const remove = document.createElement("button");
    remove.type = "button";
    remove.draggable = false;
    remove.textContent = "×";
    remove.onclick = (event) => {
      event.preventDefault();
      event.stopPropagation();
      removeEditPhotoAt(index);
    };

    photoItem.append(img, dragHandle, remove);
    grid.appendChild(photoItem);
  });

  elements.editPhotoGrid.appendChild(grid);
  elements.editAddMorePhotosBtn.hidden = false;
}

function removePhotoAt(index) {
  const removed = state.photoPreviews.splice(index, 1)[0];
  state.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderPhotoPreviews();
}

function removeEditPhotoAt(index) {
  const removed = state.editModal.photoPreviews.splice(index, 1)[0];
  state.editModal.photoFileIds.splice(index, 1);
  if (removed && removed.source === "local") {
    URL.revokeObjectURL(removed.url);
  }
  renderEditPhotoPreviews();
}

async function appendPhotos(files) {
  if (!files.length) {
    return;
  }
  if (state.photoFileIds.length + files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setUploading(true);
  const prevPreviews = [...state.photoPreviews];
  const prevFileIds = [...state.photoFileIds];
  let newPreviews = [];
  try {
    const startIndex = state.photoPreviews.length;
    newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.photoPreviews = [...state.photoPreviews, ...newPreviews];
    renderPhotoPreviews();
    const newFileIds = await uploadFilesSequentially(files);
    state.photoFileIds = [...state.photoFileIds, ...newFileIds];
  } catch (error) {
    newPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.photoPreviews = prevPreviews;
    state.photoFileIds = prevFileIds;
    renderPhotoPreviews();
    throw error;
  } finally {
    setUploading(false);
    setBusy(false);
  }
}

async function uploadPhotos(files) {
  if (!files.length) {
    return [];
  }
  if (files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setUploading(true);
  const prevPreviews = [...state.photoPreviews];
  let nextPreviews = [];
  try {
    nextPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    state.photoPreviews = nextPreviews;
    renderPhotoPreviews();
    return await uploadFilesSequentially(files);
  } catch (error) {
    nextPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.photoPreviews = prevPreviews;
    renderPhotoPreviews();
    throw error;
  } finally {
    setUploading(false);
    setBusy(false);
  }
}

async function appendEditPhotos(files) {
  if (!files.length) {
    return;
  }
  if (state.editModal.photoFileIds.length + files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setEditUploading(true);
  const prevPreviews = [...state.editModal.photoPreviews];
  const prevFileIds = [...state.editModal.photoFileIds];
  let newPreviews = [];
  try {
    const startIndex = state.editModal.photoPreviews.length;
    newPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${startIndex + idx + 1}`,
    }));
    state.editModal.photoPreviews = [...state.editModal.photoPreviews, ...newPreviews];
    renderEditPhotoPreviews();
    const newFileIds = await uploadFilesSequentially(files);
    state.editModal.photoFileIds = [...state.editModal.photoFileIds, ...newFileIds];
  } catch (error) {
    newPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.editModal.photoPreviews = prevPreviews;
    state.editModal.photoFileIds = prevFileIds;
    renderEditPhotoPreviews();
    throw error;
  } finally {
    setEditUploading(false);
    setBusy(false);
  }
}

async function uploadEditPhotos(files) {
  if (!files.length) {
    return [];
  }
  if (files.length > 10) {
    throw new Error(t("tooManyPhotos"));
  }
  setBusy(true, t("busyUploading"));
  setEditUploading(true);
  const prevPreviews = [...state.editModal.photoPreviews];
  let nextPreviews = [];
  try {
    nextPreviews = files.map((file, idx) => ({
      source: "local",
      url: URL.createObjectURL(file),
      label: `#${idx + 1}`,
    }));
    state.editModal.photoPreviews = nextPreviews;
    renderEditPhotoPreviews();
    return await uploadFilesSequentially(files);
  } catch (error) {
    nextPreviews.forEach((item) => {
      if (item?.source === "local") {
        URL.revokeObjectURL(item.url);
      }
    });
    state.editModal.photoPreviews = prevPreviews;
    renderEditPhotoPreviews();
    throw error;
  } finally {
    setEditUploading(false);
    setBusy(false);
  }
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
