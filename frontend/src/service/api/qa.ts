import { request } from '../request';

export function fetchQaHistory(assetId: string) {
  return request<{ asset_id: string; items: Api.Qa.HistoryItem[] }>({
    url: `/qa/assets/${assetId}/history`,
    method: 'get'
  });
}

export function fetchFalsePositiveBoard() {
  return request<Api.Qa.Board>({
    url: '/qa/false-positive-board',
    method: 'get'
  });
}

export function fetchCalibration(productTypeId: string) {
  return request<Api.Qa.Calibration>({
    url: '/qa/calibration',
    method: 'get',
    params: { product_type_id: productTypeId }
  });
}

export function fetchCalibrationDue() {
  return request<{ items: Array<Record<string, unknown>> }>({
    url: '/qa/calibration/due',
    method: 'get'
  });
}
