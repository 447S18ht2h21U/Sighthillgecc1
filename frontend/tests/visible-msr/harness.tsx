import React from 'react';
import { createRoot } from 'react-dom/client';
import { VisibleMSRDirectory } from '../../src/VisibleMSRDirectory';

type Pending = {
  path: string;
  method: string;
  settled: boolean;
  resolve: (value: unknown) => void;
  reject: (reason: Error) => void;
};

const requests: Pending[] = [];

const recordA = {
  id: '11111111-1111-4111-8111-111111111111',
  number: 2,
  status: 'APPROVED',
  snapshot: {
    customer: 'Synthetic Customer Alpha',
    project_location: 'Fictional Site Alpha',
    scope: 'Synthetic equipment installation',
    discount: '100',
  },
  revision_reason: 'Synthetic revision for browser testing',
  approved_at: '2026-10-01T12:00:00Z',
};

const recordB = {
  id: '22222222-2222-4222-8222-222222222222',
  number: 3,
  status: 'DRAFT',
  snapshot: {
    customer: 'Synthetic Customer Beta',
    project_location: 'Fictional Site Beta',
    scope: 'Synthetic project inspection',
  },
  revision_reason: '',
  approved_at: null,
};

const recordC = {
  id: '33333333-3333-4333-8333-333333333333',
  number: 1,
  status: 'APPROVED',
  snapshot: {
    customer: 'Synthetic Customer Gamma',
    project_location: 'Fictional Site Gamma',
  },
  revision_reason: '',
  approved_at: '2026-10-02T12:00:00Z',
};

const pages = {
  first: {
    count: 3,
    next: 'synthetic-next-page',
    previous: null,
    results: [recordA, recordB],
  },
  second: {
    count: 3,
    next: null,
    previous: 'synthetic-previous-page',
    results: [recordC],
  },
  empty: {
    count: 0,
    next: null,
    previous: null,
    results: [],
  },
};

const mockApi = <T,>(
  path: string,
  method = 'GET',
  _data?: unknown,
): Promise<T> => {
  if (!/^visible-msrs\/\?page=[1-9][0-9]*$/.test(path)) {
    return Promise.reject(new Error(
      'SAFETY STOP: Unexpected synthetic API path: ' + path
    ));
  }

  if (method !== 'GET') {
    return Promise.reject(new Error(
      'SAFETY STOP: Synthetic MSR API is read-only.'
    ));
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
    veridianMSRTest: {
      pending: () => {
        index: number;
        path: string;
        method: string;
        settled: boolean;
      }[];
      resolve: (index: number, page: keyof typeof pages) => void;
      reject: (index: number, message: string) => void;
    };
  }
}

window.veridianMSRTest = {
  pending: () => requests.map((request, index) => ({
    index,
    path: request.path,
    method: request.method,
    settled: request.settled,
  })),
  resolve: (index, page) => {
    const request = requests[index];
    if (!request || request.settled) {
      throw new Error('Unknown or settled synthetic request.');
    }
    if (!Object.prototype.hasOwnProperty.call(pages, page)) {
      throw new Error('Unknown synthetic MSR page.');
    }

    request.settled = true;
    request.resolve(pages[page]);
  },
  reject: (index, message) => {
    const request = requests[index];
    if (!request || request.settled) {
      throw new Error('Unknown or settled synthetic request.');
    }

    request.settled = true;
    request.reject(new Error(message));
  },
};

function Harness() {
  return <VisibleMSRDirectory api={mockApi} />;
}

createRoot(document.getElementById('root')!).render(<Harness />);