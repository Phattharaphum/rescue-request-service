import { isDuplicate } from '../../src/domain/dedupe';
import { RescueRequest, RescueRequestStatus } from '../../src/domain/models';

function makeRequest(overrides: Partial<RescueRequest> = {}): RescueRequest {
  return {
    requestId: 'req-001',
    incidentId: 'INC-001',
    requesterName: 'Alice Johnson',
    description: 'Person trapped',
    location: '123 Maple St',
    status: RescueRequestStatus.PENDING,
    version: 1,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ...overrides,
  };
}

describe('isDuplicate', () => {
  it('detects duplicate with same incidentId and requesterName within 5 minutes', () => {
    const existing = makeRequest({ createdAt: new Date().toISOString() });
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [existing],
    );
    expect(result).toBe(true);
  });

  it('does not flag duplicate when existing is outside the 5-minute window', () => {
    const sixMinutesAgo = new Date(Date.now() - 6 * 60 * 1000).toISOString();
    const existing = makeRequest({ createdAt: sixMinutesAgo });
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [existing],
    );
    expect(result).toBe(false);
  });

  it('does not flag duplicate for different incidentId', () => {
    const existing = makeRequest({ incidentId: 'INC-002', createdAt: new Date().toISOString() });
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [existing],
    );
    expect(result).toBe(false);
  });

  it('does not flag duplicate for different requesterName', () => {
    const existing = makeRequest({ requesterName: 'Bob Smith', createdAt: new Date().toISOString() });
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [existing],
    );
    expect(result).toBe(false);
  });

  it('returns false when existing requests array is empty', () => {
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [],
    );
    expect(result).toBe(false);
  });

  it('detects duplicate exactly at the 5-minute boundary', () => {
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000).toISOString();
    const existing = makeRequest({ createdAt: fiveMinutesAgo });
    const result = isDuplicate(
      { incidentId: 'INC-001', requesterName: 'Alice Johnson' },
      [existing],
    );
    expect(result).toBe(true);
  });
});
