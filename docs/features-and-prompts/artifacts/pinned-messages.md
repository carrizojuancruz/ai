# Pinned Messages - Feature Documentation

## Executive Summary

The **Pinned Messages** functionality allows users to save and organize specific messages from Vera that they consider important or useful. The system automatically generates a structured snippet with title, summary, and **self-contained message** (polished version without action hooks or contextual reflections), facilitating retrieval and future reference of valuable information.

## Objectives

- **Knowledge Preservation**: Maintain access to any valuable information from conversations with Vera
- **Quick Reference**: Facilitate access to past information without conversation history
- **Continuity**: Allow starting new conversations based on saved messages

## Architecture

### Content Differentiation

**Original Chat Message**:
- Contains action hooks ("What do you think if...", "Would you like to...")
- Includes contextual reflections ("Based on what you told me...")
- Requires previous context to fully understand

**Self-Contained Message (Pinned)**:
- **Removes action hooks** and rhetorical questions
- **Removes contextual reflections** that depend on previous conversations
- **Is self-sufficient** to understand without previous context
- **~2000 characters recommended** to maintain conciseness
- **Preserves essential information** in a clear and direct way

**Summary**:
- **Brief description** that helps understand what it's about (~150 characters)
- **Purpose**: Quick content identification without reading the full message

### Transformation Examples

**Example 1 - List of Tips**:
```
Original Message:
"Based on what you told me about your June expenses, here are 7 tips to optimize your savings. Would it be useful if we start with the first one?"

Title: "Tips to optimize savings in June"
Summary: "7 practical strategies to reduce expenses and increase monthly savings"
Self-Contained Message:
"7 tips to optimize savings in June: 1. Review expenses and reduce 10% in restaurants. 2. Transfer $500 extra to high-yield savings account..."
```

**Example 2 - Conceptual Explanation**:
```
Original Message:
"Let me explain what compound interest is and why it's so important for your savings. Are you interested in diving deeper into this?"

Title: "What is compound interest?"
Summary: "Explanation of the compound interest concept and its importance in saving"
Self-Contained Message:
"Compound interest is when generated interest is reinvested and generates more interest. It's the foundation of exponential money growth over the long term..."
```

### Main Components

#### Responsibility Separation

**Backend**: Provides only business data (PinnedMessage)
**Frontend**: Handles presentation logic (card variants according to context)

#### PinnedMessage (Backend)
```typescript
interface PinnedMessage {
  title: string;           // Auto-generated title
  summary: string;         // Brief summary (~150 chars)
  pinnedMessage: string;   // Self-contained message (~2000 chars recommended)
  originalMessage: string; // Original chat message
  id: string;
  createdAt: Date;
  conversationId: string;
}
```

#### PinnedMessageCard (Frontend)
```typescript
interface PinnedMessageCardProps extends PinnedMessage {
  variant: 'small' | 'big'; // Decided by parent component according to context
}
```

**Presentation Variants**:
- **`'small'`**: Compact view in main list, shows title and summary
- **`'big'`**: Detailed view in modal/full screen, shows complete content

#### Pinned Messages List
- Scrollable list with infinite scroll
- Pinned messages counter
- Sorting by date (most recent first)
- **Uses 'small' variant** to show multiple messages in compact form

#### Pin Action Interface
- Pin/unpin button on Vera's messages
- Confirmation snackbar
- Visual indicator of pinned state

#### Options Dropdown
- **Functionality**: Appears when clicking options on pinned message
- **Main option**: "Delete this pinned message"
- **Behavior**: Positions relatively to the message card

#### Confirmation Modal
- **Title**: "Delete this message?"
- **Description**: "If you delete it, you won't be able to view it again"
- **Buttons**: 
  - "Cancel" (cancels the action)
  - "Delete message" (confirms deletion)
- **Behavior**: Modal overlay that requires user confirmation

## User Flows

> **Visual Reference**: For detailed interaction flows, visual designs, and UI components, refer to the [Figma Design](https://www.figma.com/design/J6VfN5vmw84EDAYbEejsfP/Wireframes?node-id=2475-41563&t=V2RCNpRtpeVzgimH-11)

### 1. Pin a Message
1. User identifies valuable message from Vera
2. Presses pin button
3. System automatically generates snippet (title, summary, self-contained message)
4. Shows confirmation snackbar
5. Message appears in pinned list

### 2. View Pinned Messages
1. User accesses pinned messages view
2. System loads list with infinite scroll
3. Frontend shows cards in 'small' variant with title and summary
4. User can select to see complete details in 'big' variant

### 3. Start Conversation from Pinned Message
1. User selects pinned message
2. **Frontend shows 'big' variant** with complete content
3. Presses "Start conversation"
4. System loads message context
5. Vera remembers previous context and continues naturally

### 4. Delete Pinned Message
1. User selects pinned message
2. **Frontend shows 'big' variant** with action options
3. Presses options button → dropdown appears
4. Selects "Delete this pinned message" from dropdown
5. **Confirmation modal** appears with title and description
6. User confirms with "Delete message" or cancels
7. **Confirmation snackbar** appears after successful deletion
8. Message is removed and counter is updated

## Technical Specifications

### API Endpoints

#### Create Pinned Message
```http
POST /api/pinned-messages
{
  "conversationId": "string",
  "messageId": "string",
  "title": "string",
  "summary": "string",
  "pinnedMessage": "string",    // Self-contained version
  "originalMessage": "string"   // Original chat message
}
```

**Response**:
```json
{
  "id": "string",
  "title": "string",
  "summary": "string",
  "pinnedMessage": "string",
  "originalMessage": "string",
  "createdAt": "2024-01-01T00:00:00Z",
  "conversationId": "string"
}
```

#### Get Pinned Messages
```http
GET /api/pinned-messages?userId={userId}&limit={limit}&offset={offset}
```

**Response**:
```json
{
  "pinnedMessages": [
    {
      "id": "string",
      "title": "string",
      "summary": "string",
      "pinnedMessage": "string",
      "originalMessage": "string",
      "createdAt": "2024-01-01T00:00:00Z",
      "conversationId": "string"
    }
  ],
  "total": 10,
  "hasMore": true
}
```

#### Delete Pinned Message
```http
DELETE /api/pinned-messages/{messageId}
```

#### Start Conversation from Pinned Message
```http
POST /api/conversations/from-pinned
{
  "pinnedMessageId": "string",
  "initialMessage": "string" // optional
}
```

### Database Model
```sql
CREATE TABLE pinned_messages (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  conversation_id UUID NOT NULL,
  message_id UUID NOT NULL,
  title VARCHAR(255) NOT NULL,
  summary TEXT NOT NULL,
  pinned_message TEXT NOT NULL,     -- Self-contained version (~2000 chars recommended)
  original_message TEXT NOT NULL,   -- Original chat message
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_pinned_messages_user_id ON pinned_messages(user_id);
CREATE INDEX idx_pinned_messages_created_at ON pinned_messages(created_at DESC);
```

### Generation Algorithm

The system must:
1. **Remove action hooks** common ("What do you think if...", "Would you like to...")
2. **Remove contextual reflections** ("Based on what you told me...")
3. **Generate title** based on main content
4. **Create summary** descriptive (~150 characters)
5. **Truncate intelligently** to ~2000 characters if necessary

## Implementation

- [ ] **Backend**: Basic APIs (create/get/delete)
- [ ] **Backend**: Database storage
- [ ] **Frontend**: PinnedMessageCard component with variants
- [ ] **Frontend**: Infinite scroll for lists
- [ ] **Integration**: With Vera's messages
- [ ] **Functionality**: Start conversation from pinned message

## Test Cases

### TC-001: Pin Message
1. Vera sends message with valuable information
2. User presses pin button
3. Confirmation snackbar is shown
4. System automatically generates snippet
5. Message appears in pinned list

### TC-002: View Pinned List
1. User accesses pinned messages view
2. System loads message list
3. User can see titles, summaries and total count badge (infinite scroll)

### TC-003: Delete Pinned Message
1. User selects pinned message
2. Presses options and delete
3. Confirms deletion through modal
4. Message is removed from list

## Implementation Considerations

### Technical
- **Performance**: Infinite scroll for large lists
- **Storage**: Consider compression for long messages

### UX
- **Visual Feedback**: Clear state indicators
- **Progressive Loading**: Show content while loading
- **Consistency**: Coherent design patterns
