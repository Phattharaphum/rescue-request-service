import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import { DynamoDBDocumentClient, QueryCommand } from "@aws-sdk/lib-dynamodb";

const REGION = process.env.AWS_REGION || "ap-southeast-2";
const STREAM_TABLE_NAME = process.env.STREAM_TABLE_NAME;
const STREAM_KEY = process.env.STREAM_KEY || "STREAM";
const ALLOWED_ORIGINS = (process.env.ALLOWED_ORIGINS ||
  "https://rescue-request.phatphum.me,http://localhost:3000")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);
const HEARTBEAT_MS = Number.parseInt(process.env.HEARTBEAT_MS || "15000", 10);
const POLL_INTERVAL_MS = Number.parseInt(process.env.POLL_INTERVAL_MS || "1000", 10);
const STREAM_RUNTIME_BUFFER_MS = 1500;

const ddb = DynamoDBDocumentClient.from(new DynamoDBClient({ region: REGION }));

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function padTimestamp(input) {
  return String(input).padStart(13, "0");
}

function resolveAllowedOrigin(event) {
  const requestOrigin = event?.headers?.origin || event?.headers?.Origin || "";
  if (requestOrigin && ALLOWED_ORIGINS.includes(requestOrigin)) {
    return requestOrigin;
  }

  return ALLOWED_ORIGINS[0] || "";
}

function baseHeaders(event) {
  const headers = {
    "Vary": "Origin"
  };
  const allowedOrigin = resolveAllowedOrigin(event);
  if (allowedOrigin) {
    headers["Access-Control-Allow-Origin"] = allowedOrigin;
  }
  return headers;
}

function sseHeaders(event) {
  return {
    ...baseHeaders(event),
    "Content-Type": "text/event-stream; charset=utf-8",
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no"
  };
}

function optionsHeaders(event) {
  return {
    ...baseHeaders(event),
    "Access-Control-Allow-Methods": "GET,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Api-Key"
  };
}

function matchesStreamPath(event) {
  const path = event.rawPath || event.requestContext?.http?.path || "/";
  return path === "/stream" || path.endsWith("/stream");
}

async function fetchEventsAfter(cursor) {
  const response = await ddb.send(new QueryCommand({
    TableName: STREAM_TABLE_NAME,
    KeyConditionExpression: "streamKey = :streamKey AND eventKey > :cursor",
    ExpressionAttributeValues: {
      ":streamKey": STREAM_KEY,
      ":cursor": cursor
    },
    ScanIndexForward: true,
    Limit: 50
  }));

  return response.Items || [];
}

function writeChunk(stream, chunk) {
  return new Promise((resolve, reject) => {
    stream.write(chunk, (error) => {
      if (error) {
        reject(error);
        return;
      }
      resolve();
    });
  });
}

async function writeJsonResponse(responseStream, statusCode, headers, body) {
  const stream = awslambda.HttpResponseStream.from(responseStream, {
    statusCode,
    headers
  });
  await writeChunk(stream, body);
  stream.end();
}

export const handler = awslambda.streamifyResponse(async (event, responseStream, context) => {
  if (!STREAM_TABLE_NAME) {
    await writeJsonResponse(
      responseStream,
      500,
      { ...baseHeaders(event), "Content-Type": "application/json" },
      JSON.stringify({ message: "STREAM_TABLE_NAME is required" })
    );
    return;
  }

  const method = event.requestContext?.http?.method || event.httpMethod || "GET";
  if (!matchesStreamPath(event)) {
    await writeJsonResponse(
      responseStream,
      404,
      { ...baseHeaders(event), "Content-Type": "application/json" },
      JSON.stringify({ message: "Not found" })
    );
    return;
  }

  if (method === "OPTIONS") {
    await writeJsonResponse(responseStream, 200, optionsHeaders(event), "");
    return;
  }

  if (method !== "GET") {
    await writeJsonResponse(
      responseStream,
      405,
      { ...baseHeaders(event), "Content-Type": "application/json" },
      JSON.stringify({ message: "Method not allowed" })
    );
    return;
  }

  const stream = awslambda.HttpResponseStream.from(responseStream, {
    statusCode: 200,
    headers: sseHeaders(event)
  });

  let cursor = `${padTimestamp(Date.now())}#`;
  let nextHeartbeatAt = Date.now() + HEARTBEAT_MS;

  try {
    while (context.getRemainingTimeInMillis() > STREAM_RUNTIME_BUFFER_MS) {
      const events = await fetchEventsAfter(cursor);
      for (const item of events) {
        await writeChunk(stream, `data: ${JSON.stringify(item.payload)}\n\n`);
        cursor = item.eventKey;
      }

      if (Date.now() >= nextHeartbeatAt) {
        await writeChunk(stream, ": heartbeat\n\n");
        nextHeartbeatAt = Date.now() + HEARTBEAT_MS;
      }

      await sleep(POLL_INTERVAL_MS);
    }
  } finally {
    stream.end();
  }
});
