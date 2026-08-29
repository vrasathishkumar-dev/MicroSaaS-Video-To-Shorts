import api from '@/services/api';
import type { BrollAsset, BrollSource } from '@/types';

/**
 * Non-persisted search result returned by GET /broll/search. Mirrors the
 * backend's search response shape before an asset has been attached to a
 * clip (no `id`/`clip_id`/position fields yet).
 */
export interface BrollSearchResult {
  source: BrollSource;
  source_asset_id: string;
  asset_url: string;
  keyword: string;
}

export interface InsertBrollPayload {
  source: BrollSource;
  source_asset_id: string;
  asset_url: string;
  keyword: string;
  position_start: number;
  position_end: number;
}

/** Shape of GET /clips/{id} when the backend embeds its broll assets. */
interface ClipWithOptionalBroll {
  broll_assets?: BrollAsset[];
}

/**
 * Automatically source and attach B-roll for a clip based on its
 * transcript/keywords. Returns the newly created B-roll assets.
 */
export async function autoSourceBroll(clipId: number): Promise<BrollAsset[]> {
  const { data } = await api.post<BrollAsset[]>(`/clips/${clipId}/broll/auto`);
  return data;
}

/**
 * Search Pexels/Pixabay (or both) for B-roll footage matching a keyword.
 * Results are not yet persisted — call `insertBroll` to attach one to a clip.
 */
export async function searchBroll(
  query: string,
  source?: BrollSource,
): Promise<BrollSearchResult[]> {
  const { data } = await api.get<BrollSearchResult[]>('/broll/search', {
    params: {
      q: query,
      source,
    },
  });
  return data;
}

/** Attach a (searched or auto-sourced) B-roll asset to a clip. */
export async function insertBroll(
  clipId: number,
  payload: InsertBrollPayload,
): Promise<BrollAsset> {
  const { data } = await api.post<BrollAsset>(`/clips/${clipId}/broll`, payload);
  return data;
}

/** Detach/remove a B-roll asset from a clip. */
export async function removeBroll(clipId: number, brollId: number): Promise<void> {
  await api.delete(`/clips/${clipId}/broll/${brollId}`);
}

/**
 * Best-effort fetch of a clip's currently attached B-roll assets.
 *
 * There is no dedicated "list broll for clip" endpoint, so this reads the
 * clip resource directly and defensively handles both a backend that embeds
 * `broll_assets` in the ClipResponse and one that doesn't (returns `[]`).
 */
export async function getClipBrollAssets(clipId: number): Promise<BrollAsset[]> {
  const { data } = await api.get<ClipWithOptionalBroll>(`/clips/${clipId}`);
  return Array.isArray(data.broll_assets) ? data.broll_assets : [];
}
