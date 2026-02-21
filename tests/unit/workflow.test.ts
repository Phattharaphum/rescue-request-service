import { isValidTransition } from '../../src/domain/workflow';
import { RescueRequestStatus } from '../../src/domain/models';

describe('isValidTransition', () => {
  describe('PENDING transitions', () => {
    it('allows PENDING -> DISPATCHED', () => {
      expect(isValidTransition(RescueRequestStatus.PENDING, RescueRequestStatus.DISPATCHED)).toBe(true);
    });

    it('allows PENDING -> CANCELLED', () => {
      expect(isValidTransition(RescueRequestStatus.PENDING, RescueRequestStatus.CANCELLED)).toBe(true);
    });

    it('disallows PENDING -> RESOLVED', () => {
      expect(isValidTransition(RescueRequestStatus.PENDING, RescueRequestStatus.RESOLVED)).toBe(false);
    });

    it('disallows PENDING -> PENDING', () => {
      expect(isValidTransition(RescueRequestStatus.PENDING, RescueRequestStatus.PENDING)).toBe(false);
    });
  });

  describe('DISPATCHED transitions', () => {
    it('allows DISPATCHED -> RESOLVED', () => {
      expect(isValidTransition(RescueRequestStatus.DISPATCHED, RescueRequestStatus.RESOLVED)).toBe(true);
    });

    it('allows DISPATCHED -> CANCELLED', () => {
      expect(isValidTransition(RescueRequestStatus.DISPATCHED, RescueRequestStatus.CANCELLED)).toBe(true);
    });

    it('disallows DISPATCHED -> PENDING', () => {
      expect(isValidTransition(RescueRequestStatus.DISPATCHED, RescueRequestStatus.PENDING)).toBe(false);
    });

    it('disallows DISPATCHED -> DISPATCHED', () => {
      expect(isValidTransition(RescueRequestStatus.DISPATCHED, RescueRequestStatus.DISPATCHED)).toBe(false);
    });
  });

  describe('RESOLVED transitions (terminal)', () => {
    it('disallows RESOLVED -> PENDING', () => {
      expect(isValidTransition(RescueRequestStatus.RESOLVED, RescueRequestStatus.PENDING)).toBe(false);
    });

    it('disallows RESOLVED -> DISPATCHED', () => {
      expect(isValidTransition(RescueRequestStatus.RESOLVED, RescueRequestStatus.DISPATCHED)).toBe(false);
    });

    it('disallows RESOLVED -> CANCELLED', () => {
      expect(isValidTransition(RescueRequestStatus.RESOLVED, RescueRequestStatus.CANCELLED)).toBe(false);
    });

    it('disallows RESOLVED -> RESOLVED', () => {
      expect(isValidTransition(RescueRequestStatus.RESOLVED, RescueRequestStatus.RESOLVED)).toBe(false);
    });
  });

  describe('CANCELLED transitions (terminal)', () => {
    it('disallows CANCELLED -> PENDING', () => {
      expect(isValidTransition(RescueRequestStatus.CANCELLED, RescueRequestStatus.PENDING)).toBe(false);
    });

    it('disallows CANCELLED -> DISPATCHED', () => {
      expect(isValidTransition(RescueRequestStatus.CANCELLED, RescueRequestStatus.DISPATCHED)).toBe(false);
    });

    it('disallows CANCELLED -> RESOLVED', () => {
      expect(isValidTransition(RescueRequestStatus.CANCELLED, RescueRequestStatus.RESOLVED)).toBe(false);
    });

    it('disallows CANCELLED -> CANCELLED', () => {
      expect(isValidTransition(RescueRequestStatus.CANCELLED, RescueRequestStatus.CANCELLED)).toBe(false);
    });
  });
});
