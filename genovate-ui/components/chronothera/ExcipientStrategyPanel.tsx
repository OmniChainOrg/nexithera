import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { ChronoTheraExcipientComponent, ChronoTheraExcipientDoseUnit, ChronoTheraExcipientStrategy } from '@/lib/types/chronothera';

const excipientDoseUnits: { value: ChronoTheraExcipientDoseUnit; label: string }[] = [
 { value: 'mg', label: 'milligrams (mg)' },
 { value: 'g', label: 'grams (g)' },
];

function excipientAmountInMg(amount: number, unit: ChronoTheraExcipientDoseUnit) {
 return unit === 'g' ? amount * 1000 : amount;
}

function defaultAmountForPercentage(percentage: number) {
 return Math.max(1, percentage);
}

export function ExcipientStrategyPanel({ strategies, selected, onChange }: { strategies: ChronoTheraExcipientStrategy[]; selected: ChronoTheraExcipientComponent[]; onChange:(v:ChronoTheraExcipientComponent[])=>void }) {
 function toggle(s:ChronoTheraExcipientStrategy){
  const exists=selected.some(e=>e.name===s.name);
  const amount=defaultAmountForPercentage(s.default_percentage);
  onChange(exists?selected.filter(e=>e.name!==s.name):[...selected,{name:s.name,percentage:s.default_percentage,amount,unit:'mg',amount_mg:excipientAmountInMg(amount,'mg'),function:s.function}]);
 }
 function pct(name:string, percentage:number){ onChange(selected.map(e=>e.name===name?{...e,percentage}:e)); }
 function amount(name:string, nextAmount:number){ onChange(selected.map(e=>{ if(e.name!==name) return e; const unit=e.unit ?? 'mg'; return {...e,amount:nextAmount,unit,amount_mg:excipientAmountInMg(nextAmount,unit)}; })); }
 function unit(name:string, nextUnit:ChronoTheraExcipientDoseUnit){ onChange(selected.map(e=>{ if(e.name!==name) return e; const nextAmount=e.amount ?? e.amount_mg ?? defaultAmountForPercentage(e.percentage); return {...e,amount:nextAmount,unit:nextUnit,amount_mg:excipientAmountInMg(nextAmount,nextUnit)}; })); }
 return <div className="space-y-2"><div className="text-xs font-medium">Excipient strategy</div>{strategies.map(s=>{const e=selected.find(x=>x.name===s.name); const selectedAmount=e?.amount ?? e?.amount_mg ?? defaultAmountForPercentage(s.default_percentage); return <div key={s.name} className="grid gap-2 rounded-md border p-2 md:grid-cols-[auto_1fr_5rem_2rem_7rem_10rem]"><input aria-label={`select ${s.name}`} type="checkbox" checked={!!e} onChange={()=>toggle(s)}/><div className="min-w-0"><div className="font-medium">{s.name}</div><div className="text-xs text-muted-foreground">{s.function}</div></div><Input aria-label={`${s.name} percentage`} type="number" min={0} max={100} disabled={!e} value={e?.percentage ?? s.default_percentage} onChange={(ev)=>pct(s.name, Number(ev.target.value))}/><span className="self-center text-xs">%</span><Input aria-label={`${s.name} amount`} type="number" min={0} step="any" disabled={!e} value={selectedAmount} onChange={(ev)=>amount(s.name, Number(ev.target.value))}/><Select disabled={!e} value={e?.unit ?? 'mg'} onValueChange={(v:ChronoTheraExcipientDoseUnit)=>unit(s.name,v)}><SelectTrigger aria-label={`${s.name} amount unit`}><SelectValue/></SelectTrigger><SelectContent>{excipientDoseUnits.map(u=><SelectItem key={u.value} value={u.value}>{u.label}</SelectItem>)}</SelectContent></Select></div>})}</div>
}
