import { api } from '@/lib/api/client';
import type { ChronoTheraCatalog, ChronoTheraSimulation, ChronoTheraSimulationPayload, GuardianReviewPayload } from '@/lib/types/chronothera';

export function getChronoTheraCatalog() { return api.get<ChronoTheraCatalog>('/chronothera/catalog'); }
export function createChronoTheraSimulation(payload: ChronoTheraSimulationPayload) { return api.post<ChronoTheraSimulation>('/chronothera/simulations', payload); }
export function getChronoTheraSimulations() { return api.get<ChronoTheraSimulation[]>('/chronothera/simulations'); }
export function getChronoTheraSimulation(id: string) { return api.get<ChronoTheraSimulation>(`/chronothera/simulations/${id}`); }
export function getAssetChronoTheraSimulations(assetId: string) { return api.get<ChronoTheraSimulation[]>('/chronothera/simulations', { query: { asset_id: assetId } }); }
export function submitGuardianReview(simulationId: string, payload: GuardianReviewPayload) { return api.post<ChronoTheraSimulation>(`/chronothera/simulations/${simulationId}/guardian-review`, payload); }
