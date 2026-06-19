'use client';
import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ChronoTheraHeader } from './ChronoTheraHeader';
import { AssetSelector } from './AssetSelector';
import { FormulationGoalSelector } from './FormulationGoalSelector';
import { RouteOfAdministrationPanel } from './RouteOfAdministrationPanel';
import { ExcipientStrategyPanel } from './ExcipientStrategyPanel';
import { ReleaseProfileChart } from './ReleaseProfileChart';
import { ChronoTheraScorecard } from './ChronoTheraScorecard';
import { EpistemicTracePanel } from './EpistemicTracePanel';
import { CXUSwarmPanel } from './CXUSwarmPanel';
import { GuardianReviewPanel } from './GuardianReviewPanel';
import { SimulationHistoryPanel } from './SimulationHistoryPanel';
import { JsonExportButton } from './JsonExportButton';
import { ResearchUseDisclaimer } from './ResearchUseDisclaimer';
import { useChronoTheraCatalog, useChronoTheraSimulations, useCreateChronoTheraSimulation } from '@/lib/hooks/use-chronothera';
import type { ChronoTheraApiComponent, ChronoTheraDoseUnit, ChronoTheraExcipientComponent, ChronoTheraSimulation } from '@/lib/types/chronothera';

const fallbackObjectives = ['sustained_release','half_life_extension','depot_formulation','oral_delayed_release','co_formulation'];
const fallbackRoutes = ['oral','SC','IM','IV','local','ocular'];
const doseUnits: { value: ChronoTheraDoseUnit; label: string; toMg: number }[] = [
 { value:'mcg', label:'micrograms (mcg)', toMg:0.001 },
 { value:'mg', label:'milligrams (mg)', toMg:1 },
 { value:'g', label:'grams (g)', toMg:1000 },
 { value:'U', label:'Units (UI / U)', toMg:1 },
];
function apiDoseInMg(amount:number, unit:ChronoTheraDoseUnit){ return amount * (doseUnits.find(u=>u.value===unit)?.toMg ?? 1); }
export function ChronoTheraApp(){
 const catalog=useChronoTheraCatalog(); const history=useChronoTheraSimulations(); const create=useCreateChronoTheraSimulation();
 const assets=catalog.data?.assets ?? []; const [assetId,setAssetId]=useState<string>(); const asset=assets.find(a=>a.id===assetId);
 const [objective,setObjective]=useState('sustained_release'); const [route,setRoute]=useState('SC'); const [regBody,setRegBody]=useState('FDA'); const [releaseWeeks,setReleaseWeeks]=useState(8); const [optimize,setOptimize]=useState(true); const [notes,setNotes]=useState('Bridge formulation output into Forge asset dossier after Guardian review.');
 const [apis,setApis]=useState<ChronoTheraApiComponent[]>([{name:'Candidate API', dose_mg:10, dose_amount:10, dose_unit:'mg'}]); const [excipients,setExcipients]=useState<ChronoTheraExcipientComponent[]>([]); const [selected,setSelected]=useState<ChronoTheraSimulation>();
 useEffect(()=>{ if(!assetId && assets[0]) setAssetId(assets[0].id); },[assets,assetId]);
 useEffect(()=>{ if(asset){ setApis(asset.default_apis.map(name=>({name,dose_mg:10,dose_amount:10,dose_unit:'mg',modality:asset.modality}))); setObjective(asset.formulation_objectives[0] ?? objective); setRoute(asset.suggested_routes[0] ?? route); } },[assetId]);
 const validation=useMemo(()=>{ const total=excipients.reduce((s,e)=>s+Number(e.percentage||0),0); if(!apis.length || apis.some(a=>!a.name || (a.dose_amount ?? a.dose_mg)<=0)) return 'At least one API with positive dose is required.'; if(!excipients.length) return 'Select at least one excipient strategy.'; if(excipients.some(e=>(e.amount ?? e.amount_mg)<=0)) return 'Each excipient requires a positive quantitative amount.'; if(total>100) return 'Excipient percentages cannot exceed 100% total.'; return ''; },[apis,excipients]);
 async function run(){ const sim=await create.mutateAsync({ asset_id:assetId, formulation_objective:objective, apis, excipients, release_duration_weeks:releaseWeeks, route_of_administration:route, regulatory_body:regBody, strategy_mode:'cooperative', optimize_excipient_percentages:optimize, pkpd_objective:{ target_exposure:'portfolio planning range', dosing_interval_days:7, peak_to_trough_priority:3, adherence_priority:4 } }); setSelected(sim); }
 return <div className="space-y-4"><ChronoTheraHeader/><ResearchUseDisclaimer/><div className="grid gap-4 xl:grid-cols-[22rem_1fr_22rem]"><div className="space-y-4"><AssetSelector assets={assets} selectedId={assetId} onSelect={setAssetId}/><SimulationHistoryPanel simulations={history.data ?? []} onSelect={setSelected}/></div><div className="space-y-4"><Card><CardHeader><CardTitle className="text-base">B. Formulation strategy workspace</CardTitle></CardHeader><CardContent className="grid gap-4 md:grid-cols-2"><FormulationGoalSelector objectives={catalog.data?.formulation_objectives ?? fallbackObjectives} value={objective} onChange={setObjective}/><RouteOfAdministrationPanel routes={catalog.data?.routes ?? fallbackRoutes} value={route} onChange={setRoute}/><div><label className="text-xs font-medium">Release duration (weeks)</label><Input type="number" min={1} max={24} value={releaseWeeks} onChange={e=>setReleaseWeeks(Number(e.target.value))}/></div><div><label className="text-xs font-medium">Regulatory body</label><Select value={regBody} onValueChange={setRegBody}><SelectTrigger><SelectValue/></SelectTrigger><SelectContent>{(catalog.data?.regulatory_bodies ?? ['FDA','EMA','PMDA']).map(r=><SelectItem key={r} value={r}>{r}</SelectItem>)}</SelectContent></Select></div><div className="md:col-span-2"><label className="text-xs font-medium">Selected APIs</label>{apis.map((a,i)=><div key={i} className="mt-2 grid grid-cols-[1fr_7rem_10rem] gap-2"><Input aria-label="API name" value={a.name} onChange={e=>setApis(apis.map((x,n)=>n===i?{...x,name:e.target.value}:x))}/><Input aria-label="API dose" type="number" min={0} step="any" value={a.dose_amount ?? a.dose_mg} onChange={e=>{ const amount=Number(e.target.value); const unit=a.dose_unit ?? 'mg'; setApis(apis.map((x,n)=>n===i?{...x,dose_amount:amount,dose_unit:unit,dose_mg:apiDoseInMg(amount,unit)}:x)); }}/><Select value={a.dose_unit ?? 'mg'} onValueChange={(unit:ChronoTheraDoseUnit)=>setApis(apis.map((x,n)=>{ if(n!==i) return x; const amount=x.dose_amount ?? x.dose_mg; return {...x,dose_amount:amount,dose_unit:unit,dose_mg:apiDoseInMg(amount,unit)}; }))}><SelectTrigger aria-label="API dose unit"><SelectValue/></SelectTrigger><SelectContent>{doseUnits.map(unit=><SelectItem key={unit.value} value={unit.value}>{unit.label}</SelectItem>)}</SelectContent></Select></div>)}</div><div className="md:col-span-2"><ExcipientStrategyPanel strategies={catalog.data?.excipient_strategies ?? []} selected={excipients} onChange={setExcipients}/></div><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={optimize} onChange={e=>setOptimize(e.target.checked)}/> Optimize excipient percentages</label><div className="md:col-span-2"><label className="text-xs font-medium">Strategy notes</label><Textarea value={notes} onChange={e=>setNotes(e.target.value)}/></div>{validation && <div className="text-sm text-destructive">{validation}</div>}<Button disabled={!!validation || create.isPending} onClick={run}>Run ChronoThera simulation</Button><JsonExportButton simulation={selected}/></CardContent></Card><ReleaseProfileChart simulation={selected}/><ChronoTheraScorecard simulation={selected}/></div><div className="space-y-4"><GuardianReviewPanel simulation={selected}/><EpistemicTracePanel simulation={selected}/><CXUSwarmPanel simulation={selected}/></div></div></div>
}
