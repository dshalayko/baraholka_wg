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
  pendingDeleteId: null,
  editModal: {
    id: null,
    photoFileIds: [],
    photoPreviews: [],
  },
  busyCount: 0,
  lastError: null,
};
