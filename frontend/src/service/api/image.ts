import { request } from '../request';

export function fetchImagePolicy() {
  return request<Api.Image.Policy>({
    url: '/images/policy',
    method: 'get'
  });
}

export function fetchImageJobs(revisionId: string) {
  return request<{ revision_id: string; items: Api.Image.JobItem[] }>({
    url: '/images/jobs',
    method: 'get',
    params: { revision_id: revisionId }
  });
}

export function uploadImage(params: {
  revisionId: string;
  slot: number;
  file: File;
  expectedSha256?: string;
  model?: string;
  provider?: string;
}) {
  const formData = new FormData();
  formData.append('file', params.file);

  const headers: Record<string, string> = {};
  if (params.expectedSha256) headers['X-Content-Sha256'] = params.expectedSha256;
  if (params.model) headers['X-Image-Model'] = params.model;
  if (params.provider) headers['X-Image-Provider'] = params.provider;

  return request<Record<string, unknown>>({
    url: `/images/${params.revisionId}/slots/${params.slot}`,
    method: 'post',
    data: formData,
    headers: { ...headers, 'Content-Type': 'multipart/form-data' }
  });
}

export function readImageAsset(assetId: string, token: string) {
  return request<Blob>({
    url: `/images/assets/${assetId}/raw`,
    method: 'get',
    params: { token },
    responseType: 'blob'
  });
}

export function runOcr(assetId: string) {
  return request<Record<string, unknown>>({
    url: `/images/assets/${assetId}/ocr`,
    method: 'post'
  });
}
