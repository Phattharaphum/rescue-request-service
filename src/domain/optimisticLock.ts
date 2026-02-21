import { OptimisticLockError } from './errors';

export function checkVersion(expected: number, actual: number): void {
  if (expected !== actual) {
    throw new OptimisticLockError(
      `Version mismatch: expected ${expected}, got ${actual}. The resource was modified by another process.`,
    );
  }
}
