const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
}

const savedLanguage = localStorage.getItem("language");
const initialLanguage = savedLanguage || tg?.initDataUnsafe?.user?.language_code || "ru";

const state = {
  ads: [],
  editingId: null,
  photoFileIds: [],
  photoPreviews: [],
  hasUsername: !!tg?.initDataUnsafe?.user?.username,
  languageCode: initialLanguage,
  pendingDeleteId: null,
  editModal: {
    id: null,
    photoFileIds: [],
    photoPreviews: [],
  },
  busyCount: 0,
  lastError: null,
  unauthorized: false,
  isAdmin: false,
  statsSummary: null,
  expiredAds: [],
  adminDrafts: [],
  sentAppOpenEvent: false,
  adType: "fixed",
  bidScreenAnnId: null,
  bidPostLink: null,
  bidMinRequired: null,
  askedWriteAccess: false,
};
