# User Profile Management

## Overview

Profile management allows users to control their personal information in Vera. Users can add, edit, and remove information from their profile, reflecting all fields defined in the `user_context` table that can be collected from conversations with Vera or during onboarding.

## Design Philosophy & Information Architecture

> **Important Disclaimer**: This profile interface intentionally hides certain financial and personal information fields (income, assets, housing costs, etc.) to prevent user confusion and maintain data integrity across different system flows. 
>
> **Rationale**: Some information is collected qualitatively through conversations with Vera and then structured quantitatively in other specialized flows (budgeting, financial planning, etc.). Exposing these fields in the profile interface could create:
> - **Data conflicts** between conversational insights and manual user input
> - **User confusion** about which information takes precedence
> - **Inconsistent data quality** across different system modules
>
> **Solution**: These fields remain part of the `UserContext` schema but are automatically populated from conversations and other system interactions, ensuring a single source of truth while keeping the profile interface focused on user preferences and communication settings.

## Profile Sections (Based on Figma Design)

The user profile is organized into logical sections that match the mobile interface design:

### 1. Personal Information
- **Name (how Vera will call you)**: Free text field
- **Pronouns**: Dropdown selector (He/Him, She/Her, They/Them, etc.)
- **Age**: 
  - Toggle between "Exact age" and "Age rank" 
  - Numeric input field for specific age
  - Age rank selector for ranges

### 2. Location and Language
- **Place of residence (City, Region)**: Combined text field (e.g., "Springfield, CA, US")
- **Language**: Dropdown selector with language codes (e.g., "EN/US")

### 3. Vera's Personality
- **How should Vera treat you?**: Large text area for custom instructions
- **Vera's communication style**: Chip-based selection (Technical, Chatty, Funny, Sensitive)
- **Topics to avoid?**: 
  - Button to open modal
  - Chip-based display of selected topics
  - Modal with text area for adding new topics to avoid

### 4. Housing and Household Information
- **Housing**: Dropdown selector for housing situation
- **Do you have dependents?**: Toggle between "Yes" and "No"
- **Number of dependents**: Numeric field (shown when dependents = yes)

### 5. Learning Interests
- **Question**: "What would you like to learn about?"
- **Add button**: Button (74x32px) to open modal
- **Interest chips**: Removable chips showing selected topics
- **Modal**: Generic Add Item Modal for learning topics

### 6. Health Insurance
- **Tell Vera about your health coverage**: Large text area for insurance details
- **Do you pay for it?**: Toggle between "yes" and "no"

### 7. Goals
- **Question**: "What are your financial goals?"
- **Add button**: button to open modal
- **Goal chips**: Removable chips showing selected goals
- **Modal**: Generic Add Item Modal for financial goals

## Modal Components

### Generic Add Item Modal Pattern

This pattern applies to all sections with "Add" buttons: Learning Interests, Goals, and Topics to Avoid.

#### Modal Structure
- **Trigger**: button with "Add +" text
- **Modal header**: Dynamic title based on section + close button (X)
- **Input field**: Large text area with contextual placeholder text
- **Action button**: Full-width button to save item
- **Behavior**: Items are converted to removable chips in the main section

#### Specific Modal Instances

##### Topics to Avoid Modal
- **Trigger**: button in Vera's Personality section
- **Modal header**: "Topics to avoid" with close button
- **Input field**: Large text area for entering topics to avoid
- **Action button**:  button to save topics
- **Behavior**: Topics are converted to removable chips in the main section

##### Learning Interests Modal
- **Trigger**: Button in Learning Interests section
- **Modal header**: "What would you like to learn about?" with close button
- **Input field**: Large text area for entering learning topics
- **Action button**: Button to save interest
- **Behavior**: Interests are converted to removable chips

##### Goals Modal
- **Trigger**: Button in Goals section
- **Modal header**: "What are your financial goals?" with close button
- **Input field**: Large text area for entering financial goals
- **Action button**: Button to save goal
- **Behavior**: Goals are converted to removable chips

## UI Components and Patterns

### Form Fields
- **Text fields**: White background with subtle border, rounded corners
- **Large text areas**: Multi-line input for detailed responses
- **Dropdown selectors**: With chevron icon on the right
- **Numeric inputs**: For age, dependents, monetary values

### Interactive Elements
- **Toggle switches**: Two-option toggles for yes/no questions
- **Chip components**: Removable tags with X button
- **Add buttons**: Button style with plus icon
- **Section cards**: Light gray background with rounded corners
- **Modal dialogs**: Overlay modals for complex input forms (e.g., Topics to avoid)

## Data Schema Integration

> **Important Note**: The actual `UserContext` schema is more extensive than what's shown here. The fields presented below are grouped and reorganized for user interface coherence and do not reflect the actual database order or complete field set. Many additional fields are automatically inferred from conversations with Vera and are not exposed to the end user in this profile management interface.

```python
class UserContext(BaseModel):
    # Personal Information
    preferred_name: str | None = None
    pronouns: str | None = None
    age: int | None = None
    age_rank: str | None = None  # Age range/rank selection

    # Location and Language
    city: str | None = None
    region: str | None = None
    language: str = Field(default="en-US")

    # Vera's Personality
    tone_preference: str | None = None
    safety: Safety = Field(default_factory=Safety) 
    style: Style = Field(default_factory=Style)
    topics_to_avoid: list[str] = Field(default_factory=list)  # Topics user wants to avoid

    # Housing and Household
    housing: str | None = None 
    household: Household = Field(default_factory=Household)
    dependents: int | None = None

    # Learning and Interests
    learning_interests: list[str] = Field(default_factory=list)

    # Health Insurance
    health_insurance: str | None = None 

    # Additional Information
    expenses: list[str] = Field(default_factory=list)
    identity: Identity = Field(default_factory=Identity)
    goals: list[str] = Field(default_factory=list)
```

### Hidden/Inferred Fields

The following fields are automatically populated from conversations and are not visible to users in the profile interface:

- **Financial Information** (income format, income amount, money feelings)
- **Housing Details** (rent/mortgage payments, payment type, payment amounts)
- **Health Insurance Costs** (monthly health insurance costs)
- **Assets** (asset types and details)
- **Accessibility settings** (reading level, glossary preferences)
- **Budget posture** (active budget status, spending summaries)
- **Locale information** (timezone, currency, regional settings)
- **Conversation metadata** (interaction patterns, preferences)
- **System flags** (orchestrator readiness, consent status)
- **Derived insights** (financial behavior patterns, communication style)

## API Endpoints

### Base URL
```
/user/profile
```

### Main Endpoints
- `GET /user/profile/` - Get complete profile
- `PATCH /user/profile/` - Update profile (partial)
- `GET /user/profile/section/{section}` - Get specific section
- `PATCH /user/profile/section/{section}` - Update specific section
- `GET /user/profile/export` - Export profile

### Generic Add Item Endpoints
These endpoints work for all sections with "Add" functionality (learning interests, goals, topics to avoid):

- `POST /user/profile/add/{item_type}` - Add new item to list
  - **item_type**: `interests`, `goals`, `topics_to_avoid`
  - **Body**: `{"item": "string", "description": "string"}` (optional)
- `DELETE /user/profile/remove/{item_type}` - Remove item from list
  - **item_type**: `interests`, `goals`, `topics_to_avoid`
  - **Body**: `{"item": "string"}`
- `GET /user/profile/{item_type}` - Get items for specific type
  - **item_type**: `interests`, `goals`, `topics_to_avoid`

## User Experience Considerations

### Data Entry Flow
- **Logical grouping** of related fields
- **Conditional fields** that appear based on previous selections
- **Real-time validation** with clear error messages
- **Auto-save** functionality for better UX
