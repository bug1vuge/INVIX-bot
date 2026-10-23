// Minimal typing for the part of the Telegram Web App API we use.
// Full reference: https://core.telegram.org/bots/webapps

type TelegramWebApp = {
  initData: string;
  colorScheme: "light" | "dark";
  ready: () => void;
  expand: () => void;
  setHeaderColor?: (color: string) => void;
  setBackgroundColor?: (color: string) => void;
};

interface Window {
  Telegram?: {
    WebApp?: TelegramWebApp;
  };
}
