# Onboarding V2 - Functional Specification

## Executive Summary

Onboarding V2 introduces a more structured user experience flow, offering two main paths: **Guided Path** (8 structured steps) and **Open Chat** (free conversation with age validation). This system replaces the current onboarding with a more granular and controlled approach.

## Objectives

- **Personalization**: Capture name preferences and experience type
- **Validation**: Ensure only users over 18 years old access the platform
- **Structure**: Provide a guided 8-step flow to collect essential financial information
- **Flexibility**: Allow open conversation for users who prefer a less structured approach

---

## Main Flow

### Initial Entry Point

**Name Question:**
- **Type**: free_text
- **Purpose**: Personalize the experience
- **Validation**: Required field, minimum 2 characters

**Experience Question:**
- **Type**: binary_choice
- **Options**: 
  - A) Guided Path (8 structured steps)
  - B) Open Chat (free conversation)
- **Purpose**: Determine onboarding type

### 2. Age Validation (Open Chat Only)

**Age Question:**
- **Type**: free_text (numeric validation)
- **Validation**: Greater than or equal to 18
- **Behavior**: If under 18, blocks access
- **Purpose**: Legal compliance and minor protection

---

## Guided Path - 8 Structured Steps

### Step 1: Date of Birth
- **Type**: free_text (MM-DD-YYYY format)
- **Validation**: 
  - Numbers only
  - Strict MM-DD-YYYY format
  - Valid date
  - Over 18 years old
- **Vera's Text**: 
  > "Okay then, let's get rolling! First things first, would you mind telling me your date of birth? It's just to confirm you're over 18, promise I'm not being nosy."

### Step 2: Location
- **Type**: free_text
- **Validation**: Required field, minimum 3 characters
- **Vera's Text**: 
  > "And which city and state do you live in? It helps me get a sense of local living costs because, let's be real, a smoothie bowl in LA costs more than a whole barbecue in Memphis."

### Step 3: Rent or Mortgage
- **Type**: free_text
- **Validation**: Required field
- **Vera's Text**: 
  > "So, what's your monthly rent or mortgage? I know, ouch. Let's pull the Band-Aid off fast. But once it's behind us, I can start piecing together your finances so I can guide you better."

### Step 4: Home Situation
- **Type**: free_text
- **Validation**: Required field
- **Vera's Text**: 
  > "And who do you share your home with? Could be just you, a partner, family, roommates, or maybe just a very spoiled cat."

### Step 5: Feelings about Money
- **Type**: multi_choice + free_text
- **Suggestions**:
  - a) It stresses me out
  - b) I'm figuring it out
  - c) I feel great about it
  - d) Quite indifferent
- **Validation**: Allows multiple selection + additional text
- **Vera's Text**: 
  > "Got it! So, let's pause for a sec before we dive into more numbers. Could you tell how do you feel about money in general? Anxious? Confused? Totally zen? No right or wrong answers, this is a judgment-free zone. Type away or pick an option below, your call."

### Step 6: Income
- **Type**: binary_choice + single_choice/free_text
- **Initial Options**:
  - A) Sure (proceeds to numeric input)
  - B) I'd rather not to (shows predefined options)
- **If A**: free_text (numeric value)
- **If B**: single_choice (predefined options):
  - Less than $25k
  - $25k to $49k
  - $50k to $74k
  - $75k to $100k
  - More than $100k
  - I'd rather not say
- **Vera's Text**: 
  > "Thanks for the honesty! Now, let's talk a few more numbers so I can get a clearer picture and help you spot money wins faster. Mind sharing your annual income? It could be from a job, side hustles, or even selling handmade crafts online. However you make it work!"

### Step 7: Account Connection
- **Type**: binary_choice
- **Options**:
  - A) Connect accounts
  - B) Not right now
- **Vera's Text**: 
  > "Got it. Now let's peek at your spending. No judgment, I'm not here to count how many lattes or tacos you buy each month. You can safely connect your bank accounts so I can pull in the info automatically. I can only read it, I'll never touch your money. Not ready? Totally fine. You can connect later or add expenses manually. Connected accounts just give me the clearest picture and save you extra updates each month."

### Step 8: Subscription
- **Type**: binary_choice
- **Options**:
  - A) Subscribe now
  - B) Subscribe later
- **Vera's Text**: 
  > "All set! Your info is safe with me, and I'll keep everything updated automatically. Now, one last thing before we wrap up. Money talk can feel a little awkward, so I'll keep it simple. You've got 30 days of free access left. After that, it's just $5 per month to keep chatting. No hidden costs, no ads, promise. You can subscribe now, anytime during your free access, or even after it ends. Totally up to you."

---

## UI/UX Specifications

### Main Components

#### 1. **Progress Indicator**
- Visual progress bar (1/8, 2/8, etc.)
- Completion percentage
- Visual state of current step

#### 2. **Navigation**
- "Previous" button (disabled on step 1)
- "Next" button (enabled only with valid response)
- "Skip" button (optional, for non-critical steps)

#### 3. **Input Types**

**free_text:**
- Free text responses
- Minimum length validation
- Input sanitization
- Character counter (optional)
- Contextual placeholder

**binary_choice:**
- Binary selection (A/B)
- Radio buttons or selection buttons
- Required selection validation
- Clear visual states (selected/not selected)

**single_choice:**
- Single selection from predefined options
- Dropdown or option list
- Valid option validation
- Clear visual states

**multi_choice:**
- Multiple selection with configurable limits
- Checkboxes for options
- Minimum/maximum selection validation
- Clear visual states (selected/partial/not selected)

**technical_integration:**
- Integration with external systems (Plaid)
- Technical signals to frontend
- Not a conversational node

#### 4. **UI Validations**
- **free_text**: Minimum length, special characters, specific format, sanitization
- **binary_choice**: Required selection, valid option, mandatory state
- **single_choice**: Valid option from predefined list, unique selection
- **multi_choice**: Minimum/maximum selections, valid options, configurable limits
- **technical_integration**: Technical configuration validation, integration state

#### 5. **UI States**
- **Loading**: During validation or submission
- **Error**: Specific messages per error type
- **Success**: Step completion confirmation
- **Blocked**: For users under 18 years old

## Backend Specifications

### Functional Requirements

#### 1. **Question Delivery and Format**
- Provide information for each question (1-8)
- Include Vera's text for each step
- Send available options according to input type
- Indicate required input type (free_text, binary_choice, single_choice, multi_choice, technical_integration)
- Validate responses before advancing to next step
- Handle conditional flow based on user responses

#### 2. **Data Persistence**
- Store response for each question (1-8)
- Associate responses with user ID
- Validate format according to question type
- Maintain response history per user

#### 3. **USER_CONTEXT Hydration**
- Collected information must hydrate the USER_CONTEXT
- Allow access to responses for future personalization
- Maintain consistency between onboarding data and user context

---

## High-Level Tickets

### Frontend Ticket

**Title**: Implement Onboarding V2

**Description**: 
Develop the complete user interface for the new onboarding flow, including progress indicators, step navigation, real-time validations and handling of different input types.

**Acceptance Criteria**:
- Visual progress indicator (1/8, 2/8, etc.)
- Functional previous/next navigation
- Implementation of 5 input types: free_text, binary_choice, single_choice, multi_choice, technical_integration
- Real-time validations for all input types
- UI states (loading, error, success, blocked)
- Responsive design for mobile and desktop
- Accessibility (ARIA labels, keyboard navigation)
- Backend system integration

---

### Backend Ticket

**Title**: Implement Onboarding V2 Logic

**Description**: 
Develop the backend logic for the new onboarding system, including question delivery, response persistence and USER_CONTEXT hydration.

**Acceptance Criteria**:
- Question delivery and format system
- Response data persistence associated with user ID
- Validations for all input types (free_text, binary_choice, single_choice, multi_choice, technical_integration)
- USER_CONTEXT hydration with collected information
- Error handling and logging
- Unit and integration tests

---




