import { RescueRequestStatus } from '../domain/models';

export enum REQUEST_STATUS {
  PENDING = 'PENDING',
  DISPATCHED = 'DISPATCHED',
  RESOLVED = 'RESOLVED',
  CANCELLED = 'CANCELLED',
}

export const STATUS_TRANSITIONS: Record<RescueRequestStatus, RescueRequestStatus[]> = {
  [RescueRequestStatus.PENDING]: [RescueRequestStatus.DISPATCHED, RescueRequestStatus.CANCELLED],
  [RescueRequestStatus.DISPATCHED]: [RescueRequestStatus.RESOLVED, RescueRequestStatus.CANCELLED],
  [RescueRequestStatus.RESOLVED]: [],
  [RescueRequestStatus.CANCELLED]: [],
};
