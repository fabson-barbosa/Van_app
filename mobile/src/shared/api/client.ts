/**
 * Cliente HTTP fino — fetch + baseURL + Bearer + timeout + erro tipado.
 *
 * `ApiError` distingue erro de DOMÍNIO (409, a máquina de estados recusou a
 * transição — CLAUDE.md §4/§7) de qualquer outro HTTP; `NetworkError` é o
 * caso que a fila offline (`shared/offline/sync.ts`) trata como "sem
 * sinal, tentar de novo depois" em vez de "erro definitivo".
 */
const TIMEOUT_MS = 15_000;

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export class NetworkError extends Error {
  constructor(causa?: unknown) {
    super("Falha de rede");
    this.name = "NetworkError";
    this.cause = causa;
  }
}

interface ApiConfig {
  baseUrl: string;
  getToken: () => Promise<string | null>;
  onUnauthorized: () => void;
}

// `10.0.2.2` é o alias padrão do emulador Android para o `localhost` da
// máquina host — ajustável em tempo de execução via `configurarApi` (ex.:
// apontar para um dispositivo físico na mesma rede, ou para staging).
const config: ApiConfig = {
  baseUrl: "http://10.0.2.2:8000",
  getToken: async () => null,
  onUnauthorized: () => {},
};

export function configurarApi(opts: Partial<ApiConfig>): void {
  Object.assign(config, opts);
}

async function requisitar<T>(path: string, init: RequestInit): Promise<T> {
  const token = await config.getToken();
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

  let resposta: Response;
  try {
    resposta = await fetch(`${config.baseUrl}${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
      signal: controller.signal,
    });
  } catch (causa) {
    throw new NetworkError(causa);
  } finally {
    clearTimeout(timeoutId);
  }

  if (resposta.status === 401) {
    config.onUnauthorized();
    throw new ApiError(401, "Sessão expirada. Faça login novamente.");
  }

  if (!resposta.ok) {
    let detail = `Erro ${resposta.status}`;
    try {
      const corpo = (await resposta.json()) as { detail?: string };
      if (corpo.detail) detail = corpo.detail;
    } catch {
      // corpo não é JSON — mantém a mensagem genérica
    }
    throw new ApiError(resposta.status, detail);
  }

  if (resposta.status === 204) return undefined as T;
  return (await resposta.json()) as T;
}

export const api = {
  get: <T>(path: string): Promise<T> => requisitar<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown): Promise<T> =>
    requisitar<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown): Promise<T> =>
    requisitar<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
};
