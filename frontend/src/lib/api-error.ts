export class ApiError extends Error {
  constructor(public code: string, public status: number, message: string, public requestId?: string, public details?: unknown) {
    super(message); this.name = 'ApiError';
  }
}
