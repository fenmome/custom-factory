import { request } from '../request';

export function fetchProductList(params: { batchId?: string; page: number; pageSize: number }) {
  return request<Api.Page<Api.Product.ListItem>>({
    url: '/products',
    method: 'get',
    params: {
      batch_id: params.batchId,
      page: params.page,
      page_size: params.pageSize
    }
  });
}

export function fetchProductDetail(productId: string) {
  return request<Api.Product.Detail>({
    url: `/products/${productId}`,
    method: 'get'
  });
}

export function markReady(productId: string, operationKey: string) {
  return request<Api.Product.ReadyResult>({
    url: `/products/${productId}/ready`,
    method: 'post',
    data: { operation_key: operationKey }
  });
}

export function buildProductData(productId: string) {
  return request<Record<string, unknown>>({
    url: `/products/${productId}/product-data`,
    method: 'post'
  });
}

export function summariseQa(productId: string) {
  return request<Record<string, unknown>>({
    url: `/products/${productId}/summarise-qa`,
    method: 'post'
  });
}
