# Nudge Evaluation API Examples

This document provides examples for testing the new nudge evaluation and queueing system.

## Overview

The new nudge system evaluates users asynchronously and queues nudges in SQS based on priority. This is the evaluation and queueing part only - initialization and notification sending will be implemented separately.

## Endpoints

### 1. Evaluate Nudges (Main Endpoint)

**Endpoint**: `POST /nudges/evaluate`

This is the main endpoint called by cron jobs or FOS pings to trigger nudge evaluation.

#### Type 1 - Bill Nudges (Verde generates text)

```bash
curl -X POST http://localhost:8000/nudges/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "nudge_type": "static_bill"
  }'
```

Response:
```json
{
  "status": "started",
  "message": "Evaluation started for static_bill nudges",
  "task_id": "abc123-def456-..."
}
```

#### Type 2 - Memory Icebreaker (Verde generates text)

```bash
curl -X POST http://localhost:8000/nudges/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "nudge_type": "memory_icebreaker"
  }'
```

#### Type 3 - Info-Based (FOS provides text)

```bash
curl -X POST http://localhost:8000/nudges/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "nudge_type": "info_based",
    "nudge_id": "spending_alert",
    "notification_text": "Hey! Your dining expenses increased 40% this month. Want to review?",
    "preview_text": "Spending alert 💳"
  }'
```

### 2. Manual Trigger (For Testing)

**Endpoint**: `POST /nudges/trigger`

Manually trigger a nudge for a specific user (useful for testing).

```bash
curl -X POST http://localhost:8000/nudges/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "nudge_type": "static_bill",
    "force": false,
    "priority_override": 4
  }'
```

Response:
```json
{
  "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
  "status": "queued",
  "nudge_type": "static_bill",
  "priority": 4,
  "message_id": "sqs-message-id-123"
}
```

### 3. Get User Status

**Endpoint**: `GET /nudges/status/{user_id}`

Check nudge status for a specific user.

```bash
curl http://localhost:8000/nudges/status/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

Response:
```json
{
  "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
  "nudges_today": 1,
  "nudges_this_week": 3,
  "last_nudge": "2025-01-09T10:00:00Z",
  "next_eligible": "2025-01-09T14:00:00Z",
  "in_cooldown": false,
  "queued_nudges": 2
}
```

### 4. Health Check

**Endpoint**: `GET /nudges/health`

Check the health of the nudge system.

```bash
curl http://localhost:8000/nudges/health
```

Response:
```json
{
  "status": "healthy",
  "nudges_enabled": true,
  "queue_depth": 5,
  "queue_url": "https://sqs.us-east-1.amazonaws.com/909418399862/fos-ai-dev-nudges",
  "rate_limits": {
    "max_per_day": 3,
    "max_per_week": 10
  }
}
```

## Mock Active Users

Currently, the system uses mock user IDs for testing. The mock users are:

1. `ba5c5db4-d3fb-4ca8-9445-1c221ea502a8`
2. `a1b2c3d4-e5f6-7890-abcd-ef1234567890`
3. `98765432-1234-5678-90ab-cdef12345678`

These are defined in `app/services/nudges/evaluator.py` in the `iter_active_users` function. In production, this will be replaced with actual FOS API calls.

## Testing Flow

### 1. Basic Evaluation Test

```bash
# 1. Check health
curl http://localhost:8000/nudges/health

# 2. Trigger bill evaluation for all mock users
curl -X POST http://localhost:8000/nudges/evaluate \
  -H "Content-Type: application/json" \
  -d '{"nudge_type": "static_bill"}'

# 3. Check a specific user's status
curl http://localhost:8000/nudges/status/ba5c5db4-d3fb-4ca8-9445-1c221ea502a8
```

### 2. Info-Based Nudge Test

```bash
# Simulate FOS ping with notification text
curl -X POST http://localhost:8000/nudges/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "nudge_type": "info_based",
    "nudge_id": "budget_warning",
    "notification_text": "You have used 75% of your dining budget with 10 days left in the month.",
    "preview_text": "Budget Alert"
  }'
```

### 3. Manual Test for Specific User

```bash
# Manually trigger a memory nudge for testing
curl -X POST http://localhost:8000/nudges/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ba5c5db4-d3fb-4ca8-9445-1c221ea502a8",
    "nudge_type": "memory_icebreaker"
  }'
```

## Configuration

Key environment variables for testing:

```bash
# Enable/disable nudges
NUDGES_ENABLED=true

# SQS Configuration
SQS_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/909418399862/fos-ai-dev-nudges
SQS_QUEUE_REGION=us-east-1

# Rate Limits
NUDGE_MAX_PER_DAY=3
NUDGE_MAX_PER_WEEK=10

# Quiet Hours (24-hour format)
NUDGE_QUIET_HOURS_START=22  # 10 PM
NUDGE_QUIET_HOURS_END=8     # 8 AM

# FOS API Pagination (when implemented)
FOS_USERS_PAGE_SIZE=500
FOS_USERS_MAX_PAGES=100
```

## Queue Message Format

Messages in SQS follow this format:

```json
{
  "messageId": "uuid",
  "userId": "user-uuid",
  "nudgeType": "static_bill|memory_icebreaker|info_based",
  "priority": 3,  // 1-5 scale
  "nudgePayload": {
    "notification_text": "Your Netflix subscription ($15.99) is due tomorrow.",
    "preview_text": "Netflix due tomorrow",
    "metadata": {
      "bill": {
        "merchant": "Netflix",
        "amount": 15.99,
        "predicted_due_date": "2025-01-15",
        "days_until_due": 1
      }
    }
  },
  "channel": "push",
  "timestamp": "2025-01-09T10:00:00Z",
  "expiresAt": "2025-01-09T22:00:00Z",
  "deduplicationKey": "user123:static_bill"
}
```

## Implementation Notes

1. **Deduplication**: The system uses a "Latest Wins" strategy where newer nudges for the same user+type replace older ones in the queue.

2. **Priority Ordering**: Messages are processed by priority (5 = highest, 1 = lowest), then by timestamp (FIFO within same priority).

3. **Rate Limiting**: The system enforces daily and weekly limits per user, tracked in memory (will be Redis in production).

4. **Quiet Hours**: Nudges are not evaluated during configured quiet hours (default 10 PM - 8 AM).

5. **Mock Data**: Bill detection currently returns random test data. In production, it will query the Plaid financial database.

## Next Steps

The following components will be implemented separately:

1. **Queue Worker**: Consumer that processes messages from SQS
2. **Nudge Initialization**: Creating conversation threads
3. **Notification Sending**: Actual push/in-app notification delivery
4. **Redis Integration**: For distributed activity tracking
5. **FOS API Integration**: Replace mock users with actual API calls

## Troubleshooting

### Nudges Not Being Queued

1. Check if nudges are enabled: `NUDGES_ENABLED=true`
2. Verify SQS permissions and queue URL
3. Check rate limits haven't been exceeded
4. Ensure not in quiet hours
5. Check logs for evaluation errors

### SQS Connection Issues

1. Verify AWS credentials are configured
2. Check SQS queue URL is correct
3. Ensure IAM role has SendMessage permission
4. Check network connectivity to AWS

### Mock Users Not Working

The mock user IDs are hardcoded in `app/services/nudges/evaluator.py`. Make sure you're using one of the predefined IDs for testing.
