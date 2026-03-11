import crypto from "node:crypto";

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { SQSClient, ReceiveMessageCommand, DeleteMessageCommand } from "@aws-sdk/client-sqs";
import { DynamoDBDocumentClient, PutCommand, UpdateCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION || "ap-southeast-2";
const QUEUE_URL = process.env.SNS_STREAM_SQS_QUEUE_URL;
const STREAM_TABLE_NAME = process.env.STREAM_TABLE_NAME;
const STREAM_KEY = process.env.STREAM_KEY || "STREAM";
const EVENT_RETENTION_SECONDS = Number.parseInt(process.env.EVENT_RETENTION_SECONDS || "86400", 10);
const POLLER_LOCK_KEY = process.env.POLLER_LOCK_KEY || "POLLER";
const POLLER_LEASE_MS = Number.parseInt(process.env.POLLER_LEASE_MS || "55000", 10);
const POLLER_RUNTIME_BUFFER_MS = 5000;

const sqs = new SQSClient({ region: REGION });
const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }), {
  marshallOptions: { removeUndefinedValues: true }
});

function padTimestamp(input) {
  return String(input).padStart(13, "0");
}

function buildEventKey(event) {
  const timestampValue = Date.parse(event.metadata?.timestamp || "") || Date.now();
  const eventId = event.metadata?.eventId || crypto.randomUUID();
  return `${padTimestamp(timestampValue)}#${eventId}`;
}

function tryParseJson(value) {
  if (typeof value !== "string") {
    return null;
  }

  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export function unwrapSnsEnvelope(body) {
  const parsedBody = tryParseJson(body);
  if (!parsedBody || typeof parsedBody !== "object") {
    return body;
  }

  if (typeof parsedBody.Message === "string") {
    return tryParseJson(parsedBody.Message) ?? parsedBody.Message;
  }

  return parsedBody;
}

export function normalizeEvent(body) {
  const payload = unwrapSnsEnvelope(body);
  if (
    payload &&
    typeof payload === "object" &&
    !Array.isArray(payload) &&
    payload.metadata &&
    payload.body
  ) {
    return payload;
  }

  return {
    metadata: {
      eventType: "rescue-request.unknown",
      eventId: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      partitionKey: "stream-fallback",
      schemaVersion: "1.0",
      source: "rescue-request-stream-poller",
      correlationId: null
    },
    body: payload
  };
}

async function acquireLease(ownerId) {
  const now = Date.now();
  try {
    await ddb.send(new UpdateCommand({
      TableName: STREAM_TABLE_NAME,
      Key: {
        streamKey: "LOCK",
        eventKey: POLLER_LOCK_KEY
      },
      UpdateExpression: "SET leaseOwner = :owner, leaseExpiresAt = :expiresAt, updatedAt = :updatedAt",
      ConditionExpression: "attribute_not_exists(leaseExpiresAt) OR leaseExpiresAt < :now OR leaseOwner = :owner",
      ExpressionAttributeValues: {
        ":owner": ownerId,
        ":expiresAt": now + POLLER_LEASE_MS,
        ":updatedAt": new Date(now).toISOString(),
        ":now": now
      }
    }));
    return true;
  } catch (error) {
    if (error?.name === "ConditionalCheckFailedException") {
      return false;
    }
    throw error;
  }
}

async function releaseLease(ownerId) {
  const now = Date.now();
  try {
    await ddb.send(new UpdateCommand({
      TableName: STREAM_TABLE_NAME,
      Key: {
        streamKey: "LOCK",
        eventKey: POLLER_LOCK_KEY
      },
      UpdateExpression: "SET leaseExpiresAt = :now, updatedAt = :updatedAt",
      ConditionExpression: "leaseOwner = :owner",
      ExpressionAttributeValues: {
        ":owner": ownerId,
        ":now": now,
        ":updatedAt": new Date(now).toISOString()
      }
    }));
  } catch (error) {
    if (error?.name !== "ConditionalCheckFailedException") {
      throw error;
    }
  }
}

async function persistEvent(event) {
  const nowSeconds = Math.floor(Date.now() / 1000);
  await ddb.send(new PutCommand({
    TableName: STREAM_TABLE_NAME,
    Item: {
      streamKey: STREAM_KEY,
      eventKey: buildEventKey(event),
      payload: event,
      createdAt: new Date().toISOString(),
      expiresAt: nowSeconds + EVENT_RETENTION_SECONDS
    }
  }));
}

async function processMessage(message) {
  const event = normalizeEvent(message.Body);
  await persistEvent(event);
  await sqs.send(new DeleteMessageCommand({
    QueueUrl: QUEUE_URL,
    ReceiptHandle: message.ReceiptHandle
  }));
}

export const handler = async (_event, context) => {
  if (!QUEUE_URL || !STREAM_TABLE_NAME) {
    throw new Error("SNS_STREAM_SQS_QUEUE_URL and STREAM_TABLE_NAME are required");
  }

  const startedAt = Date.now();
  const ownerId = context.awsRequestId || crypto.randomUUID();
  let processed = 0;

  if (!await acquireLease(ownerId)) {
    return {
      processed,
      skipped: true,
      reason: "lease-unavailable",
      elapsedMs: Date.now() - startedAt
    };
  }

  try {
    while (context.getRemainingTimeInMillis() > POLLER_RUNTIME_BUFFER_MS) {
      const response = await sqs.send(new ReceiveMessageCommand({
        QueueUrl: QUEUE_URL,
        WaitTimeSeconds: 20,
        MaxNumberOfMessages: 10,
        VisibilityTimeout: 30
      }));

      const messages = response.Messages || [];
      if (messages.length === 0) {
        continue;
      }

      for (const message of messages) {
        await processMessage(message);
        processed += 1;

        if (context.getRemainingTimeInMillis() <= POLLER_RUNTIME_BUFFER_MS) {
          break;
        }
      }
    }
  } finally {
    await releaseLease(ownerId);
  }

  return {
    processed,
    elapsedMs: Date.now() - startedAt
  };
};
