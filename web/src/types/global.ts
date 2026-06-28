/** Standard FastAPI wrapper used by Compliance Navigator API */
export interface APIResponse<T> {
  message: string;
  payload: T;
}

export interface PaginatedResult<T> {
  result: T[];
  total: number;
  page: number;
  limit: number;
  totalPages: number;
}
