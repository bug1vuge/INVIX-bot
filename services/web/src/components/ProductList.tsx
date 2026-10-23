"use client";

import { useState } from "react";

import { fetchProductsInBrowser } from "@/lib/api";
import type { Product } from "@/lib/types";

import { ProductCard } from "./ProductCard";

type Props = {
  initialItems: Product[];
  initialCursor: string | null;
};

const ABOVE_THE_FOLD = 4;

export function ProductList({ initialItems, initialCursor }: Props) {
  const [items, setItems] = useState(initialItems);
  const [cursor, setCursor] = useState(initialCursor);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);

  async function loadMore() {
    if (!cursor || loading) return;
    setLoading(true);
    setError(false);
    try {
      const page = await fetchProductsInBrowser(cursor);
      setItems((current) => {
        // A product can be returned twice if pages shift; keep ids unique.
        const known = new Set(current.map((item) => item.id));
        return [...current, ...page.items.filter((item) => !known.has(item.id))];
      });
      setCursor(page.next_cursor);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }

  if (items.length === 0) {
    return <p className="empty">Товаров пока нет</p>;
  }

  return (
    <>
      <ul className="grid">
        {items.map((product, index) => (
          <ProductCard key={product.id} product={product} priority={index < ABOVE_THE_FOLD} />
        ))}
      </ul>

      {error && (
        <p className="notice" role="alert">
          Не удалось загрузить товары. Попробуйте ещё раз.
        </p>
      )}

      {cursor && (
        <button className="more" type="button" onClick={loadMore} disabled={loading}>
          {loading ? "Загружаем…" : "Показать ещё"}
        </button>
      )}
    </>
  );
}
