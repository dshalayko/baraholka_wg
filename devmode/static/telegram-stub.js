/*
 * Browser stand-in for window.Telegram.WebApp, plus a small debug toolbar.
 *
 * Loaded in place of telegram-web-app.js and BEFORE the app's own scripts, so
 * state.js sees a ready `tg` synchronously. initData is signed server-side on
 * every page render with the debug bot token, so webserver/auth.py verifies it
 * through the exact same HMAC path it uses in real Telegram.
 */
(function () {
  "use strict";

  const config = window.__DEBUG_TG__ || {};
  const listeners = Object.create(null);

  function prefersDark() {
    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
  }

  function themeFor(dark) {
    return dark
      ? {
          bg_color: "#17212b",
          secondary_bg_color: "#0e1621",
          text_color: "#f5f5f5",
          hint_color: "#708499",
          link_color: "#6ab3f3",
          button_color: "#5288c1",
          button_text_color: "#ffffff",
          header_bg_color: "#17212b",
          accent_text_color: "#6ab3f3",
          destructive_text_color: "#ec3942",
        }
      : {
          bg_color: "#ffffff",
          secondary_bg_color: "#f1f1f1",
          text_color: "#000000",
          hint_color: "#707579",
          link_color: "#3390ec",
          button_color: "#3390ec",
          button_text_color: "#ffffff",
          header_bg_color: "#ffffff",
          accent_text_color: "#3390ec",
          destructive_text_color: "#df3f40",
        };
  }

  function emit(event) {
    (listeners[event] || []).forEach((callback) => {
      try {
        callback();
      } catch (err) {
        console.warn("[debug-tg] listener failed for", event, err);
      }
    });
  }

  function log(method, detail) {
    if (detail === undefined) console.info(`[debug-tg] ${method}()`);
    else console.info(`[debug-tg] ${method}()`, detail);
  }

  function urlWith(overrides) {
    const url = new URL(window.location.href);
    Object.entries(overrides).forEach(([key, value]) => {
      if (value === null) url.searchParams.delete(key);
      else url.searchParams.set(key, value);
    });
    return url.toString();
  }

  const noopButton = (name) => ({
    isVisible: false,
    text: "",
    show() {
      this.isVisible = true;
      log(`${name}.show`);
      return this;
    },
    hide() {
      this.isVisible = false;
      log(`${name}.hide`);
      return this;
    },
    setText(text) {
      this.text = text;
      return this;
    },
    onClick(callback) {
      this._callback = callback;
      return this;
    },
    offClick() {
      this._callback = null;
      return this;
    },
    enable() {
      return this;
    },
    disable() {
      return this;
    },
    showProgress() {
      return this;
    },
    hideProgress() {
      return this;
    },
  });

  const webApp = {
    initData: config.initData || "",
    initDataUnsafe: config.initDataUnsafe || {},
    version: "7.10",
    platform: "debug-browser",
    colorScheme: prefersDark() ? "dark" : "light",
    themeParams: themeFor(prefersDark()),
    isExpanded: true,
    viewportHeight: window.innerHeight,
    viewportStableHeight: window.innerHeight,
    headerColor: themeFor(prefersDark()).header_bg_color,
    backgroundColor: themeFor(prefersDark()).bg_color,
    isClosingConfirmationEnabled: false,

    ready() {
      log("ready");
    },
    expand() {
      this.isExpanded = true;
      log("expand");
    },
    close() {
      // A browser tab can't close itself reliably; going back to the ad list is
      // the closest analogue of "the Mini App closed and Telegram is showing".
      log("close", "→ returning to the ad list");
      window.location.href = urlWith({ bid: null, bids: null, startapp: null, start_param: null });
    },
    showAlert(message, callback) {
      log("showAlert", message);
      window.alert(message);
      if (callback) callback();
    },
    showConfirm(message, callback) {
      log("showConfirm", message);
      const ok = window.confirm(message);
      if (callback) callback(ok);
    },
    showPopup(params, callback) {
      log("showPopup", params);
      window.alert([params?.title, params?.message].filter(Boolean).join("\n\n"));
      if (callback) callback((params?.buttons && params.buttons[0]?.id) || "ok");
    },
    requestWriteAccess(callback) {
      const granted = window.confirm("[debug] Разрешить боту писать вам в личку?");
      log("requestWriteAccess", granted);
      if (callback) callback(granted);
    },
    requestContact(callback) {
      if (callback) callback(false);
    },
    openTelegramLink(url) {
      log("openTelegramLink", url);
      window.open(url, "_blank", "noopener");
    },
    openLink(url) {
      log("openLink", url);
      window.open(url, "_blank", "noopener");
    },
    setBackgroundColor(color) {
      this.backgroundColor = color;
      log("setBackgroundColor", color);
    },
    setHeaderColor(color) {
      this.headerColor = color;
      log("setHeaderColor", color);
    },
    enableClosingConfirmation() {
      this.isClosingConfirmationEnabled = true;
    },
    disableClosingConfirmation() {
      this.isClosingConfirmationEnabled = false;
    },
    sendData(data) {
      log("sendData", data);
    },
    onEvent(event, callback) {
      (listeners[event] = listeners[event] || []).push(callback);
    },
    offEvent(event, callback) {
      listeners[event] = (listeners[event] || []).filter((item) => item !== callback);
    },
    HapticFeedback: {
      impactOccurred(style) {
        log("haptic.impact", style);
        return this;
      },
      notificationOccurred(type) {
        log("haptic.notification", type);
        return this;
      },
      selectionChanged() {
        return this;
      },
    },
    BackButton: noopButton("BackButton"),
    MainButton: noopButton("MainButton"),
    SettingsButton: noopButton("SettingsButton"),
    CloudStorage: {
      setItem(key, value, callback) {
        try {
          localStorage.setItem(`tgcloud:${key}`, value);
          if (callback) callback(null, true);
        } catch (err) {
          if (callback) callback(err);
        }
      },
      getItem(key, callback) {
        if (callback) callback(null, localStorage.getItem(`tgcloud:${key}`));
      },
      removeItem(key, callback) {
        localStorage.removeItem(`tgcloud:${key}`);
        if (callback) callback(null, true);
      },
    },
  };

  window.Telegram = { WebApp: webApp };

  // Keep the fake theme following the OS so "Auto" is testable both ways.
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", (event) => {
      webApp.colorScheme = event.matches ? "dark" : "light";
      webApp.themeParams = themeFor(event.matches);
      emit("themeChanged");
    });
  }
  window.addEventListener("resize", () => {
    webApp.viewportHeight = window.innerHeight;
    webApp.viewportStableHeight = window.innerHeight;
    emit("viewportChanged");
  });

  // ------------------------------------------------------------------
  // Debug toolbar (Shadow DOM, so the app's CSS can't reach into it)
  // ------------------------------------------------------------------
  function mountToolbar() {
    const host = document.createElement("div");
    host.id = "devmode-toolbar";
    // Pinned to the middle of the right edge: the app puts its own controls in
    // both top corners and a floating tab bar along the bottom, so this is the
    // only spot that never covers a real control.
    host.style.cssText =
      "position:fixed;right:0;top:50%;transform:translateY(-50%);z-index:2147483647;display:flex;justify-content:flex-end;";
    document.body.appendChild(host);
    const root = host.attachShadow({ mode: "open" });

    const users = Array.isArray(config.users) ? config.users : [];
    const current = config.currentUser;
    // Open on a first visit so the toolbar is discoverable; remembered after.
    const stored = localStorage.getItem("devmodeToolbarOpen");
    const startOpen = stored === null ? true : stored === "1";

    root.innerHTML = `
      <style>
        :host { all: initial; }
        * { box-sizing: border-box; font-family: -apple-system, "SF Pro Text", Segoe UI, Roboto, sans-serif; }
        /* Collapsed: a discreet edge tab, so it never hides content it sits on. */
        .pill {
          padding: 9px 5px 9px 7px; border-radius: 9px 0 0 9px; cursor: pointer;
          background: #b3261e; color: #fff; font-size: 13px; line-height: 1;
          border: none; box-shadow: 0 2px 10px rgba(0,0,0,.3);
          opacity: .45; transition: opacity .15s;
        }
        .pill:hover { opacity: 1; }
        .panel {
          margin: 8px; width: min(272px, 76vw); max-height: 80vh; overflow: auto;
          background: #14181f; color: #e8ecf2; border: 1px solid #2b3340;
          border-radius: 12px; box-shadow: 0 12px 32px rgba(0,0,0,.5); font-size: 12px;
        }
        .head { display:flex; align-items:center; justify-content:space-between;
                padding: 9px 11px; border-bottom: 1px solid #2b3340; }
        .title { font-weight: 700; font-size: 11px; letter-spacing: .06em; color: #ff8a80; }
        .x { background:none;border:none;color:#8b97a8;font-size:16px;cursor:pointer;line-height:1; }
        .section { padding: 9px 11px; border-bottom: 1px solid #222a35; }
        .label { color:#8b97a8; text-transform:uppercase; font-size:9.5px; letter-spacing:.08em; margin-bottom:6px; }
        .user { display:block; width:100%; text-align:left; margin-bottom:5px; padding:7px 9px;
                border-radius:8px; border:1px solid #2b3340; background:#1b212b; color:#e8ecf2; cursor:pointer; }
        .user:hover { border-color:#3f8cff; }
        .user.active { background:#1e3a5f; border-color:#3f8cff; }
        .user b { display:block; font-size:12px; margin-bottom:2px; }
        .user small { display:block; color:#8b97a8; font-size:10.5px; }
        .badge { display:inline-block; margin-left:5px; padding:1px 5px; border-radius:5px;
                 background:#4a3a00; color:#ffd166; font-size:9px; font-weight:700; }
        .row { display:flex; gap:6px; }
        .btn { flex:1; padding:7px 8px; border-radius:8px; border:1px solid #2b3340;
               background:#1b212b; color:#e8ecf2; cursor:pointer; font-size:11px; text-align:center;
               text-decoration:none; display:block; }
        .btn:hover { border-color:#3f8cff; }
        .btn.warn:hover { border-color:#ff8a80; color:#ff8a80; }
        input { width:100%; padding:6px 8px; border-radius:8px; border:1px solid #2b3340;
                background:#0f141b; color:#e8ecf2; font-size:12px; margin-bottom:6px; }
        .hint { color:#6f7c8d; font-size:10px; line-height:1.45; }
      </style>
      <button class="pill" title="Открыть debug-панель" hidden>🐞</button>
      <div class="panel">
        <div class="head">
          <span class="title">DEBUG MODE</span>
          <button class="x" title="Свернуть">✕</button>
        </div>
        <div class="section">
          <div class="label">Тестовый пользователь</div>
          <div class="users"></div>
        </div>
        <div class="section">
          <div class="label">Виртуальный Telegram</div>
          <div class="row">
            <a class="btn" href="/__debug__/channel" target="_blank" rel="noopener">📢 Канал и ЛС</a>
          </div>
        </div>
        <div class="section">
          <div class="label">Экран ставок по ID</div>
          <input class="annid" type="number" min="1" placeholder="id объявления" />
          <div class="row">
            <button class="btn go-bid">Ставка</button>
            <button class="btn go-bids">Список ставок</button>
          </div>
        </div>
        <div class="section">
          <div class="label">Данные</div>
          <div class="row">
            <button class="btn warn reseed">Пересоздать</button>
            <button class="btn clear">Очистить лог</button>
          </div>
          <div class="hint" style="margin-top:7px">
            Пересоздание удаляет все объявления в debug-базе и заново заполняет её тестовыми данными.
          </div>
        </div>
      </div>
    `;

    const pill = root.querySelector(".pill");
    const panel = root.querySelector(".panel");

    function setOpen(open) {
      pill.hidden = open;
      panel.hidden = !open;
      localStorage.setItem("devmodeToolbarOpen", open ? "1" : "0");
    }
    setOpen(startOpen);
    pill.addEventListener("click", () => setOpen(true));
    root.querySelector(".x").addEventListener("click", () => setOpen(false));

    const list = root.querySelector(".users");
    users.forEach((user) => {
      const button = document.createElement("button");
      button.className = "user" + (user.key === current ? " active" : "");
      const admin = user.is_admin ? '<span class="badge">ADMIN</span>' : "";
      const handle = user.username ? `@${user.username}` : "без username";
      // The longer note lives in the tooltip so the panel stays compact.
      button.title = user.note;
      button.innerHTML = `<b>${user.label}${admin}</b><small>${handle} · id ${user.id}</small>`;
      button.addEventListener("click", () => {
        if (user.key === current) return;
        window.location.href = urlWith({ as: user.key });
      });
      list.appendChild(button);
    });

    const annInput = root.querySelector(".annid");
    root.querySelector(".go-bid").addEventListener("click", () => {
      const id = parseInt(annInput.value, 10);
      if (id > 0) window.location.href = urlWith({ bid: id, bids: null });
    });
    root.querySelector(".go-bids").addEventListener("click", () => {
      const id = parseInt(annInput.value, 10);
      if (id > 0) window.location.href = urlWith({ bids: id, bid: null });
    });

    root.querySelector(".reseed").addEventListener("click", async () => {
      if (!window.confirm("Удалить все debug-объявления и заново залить тестовые данные?")) return;
      await fetch("/__debug__/reseed", { method: "POST" });
      window.location.href = urlWith({ bid: null, bids: null });
    });
    root.querySelector(".clear").addEventListener("click", async () => {
      await fetch("/__debug__/outbox/clear", { method: "POST" });
      window.alert("Лог виртуального Telegram очищен.");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mountToolbar);
  } else {
    mountToolbar();
  }

  console.info(
    `[debug-tg] ready — user "${config.currentUser}" (id ${config.initDataUnsafe?.user?.id}), start_param: ${
      config.startParam || "—"
    }`
  );
})();
