import type { Metadata, Viewport } from "next";
import Script from "next/script";

import { TelegramWebApp } from "@/components/TelegramWebApp";

import "./globals.css";

export const metadata: Metadata = {
  title: "Каталог",
  description: "Каталог товаров",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#17212b" },
  ],
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru">
      <body>
        {/* Must load before hydration: it sets the --tg-theme-* CSS variables. */}
        <Script src="https://telegram.org/js/telegram-web-app.js" strategy="beforeInteractive" />
        <TelegramWebApp />
        {children}
      </body>
    </html>
  );
}
