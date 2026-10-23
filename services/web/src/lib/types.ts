export type Product = {
  id: string;
  name: string;
  image_url: string;
  image_width: number;
  image_height: number;
  created_at: string;
};

export type ProductPage = {
  items: Product[];
  next_cursor: string | null;
};
