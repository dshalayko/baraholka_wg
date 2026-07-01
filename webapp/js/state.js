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
  formSnapshot: null,
  editModalSnapshot: null,
  pendingDiscardAction: null,
  editModal: {
    id: null,
    photoFileIds: [],
    originalPhotoFileIds: [],
    photoPreviews: [],
    adType: "fixed",
    startPrice: null,
    currency: "RSD",
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
  auctionCurrency: "RSD",
  bidScreenAnnId: null,
  bidPostLink: null,
  bidMinRequired: null,
  askedWriteAccess: false,
  // Telegram tells us up front whether the bot may already message this user.
  writeAccessGranted: !!tg?.initDataUnsafe?.user?.allows_write_to_pm,
};
