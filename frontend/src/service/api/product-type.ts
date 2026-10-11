import { request } from '../request';

export function fetchProductTypes() {
  return request<{ items: Api.ProductType.Item[]; total: number }>({
    url: '/product-types',
    method: 'get'
  });
}

export function createProductType(params: Api.ProductType.UpsertParams) {
  return request<Api.ProductType.Item>({
    url: '/product-types',
    method: 'post',
    data: params
  });
}

export function updateProductType(productTypeCode: string, params: { sequence_width: number; is_enabled?: boolean }) {
  return request<Api.ProductType.Item>({
    url: `/product-types/${productTypeCode}`,
    method: 'patch',
    data: params
  });
}

export function fetchNextSkuPreview(productTypeCode: string) {
  return request<{ product_type_code: string; next_sku: string }>({
    url: `/product-types/${productTypeCode}/next-preview`,
    method: 'get'
  });
}
