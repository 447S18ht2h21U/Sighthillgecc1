import React from 'react';
import { createRoot } from 'react-dom/client';
import { TechnicianAssignments } from '../../src/TechnicianAssignments';

const PROJECT_ID = '11111111-1111-4111-8111-111111111111';

const projects = [{
  id: PROJECT_ID,
  code: 'SYNTHETIC-TEST-PROJECT',
  customer_name: 'Synthetic Customer',
  location: 'Synthetic Location',
}];

const technicians = [{
  id: '22222222-2222-4222-8222-222222222222',
  username: 'synthetic_technician',
  first_name: 'Synthetic',
  last_name: 'Technician',
}];

const assignments = [
  {
    id: '33333333-3333-4333-8333-333333333333',
    project: PROJECT_ID,
    technical_associate: technicians[0].id,
    technician_username: 'synthetic_technician',
    technician_first_name: 'Synthetic',
    technician_last_name: 'Technician',
    assigned_by: 'synthetic_manager',
    effective_date: '2026-10-24',
    status: 'ACTIVE',
    ended_at: null,
  },
  {
    id: '44444444-4444-4444-8444-444444444444',
    project: PROJECT_ID,
    technical_associate: technicians[0].id,
    technician_username: 'synthetic_technician',
    technician_first_name: 'Synthetic',
    technician_last_name: 'Technician',
    assigned_by: 'synthetic_manager',
    effective_date: '2026-10-10',
    status: 'ENDED',
    ended_at: '2026-10-20T14:30:00Z',
  },
];

const requests: { path: string; method: string }[] = [];

const mockApi = <T,>(
  path: string,
  method = 'GET',
  _data?: unknown,
): Promise<T> => {
  requests.push({ path, method });

  if (method !== 'GET') {
    return Promise.reject(new Error('SAFETY STOP: Write request blocked.'));
  }

  if (path.startsWith('operational-projects/?')) {
    return Promise.resolve({
      results: projects,
      count: projects.length,
      next: null,
    } as T);
  }

  if (path.startsWith('technical-assignment-history/?')) {
    return Promise.resolve({
      results: assignments.map(assignment => ({ ...assignment })),
      count: assignments.length,
      next: null,
    } as T);
  }

  if (path === 'technicians/') {
    return Promise.resolve(technicians as T);
  }

  return Promise.reject(new Error('Unexpected synthetic API request.'));
};

declare global {
  interface Window {
    veridianTechnicianStatusTest: {
      requests: () => { path: string; method: string }[];
    };
  }
}

window.veridianTechnicianStatusTest = {
  requests: () => requests.map(request => ({ ...request })),
};

createRoot(document.getElementById('root')!).render(
  <TechnicianAssignments api={mockApi} />
);
