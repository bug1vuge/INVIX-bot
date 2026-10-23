import { connection } from "next/server";

import { ProductList } from "@/components/ProductList";
import { fetchProductsOnServer } from "@/lib/api";

export default async function CatalogPage() {
  // Render on every request: the list changes whenever an admin adds a product.
  await connection();
  const page = await fetchProductsOnServer();

  return (
    <main className="page">
      <h1 className="title">Каталог</h1>
      <ProductList initialItems={page.items} initialCursor={page.next_cursor} />
    </main>
  );
}
