"use client";

import { useEffect } from "react";

/**
 * Tells Telegram the Mini App is ready and opens it at full height.
 * In a regular browser `window.Telegram.WebApp` has no init data, so we
 * leave the page alone there.
 */
export function TelegramWebApp() {
  useEffect(() => {
    const webApp = window.Telegram?.WebApp;
    if (!webApp?.initData) return;

    webApp.ready();
    webApp.expand();
    webApp.setHeaderColor?.("bg_color");
  }, []);

  return null;
}
