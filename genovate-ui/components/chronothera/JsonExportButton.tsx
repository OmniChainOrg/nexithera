import { Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { ChronoTheraSimulation } from '@/lib/types/chronothera';
export function JsonExportButton({ simulation }: { simulation?: ChronoTheraSimulation }) { function exportJson(){ if(!simulation) return; const blob=new Blob([JSON.stringify(simulation,null,2)],{type:'application/json'}); const url=URL.createObjectURL(blob); const a=document.createElement('a'); a.href=url; a.download=`${simulation.id}.json`; a.click(); URL.revokeObjectURL(url); } return <Button onClick={exportJson} disabled={!simulation}><Download className="h-4 w-4"/>Export JSON dossier artifact</Button> }
