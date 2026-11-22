import { useSyncExternalStore } from 'react';

export type FictionalScenarioField =
  | 'payment'
  | 'equipment'
  | 'materials'
  | 'dealerFee'
  | 'leadCost'
  | 'otherVendor'
  | 'vendorPaid'
  | 'hours'
  | 'hourlyRate';

export type FictionalScenarioValues =
  Record<FictionalScenarioField, string>;

const initial: FictionalScenarioValues = {
  payment: '13500.00',
  equipment: '4800.00',
  materials: '1200.00',
  dealerFee: '0.00',
  leadCost: '0.00',
  otherVendor: '0.00',
  vendorPaid: '0.00',
  hours: '8.00',
  hourlyRate: '30.00',
};

let snapshot: FictionalScenarioValues = { ...initial };

const subscribers = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  subscribers.add(listener);
  return () => subscribers.delete(listener);
}

function getSnapshot(): FictionalScenarioValues {
  return snapshot;
}

export function updateFictionalScenario(
  field: FictionalScenarioField,
  value: string,
): void {
  if (snapshot[field] === value) return;

  snapshot = { ...snapshot, [field]: value };
  subscribers.forEach(listener => listener());
}

export function resetFictionalScenario(): void {
  snapshot = { ...initial };
  subscribers.forEach(listener => listener());
}

export function useFictionalScenario(): FictionalScenarioValues {
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}

export function useScenarioInput(
  field: FictionalScenarioField,
): [string, (value: string) => void] {
  const values = useFictionalScenario();

  return [
    values[field],
    (value: string) => updateFictionalScenario(field, value),
  ];
}
