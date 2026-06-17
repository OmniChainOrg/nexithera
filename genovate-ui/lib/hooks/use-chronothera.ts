import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { createChronoTheraSimulation, getChronoTheraCatalog, getChronoTheraSimulations, submitGuardianReview } from '@/lib/api/chronothera';
import type { ChronoTheraSimulationPayload, GuardianReviewPayload } from '@/lib/types/chronothera';

export const chronotheraKeys = { catalog: ['chronothera','catalog'] as const, simulations: ['chronothera','simulations'] as const };
export function useChronoTheraCatalog() { return useQuery({ queryKey: chronotheraKeys.catalog, queryFn: getChronoTheraCatalog }); }
export function useChronoTheraSimulations() { return useQuery({ queryKey: chronotheraKeys.simulations, queryFn: getChronoTheraSimulations }); }
export function useCreateChronoTheraSimulation() { const qc = useQueryClient(); return useMutation({ mutationFn: (payload: ChronoTheraSimulationPayload) => createChronoTheraSimulation(payload), onSuccess: () => qc.invalidateQueries({ queryKey: chronotheraKeys.simulations }) }); }
export function useSubmitGuardianReview(simulationId: string) { const qc = useQueryClient(); return useMutation({ mutationFn: (payload: GuardianReviewPayload) => submitGuardianReview(simulationId, payload), onSuccess: () => qc.invalidateQueries({ queryKey: chronotheraKeys.simulations }) }); }
