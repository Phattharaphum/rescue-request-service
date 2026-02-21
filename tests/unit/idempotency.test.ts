import { generateIdempotencyKey, checkIdempotency } from '../../src/domain/idempotency';
import { RescueRequestStatus } from '../../src/domain/models';

const baseInput = {
  incidentId: 'INC-001',
  requesterName: 'Alice Johnson',
  description: 'Person trapped on rooftop',
  location: '123 Maple Street',
};

describe('generateIdempotencyKey', () => {
  it('generates the same key for identical inputs', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey(baseInput);
    expect(key1).toBe(key2);
  });

  it('generates different keys for different incidentId', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey({ ...baseInput, incidentId: 'INC-002' });
    expect(key1).not.toBe(key2);
  });

  it('generates different keys for different requesterName', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey({ ...baseInput, requesterName: 'Bob Smith' });
    expect(key1).not.toBe(key2);
  });

  it('generates different keys for different description', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey({ ...baseInput, description: 'Different description' });
    expect(key1).not.toBe(key2);
  });

  it('generates different keys for different location', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey({ ...baseInput, location: 'Different location' });
    expect(key1).not.toBe(key2);
  });

  it('is case-insensitive and trims whitespace', () => {
    const key1 = generateIdempotencyKey(baseInput);
    const key2 = generateIdempotencyKey({
      incidentId: '  INC-001  ',
      requesterName: 'ALICE JOHNSON',
      description: 'Person Trapped On Rooftop',
      location: '123 MAPLE STREET',
    });
    expect(key1).toBe(key2);
  });

  it('returns a non-empty hex string', () => {
    const key = generateIdempotencyKey(baseInput);
    expect(key).toMatch(/^[a-f0-9]{64}$/);
  });
});

describe('checkIdempotency', () => {
  const existingRequest = {
    requestId: 'req-001',
    incidentId: 'INC-001',
    requesterName: 'Alice Johnson',
    description: 'Person trapped on rooftop',
    location: '123 Maple Street',
    status: RescueRequestStatus.PENDING,
    version: 1,
    createdAt: '2024-03-15T08:30:00.000Z',
    updatedAt: '2024-03-15T08:30:00.000Z',
    idempotencyKey: 'matching-key',
  };

  it('returns the existing request when idempotency key matches', () => {
    const result = checkIdempotency('matching-key', existingRequest);
    expect(result).toBe(existingRequest);
  });

  it('returns null when idempotency key does not match', () => {
    const result = checkIdempotency('different-key', existingRequest);
    expect(result).toBeNull();
  });

  it('returns null when existingRequest is null', () => {
    const result = checkIdempotency('some-key', null);
    expect(result).toBeNull();
  });
});
