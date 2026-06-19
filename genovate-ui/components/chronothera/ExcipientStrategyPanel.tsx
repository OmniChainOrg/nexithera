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

export function ExcipientStrategyPanel({ strategies, selected, onChange }: { strategies: ChronoTheraExcipientStrategy[]; selected: ChronoTheraExcipientComponent[]; onChange: (value: ChronoTheraExcipientComponent[]) => void }) {
  function toggle(strategy: ChronoTheraExcipientStrategy) {
    const exists = selected.some((excipient) => excipient.name === strategy.name);
    const amount = defaultAmountForPercentage(strategy.default_percentage);
    onChange(exists ? selected.filter((excipient) => excipient.name !== strategy.name) : [...selected, { name: strategy.name, percentage: strategy.default_percentage, amount, unit: 'mg', amount_mg: excipientAmountInMg(amount, 'mg'), function: strategy.function }]);
  }

  function pct(name: string, percentage: number) {
    onChange(selected.map((excipient) => (excipient.name === name ? { ...excipient, percentage } : excipient)));
  }

  function amount(name: string, nextAmount: number) {
    onChange(selected.map((excipient) => {
      if (excipient.name !== name) return excipient;
      const unit = excipient.unit ?? 'mg';
      return { ...excipient, amount: nextAmount, unit, amount_mg: excipientAmountInMg(nextAmount, unit) };
    }));
  }

  function unit(name: string, nextUnit: ChronoTheraExcipientDoseUnit) {
    onChange(selected.map((excipient) => {
      if (excipient.name !== name) return excipient;
      const nextAmount = excipient.amount ?? excipient.amount_mg ?? defaultAmountForPercentage(excipient.percentage);
      return { ...excipient, amount: nextAmount, unit: nextUnit, amount_mg: excipientAmountInMg(nextAmount, nextUnit) };
    }));
  }

  return (
    <div className="space-y-2">
      <div className="text-xs font-medium">Excipient strategy</div>
      <div className="space-y-2">
        {strategies.map((strategy) => {
          const excipient = selected.find((item) => item.name === strategy.name);
          const selectedAmount = excipient?.amount ?? excipient?.amount_mg ?? defaultAmountForPercentage(strategy.default_percentage);
          return (
            <div key={strategy.name} className="rounded-md border p-3">
              <label className="flex items-center gap-2 text-sm font-medium">
                <input aria-label={`select ${strategy.name}`} type="checkbox" checked={!!excipient} onChange={() => toggle(strategy)} />
                <span>{strategy.name}</span>
              </label>
              <div className="mt-1 text-xs text-muted-foreground">{strategy.function}</div>
              <div className="mt-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_10rem]">
                <label className="text-xs font-medium">
                  {strategy.name} percentage
                  <Input aria-label={`${strategy.name} percentage`} type="number" min={0} max={100} disabled={!excipient} value={excipient?.percentage ?? strategy.default_percentage} onChange={(event) => pct(strategy.name, Number(event.target.value))} />
                </label>
                <label className="text-xs font-medium">
                  {strategy.name} amount
                  <Input aria-label={`${strategy.name} amount`} type="number" min={0} step="any" disabled={!excipient} value={selectedAmount} onChange={(event) => amount(strategy.name, Number(event.target.value))} />
                </label>
                <label className="text-xs font-medium">
                  Unit
                  <Select disabled={!excipient} value={excipient?.unit ?? 'mg'} onValueChange={(value: ChronoTheraExcipientDoseUnit) => unit(strategy.name, value)}>
                    <SelectTrigger aria-label={`${strategy.name} amount unit`}><SelectValue /></SelectTrigger>
                    <SelectContent>{excipientDoseUnits.map((doseUnit) => <SelectItem key={doseUnit.value} value={doseUnit.value}>{doseUnit.label}</SelectItem>)}</SelectContent>
                  </Select>
                </label>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
