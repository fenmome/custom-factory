import { request } from '../request';

export function fetchPendingQueue(params: { batchId?: string; page: number; pageSize: number }) {
  return request<Api.Page<Api.Review.PendingItem>>({
    url: '/reviews/pending',
    method: 'get',
    params: {
      batch_id: params.batchId,
      page: params.page,
      page_size: params.pageSize
    }
  });
}

export function fetchReviewView(productId: string) {
  return request<Api.Review.View>({
    url: `/reviews/${productId}`,
    method: 'get'
  });
}

export function submitReview(productId: string, params: Api.Review.SubmitParams) {
  return request<Api.Review.SubmitResult>({
    url: `/reviews/${productId}/submit`,
    method: 'post',
    data: params
  });
}

export function fetchReviewStats() {
  return request<Record<string, number>>({
    url: '/reviews/stats/summary',
    method: 'get'
  });
}
