import type { ProductPage } from "./types";

export const PAGE_SIZE = 20;

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function buildQuery(cursor?: string | null): string {
  const params = new URLSearchParams({ limit: String(PAGE_SIZE) });
  if (cursor) params.set("cursor", cursor);
  return params.toString();
}

async function request(url: string, init?: RequestInit): Promise<ProductPage> {
  const response = await fetch(url, {
    ...init,
    headers: { Accept: "application/json", ...init?.headers },
  });
  if (!response.ok) {
    throw new ApiError(`Catalog API responded with ${response.status}`, response.status);
  }
  return response.json() as Promise<ProductPage>;
}

/**
 * Server side: goes straight to the internal gateway, bypassing the public
 * edge. Not cached, the catalog must show new products immediately.
 */
export function fetchProductsOnServer(cursor?: string | null): Promise<ProductPage> {
  const baseUrl = process.env.API_INTERNAL_URL ?? "http://gateway:8081";
  return request(`${baseUrl}/api/v1/products?${buildQuery(cursor)}`, {
    cache: "no-store",
    signal: AbortSignal.timeout(5000),
  });
}

/** Browser side: same origin, the gateway routes /api to the API service. */
export function fetchProductsInBrowser(cursor: string): Promise<ProductPage> {
  return request(`/api/v1/products?${buildQuery(cursor)}`);
}
