"use client";

import { useEffect } from "react";

type Props = {
  error: unknown;
  retry: () => void;
};

export default function CatalogError({ error, retry }: Props) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <main className="page">
      <h1 className="title">Каталог</h1>
      <p className="notice" role="alert">
        Каталог временно недоступен.
      </p>
      <button className="more" type="button" onClick={() => retry()}>
        Обновить
      </button>
    </main>
  );
}
