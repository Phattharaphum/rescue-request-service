import { APIGatewayProxyEvent, APIGatewayProxyResult } from 'aws-lambda';

export function success(statusCode: number, body: unknown): APIGatewayProxyResult {
  return {
    statusCode,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  };
}

export function error(
  statusCode: number,
  code: string,
  message: string,
): APIGatewayProxyResult {
  return {
    statusCode,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ code, message }),
  };
}

export function parseBody<T = unknown>(event: APIGatewayProxyEvent): T {
  if (!event.body) {
    throw new Error('Request body is required');
  }
  return JSON.parse(event.body) as T;
}

export function parsePathParam(
  event: APIGatewayProxyEvent,
  param: string,
): string {
  const value = event.pathParameters?.[param];
  if (!value) {
    throw new Error(`Missing path parameter: ${param}`);
  }
  return value;
}

export function parseQueryParam(
  event: APIGatewayProxyEvent,
  param: string,
): string | undefined {
  return event.queryStringParameters?.[param] ?? undefined;
}
