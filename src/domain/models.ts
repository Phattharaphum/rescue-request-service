export enum RescueRequestStatus {
  PENDING = 'PENDING',
  DISPATCHED = 'DISPATCHED',
  RESOLVED = 'RESOLVED',
  CANCELLED = 'CANCELLED',
}

export interface RescueRequest {
  requestId: string;
  incidentId: string;
  requesterName: string;
  description: string;
  location: string;
  status: RescueRequestStatus;
  version: number;
  createdAt: string;
  updatedAt: string;
  idempotencyKey?: string;
}

export interface CreateRequestInput {
  incidentId: string;
  requesterName: string;
  description: string;
  location: string;
}

export interface PatchStatusInput {
  status: RescueRequestStatus;
  reason?: string;
  version: number;
}
