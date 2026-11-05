import { ApiError } from './api-error';
export type ApiEnvelope<T> = { code: string; message: string; data: T; request_id: string };
export type RequestOptions = { method?: string; body?: unknown; headers?: HeadersInit; signal?: AbortSignal };
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<ApiEnvelope<T>> {
  if (!path.startsWith('/api/v1/')) throw new ApiError('INVALID_API_PATH', 0, '只允许同域接口');
  const headers = new Headers(options.headers);
  const formData = options.body instanceof FormData;
  if (options.body !== undefined && !formData) headers.set('Content-Type','application/json');
  const method = options.method ?? 'GET';
  if (!['GET','HEAD','OPTIONS'].includes(method.toUpperCase()) && typeof document !== 'undefined') {
    const csrf = document.cookie.split('; ').find(c => c.startsWith('talent_csrf='))?.slice('talent_csrf='.length);
    if (csrf) headers.set('X-CSRF-Token',decodeURIComponent(csrf));
  }
  const response = await fetch(path, {method,headers,signal:options.signal,credentials:'include',body:options.body === undefined ? undefined : formData ? options.body as FormData : JSON.stringify(options.body)});
  let result: ApiEnvelope<T>;
  try { result = await response.json(); } catch { throw new ApiError('INVALID_RESPONSE', response.status, '服务返回了无法识别的响应'); }
  if (!response.ok || result.code !== 'OK') throw new ApiError(result.code ?? 'HTTP_ERROR',response.status,result.message ?? '请求失败',result.request_id,result.data);
  return result;
}
