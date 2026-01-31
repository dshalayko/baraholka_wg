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

function autoResizeTextarea(textarea) {
  if (!textarea) return;
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

function autoResizeDescription() {
  autoResizeTextarea(elements.description);
}

function formatPublishedAt(value) {
  if (!value) return "";
  const match = String(value).match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}:\d{2})$/);
  if (!match) return value;
  return `${match[1]}.${match[2]}.${match[3]}, ${match[4]}`;
}

function showToast(message, variant = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${variant}`;
  toast.textContent = message;
  elements.toastContainer.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

function setBusy(isBusy, text = "") {
  if (isBusy) {
    state.busyCount += 1;
  } else {
    state.busyCount = Math.max(0, state.busyCount - 1);
  }
  const active = state.busyCount > 0;
  elements.busyOverlay.hidden = !active;
  elements.busyOverlay.style.display = active ? "flex" : "none";
  if (text) {
    elements.busyText.textContent = text;
  }
  document.querySelectorAll("button, input, textarea, select").forEach((el) => {
    if (el === elements.themeToggle) return;
    el.disabled = active;
  });
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
