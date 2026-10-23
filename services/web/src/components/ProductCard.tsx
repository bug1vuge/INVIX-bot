import type { Product } from "@/lib/types";

type Props = {
  product: Product;
  priority?: boolean;
};

export function ProductCard({ product, priority = false }: Props) {
  return (
    <li className="card">
      <div className="card__media">
        {/* Plain img on purpose: see `images.unoptimized` in next.config.ts */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={product.image_url}
          alt={product.name}
          width={product.image_width}
          height={product.image_height}
          loading={priority ? "eager" : "lazy"}
          fetchPriority={priority ? "high" : "auto"}
          decoding="async"
        />
      </div>
      <p className="card__name">{product.name}</p>
    </li>
  );
}
