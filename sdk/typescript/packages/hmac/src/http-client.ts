/** Options for HTTP request methods. */
export interface RequestOptions {
  headers?: Record<string, string>;
}

/** Normalized HTTP response, adapter-independent. */
export interface HmacResponse {
  status: number;
  headers: Record<string, string>;
  json(): Promise<unknown>;
  text(): Promise<string>;
}

/** HTTP client with automatic HMAC signing. */
export interface HmacClient {
  get(path: string, options?: RequestOptions): Promise<HmacResponse>;
  post(path: string, body?: string, options?: RequestOptions): Promise<HmacResponse>;
  put(path: string, body?: string, options?: RequestOptions): Promise<HmacResponse>;
  patch(path: string, body?: string, options?: RequestOptions): Promise<HmacResponse>;
  delete(path: string, options?: RequestOptions): Promise<HmacResponse>;
  /** Generic request method for non-standard HTTP methods. */
  request(method: string, path: string, body?: string, options?: RequestOptions): Promise<HmacResponse>;
}

/** Adapter interface that abstracts the underlying HTTP transport (fetch vs axios). */
export interface HttpAdapter {
  request(
    url: string,
    method: string,
    body: string | undefined,
    headers: Record<string, string>
  ): Promise<HmacResponse>;
}

/** Adapter that uses the Fetch API as the underlying HTTP transport. */
export class FetchAdapter implements HttpAdapter {
  private fetchFn: typeof globalThis.fetch;

  constructor(fetchFn?: typeof globalThis.fetch) {
    this.fetchFn = fetchFn ?? globalThis.fetch;
  }

  async request(
    url: string,
    method: string,
    body: string | undefined,
    headers: Record<string, string>
  ): Promise<HmacResponse> {
    const resp = await this.fetchFn(url, { method, body, headers });
    const responseHeaders: Record<string, string> = {};
    resp.headers.forEach((value, key) => {
      responseHeaders[key] = value;
    });

    // Cache the body text so both json() and text() work without double-consuming
    let cachedText: string | undefined;
    return {
      status: resp.status,
      headers: responseHeaders,
      async json() {
        cachedText ??= await resp.text();
        return JSON.parse(cachedText);
      },
      async text() {
        cachedText ??= await resp.text();
        return cachedText;
      },
    };
  }
}

/**
 * Minimal axios instance type to avoid requiring the axios package at compile time.
 * Users pass their own axios instance; we only depend on the shape.
 */
export interface AxiosInstance {
  request(config: {
    url: string;
    method: string;
    data?: string;
    headers?: Record<string, string>;
  }): Promise<{
    status: number;
    headers: Record<string, string>;
    data: unknown;
  }>;
}

/** Adapter that uses an axios instance as the underlying HTTP transport. */
export class AxiosAdapter implements HttpAdapter {
  private axios: AxiosInstance;

  constructor(axiosInstance: AxiosInstance) {
    this.axios = axiosInstance;
  }

  async request(
    url: string,
    method: string,
    body: string | undefined,
    headers: Record<string, string>
  ): Promise<HmacResponse> {
    const resp = await this.axios.request({ url, method, data: body, headers });
    const data = resp.data;
    const text = typeof data === "string" ? data : JSON.stringify(data);
    return {
      status: resp.status,
      headers: resp.headers as Record<string, string>,
      async json() {
        return typeof data === "string" ? JSON.parse(data) : data;
      },
      async text() {
        return text;
      },
    };
  }
}

/** Options for creating an HmacClientFactory. */
export interface HmacClientFactoryOptions {
  /** Custom fetch function. Ignored if axios is provided. */
  fetchFn?: typeof globalThis.fetch;
  /** Axios instance to use instead of fetch. */
  axios?: AxiosInstance;
}
