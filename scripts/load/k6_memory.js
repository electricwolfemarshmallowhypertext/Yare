import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  vus: 25,
  duration: '1m',
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<500'],
  },
};

const BASE = __ENV.BASE_URL || 'http://localhost:8000';
const TOKEN = __ENV.API_TOKEN || 'REPLACE_ME';

export default function () {
  // health
  let r1 = http.get(`${BASE}/health`);
  check(r1, { 'health ok/degraded': (r) => r.status === 200 });

  // write
  const mem = {
    id: `m_${__ITER}_${__VU}`,
    text: 'Load test memory',
    type: 'fact',
    salience: 0.5,
    created_at: new Date().toISOString(),
    thread_id: 't1',
    user_id: 'u1',
    persona_id: 'p1',
  };
  let r2 = http.post(`${BASE}/memories`, JSON.stringify(mem), {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`,
    },
  });
  check(r2, { 'store 200': (r) => r.status === 200 || r.status === 201 || r.status === 409 });

  // read
  let r3 = http.get(`${BASE}/memories/${mem.id}`, {
    headers: { 'Authorization': `Bearer ${TOKEN}` },
  });
  check(r3, { 'get 200/404': (r) => r.status === 200 || r.status === 404 });

  sleep(0.5);
}