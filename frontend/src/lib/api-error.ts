/** 标准API异常；仅携带可公开的错误码、消息和请求标识。 */
export class ApiError extends Error {
  constructor(public code: string, public status: number, message: string, public requestId?: string, public details?: unknown) {
    super(message); this.name = 'ApiError';
  }
}
