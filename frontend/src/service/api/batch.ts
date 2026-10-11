import { request } from '../request';

export function fetchBatchList(params: { page: number; pageSize: number }) {
  return request<Api.Page<Api.Batch.Summary>>({
    url: '/batches',
    method: 'get',
    params: normalize(params)
  });
}

export function fetchBatchDetail(batchId: string) {
  return request<Api.Batch.Detail>({
    url: `/batches/${batchId}`,
    method: 'get'
  });
}

export function createBatch(params: Api.Batch.CreateParams) {
  return request<{ batch: Api.Batch.Summary; preparation: Record<string, unknown> }>({
    url: '/batches',
    method: 'post',
    data: params
  });
}

export function prepareBatch(batchId: string) {
  return request<Record<string, unknown>>({
    url: `/batches/${batchId}/prepare`,
    method: 'post'
  });
}

export function fetchBatchProgress(batchId: string) {
  return request<Api.Batch.Progress>({
    url: `/dashboard/batches/${batchId}/progress`,
    method: 'get'
  });
}

function normalize(params: { page: number; pageSize: number }) {
  return { page: params.page, page_size: params.pageSize };
}
