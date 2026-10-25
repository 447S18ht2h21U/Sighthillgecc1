import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { InstallationScheduling } from '../../src/InstallationScheduling';

type Pending = {
  path: string;
  method: string;
  settled: boolean;
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
};

const projects = [
  {
    id: '11111111-1111-4111-8111-111111111111',
    code: 'TEST-PROJECT-A',
    customer_name: 'Synthetic Customer A',
    location: 'Test Location A',
  },
  {
    id: '22222222-2222-4222-8222-222222222222',
    code: 'TEST-PROJECT-B',
    customer_name: 'Synthetic Customer B',
    location: 'Test Location B',
  },
];

const managers = [{
  id: '33333333-3333-4333-8333-333333333333',
  username: 'synthetic_manager',
  first_name: 'Synthetic',
  last_name: 'Manager',
}];

const schedules = [
  {
    id: '44444444-4444-4444-8444-444444444444',
    project: '11111111-1111-4111-8111-111111111111',
    scheduled_date: '2026-11-15',
    installation_manager: '33333333-3333-4333-8333-333333333333',
    status: 'SCHEDULED',
  },
  {
    id: '55555555-5555-4555-8555-555555555555',
    project: '22222222-2222-4222-8222-222222222222',
    scheduled_date: '2026-11-16',
    installation_manager: '33333333-3333-4333-8333-333333333333',
    status: 'SCHEDULED',
  },
];

const requests: Pending[] = [];

const mockApi = <T,>(
  path: string,
  method = 'GET',
  _data?: unknown,
): Promise<T> => {
  if (path.startsWith('operational-projects/?')) {
    return Promise.resolve({
      results: projects,
      next: null,
    } as T);
  }

  if (path.startsWith('installation-schedules/?')) {
    return Promise.resolve({
      results: schedules.map(schedule => ({ ...schedule })),
      next: null,
    } as T);
  }

  if (path === 'installation-managers/') {
    return Promise.resolve(managers as T);
  }

  return new Promise<T>((resolve, reject) => {
    requests.push({
      path,
      method,
      settled: false,
      resolve: value => resolve(value as T),
      reject,
    });
    window.dispatchEvent(new Event('mock-request'));
  });
};

declare global {
  interface Window {
    veridianTest: {
      pending: () => {
        index: number;
        path: string;
        method: string;
        settled: boolean;
      }[];
      resolve: (index: number, result: unknown) => void;
      reject: (index: number, reason: string) => void;
      ready: (projectId: string, eligible: boolean) => unknown;
      setScheduleStatus: (
        scheduleId: string,
        status: 'SCHEDULED' | 'COMPLETED' | 'CANCELLED'
      ) => void;
    };
  }
}

window.veridianTest = {
  pending: () => requests.map((request, index) => ({
    index,
    path: request.path,
    method: request.method,
    settled: request.settled,
  })),
  resolve: (index, result) => {
    const request = requests[index];
    if (!request || request.settled) {
      throw new Error('Unknown or already settled synthetic request.');
    }
    request.settled = true;
    request.resolve(result);
  },
  reject: (index, reason) => {
    const request = requests[index];
    if (!request || request.settled) {
      throw new Error('Unknown or already settled synthetic request.');
    }
    request.settled = true;
    request.reject(new Error(reason));
  },
  setScheduleStatus: (scheduleId, status) => {
    const schedule = schedules.find(item => item.id === scheduleId);
    if (!schedule) {
      throw new Error('Unknown synthetic installation schedule.');
    }
    schedule.status = status;
  },
  ready: (projectId, eligible) => ({
    project_id: projectId,
    eligible,
    requirements: {
      approved_msr: true,
      contract_signed: true,
      invoice_signed: true,
      cancellation_complete: true,
      waiting_period_complete: true,
      deposit_verified: eligible,
    },
    blocking_reasons: eligible
      ? []
      : ['Deposit required: bank-confirmed funds are insufficient.'],
  }),
};

function Harness() {
  const [selected, setSelected] = useState('');

  return (
    <InstallationScheduling
      api={mockApi}
      selectedProjectId={selected}
      onProjectSelected={setSelected}
      onReturnToProject={() => undefined}
    />
  );
}

createRoot(document.getElementById('root')!).render(<Harness />);
