# Plaid Integration Trigger (Technical Signal)

## Description
This is not a conversational node but a technical signal that tells the frontend to initialize the Plaid account connection component after completing the onboarding flow.

## Type
Frontend Integration Signal - No LLM interaction

## Purpose
- Signals completion of conversational onboarding
- Triggers frontend Plaid component initialization
- Provides context from onboarding for connection flow

## Technical Signal

```json
{
  "signal_type": "frontend_integration",
  "component": "plaid_connector",
  "trigger_condition": "onboarding_complete",
  "payload": {
    "user_id": "{user_id}",
    "onboarding_context": {
      "completed_nodes": [],
      "user_profile": {},
      "ready_for_connection": true
    },
    "plaid_config": {
      "products": ["transactions", "accounts"],
      "country_codes": ["US", "CA"],
      "link_customization": "vera_onboarding"
    }
  }
}
```

## Frontend Implementation
1. **Onboarding completes** → System sends this signal
2. **Frontend receives signal** → Initializes PlaidLinkConnector component
3. **User connects accounts** → Data flows to backend
4. **Connection complete** → Redirect to main chat interface

## No LLM Processing Required
- This is purely a technical handoff point
- No conversational prompts needed
- No validation or user interaction
- Simply triggers the frontend component

## Integration Notes
- Frontend handles all Plaid interaction
- Backend receives connection data via Plaid webhooks
- User experience seamlessly transitions from chat to account connection
