export class NotFoundError extends Error {
  readonly statusCode = 404;
  readonly code = 'NOT_FOUND';

  constructor(message: string) {
    super(message);
    this.name = 'NotFoundError';
  }
}

export class ConflictError extends Error {
  readonly statusCode = 409;
  readonly code = 'CONFLICT';

  constructor(message: string) {
    super(message);
    this.name = 'ConflictError';
  }
}

export class OptimisticLockError extends Error {
  readonly statusCode = 409;
  readonly code = 'OPTIMISTIC_LOCK_CONFLICT';

  constructor(message: string) {
    super(message);
    this.name = 'OptimisticLockError';
  }
}

export class InvalidTransitionError extends Error {
  readonly statusCode = 409;
  readonly code = 'INVALID_TRANSITION';

  constructor(message: string) {
    super(message);
    this.name = 'InvalidTransitionError';
  }
}

export class ValidationError extends Error {
  readonly statusCode = 400;
  readonly code = 'VALIDATION_ERROR';

  constructor(message: string) {
    super(message);
    this.name = 'ValidationError';
  }
}

export class UnprocessableEntityError extends Error {
  readonly statusCode = 422;
  readonly code = 'UNPROCESSABLE_ENTITY';

  constructor(message: string) {
    super(message);
    this.name = 'UnprocessableEntityError';
  }
}

export type DomainError =
  | NotFoundError
  | ConflictError
  | OptimisticLockError
  | InvalidTransitionError
  | ValidationError
  | UnprocessableEntityError;

export function isDomainError(err: unknown): err is DomainError {
  return (
    err instanceof NotFoundError ||
    err instanceof ConflictError ||
    err instanceof OptimisticLockError ||
    err instanceof InvalidTransitionError ||
    err instanceof ValidationError ||
    err instanceof UnprocessableEntityError
  );
}
