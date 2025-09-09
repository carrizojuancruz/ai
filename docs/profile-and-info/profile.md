# User Profile Management

## Overview

Profile management allows users to control their personal information in Vera. Users can add, edit, and remove information from their profile, reflecting all fields defined in the `user_context` table that can be collected from conversations with Vera or during onboarding.

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

### 3. Financial Information
- **Income format**: Toggle between "Range" and "Exact amount"
- **Income**: Text field for income range (e.g., "Between NNNN and NNNN")
- **How do you feel about money in general?**: Large text area for detailed response

### 4. Vera's Personality
- **How should Vera treat you?**: Large text area for custom instructions
- **Vera's communication style**: Chip-based selection (Technical, Chatty, Funny, Sensitive)
- **Topics to avoid?**: 
  - Secondary button to open modal
  - Chip-based display of selected topics
  - Modal with text area for adding new topics to avoid

### 5. Housing and Household Information
- **Housing**: Large text area for housing details
- **Do you have dependents?**: Toggle between "Yes" and "No"
- **Number of dependents**: Numeric field (shown when dependents = yes)
- **Do you pay rent or mortgage?**: Toggle between "Yes" and "No"
- **Select type**: Toggle between "Rent" and "Mortgage" (shown when rent/mortgage = yes)
- **Rent/Mortgage value**: Numeric field (shown when rent/mortgage = yes)

### 6. Learning Interests
- **Question**: "What would you like to learn about?"
- **Add button**: Secondary button (74x32px) to open modal
- **Interest chips**: Removable chips showing selected topics
- **Modal**: Generic Add Item Modal for learning topics

### 7. Health Insurance
- **Do you pay for health insurance?**: Toggle between "yes" and "no"
- **Add Detail**: Large text area for insurance details
- **Monthly cost**: Text area for cost information

### 8. Assets
- **Question**: "What assets do you have?"
- **Add button**: Secondary button (74x32px) to open modal
- **Asset chips**: Removable chips showing selected assets
- **Modal**: Generic Add Item Modal for asset types

### 9. Goals
- **Question**: "What are your financial goals?"
- **Add button**: Secondary button (74x32px) to open modal
- **Goal chips**: Removable chips showing selected goals
- **Modal**: Generic Add Item Modal for financial goals

## Modal Components

### Generic Add Item Modal Pattern

This pattern applies to all sections with "Add" buttons: Learning Interests, Assets, Goals, and Topics to Avoid.

#### Modal Structure
- **Trigger**: Secondary button (74x32px) with "Add +" text
- **Modal header**: Dynamic title based on section + close button (X)
- **Input field**: Large text area with contextual placeholder text
- **Action button**: Full-width secondary button to save item
- **Behavior**: Items are converted to removable chips in the main section

#### Specific Modal Instances

##### Topics to Avoid Modal
- **Trigger**: Secondary button in Vera's Personality section
- **Modal header**: "Topics to avoid" with close button
- **Input field**: Large text area for entering topics to avoid
- **Action button**: Secondary button to save topics
- **Behavior**: Topics are converted to removable chips in the main section

##### Learning Interests Modal
- **Trigger**: Secondary button in Learning Interests section
- **Modal header**: "What would you like to learn about?" with close button
- **Input field**: Large text area for entering learning topics
- **Action button**: Secondary button to save interest
- **Behavior**: Interests are converted to removable chips

##### Assets Modal
- **Trigger**: Secondary button in Assets section
- **Modal header**: "What assets do you have?" with close button
- **Input field**: Large text area for entering asset types
- **Action button**: Secondary button to save asset
- **Behavior**: Assets are converted to removable chips

##### Goals Modal
- **Trigger**: Secondary button in Goals section
- **Modal header**: "What are your financial goals?" with close button
- **Input field**: Large text area for entering financial goals
- **Action button**: Secondary button to save goal
- **Behavior**: Goals are converted to removable chips

#### Technical Specifications
- **Modal dimensions**: 353x258px (mobile-optimized)
- **Header height**: 32px with close button (X) on right
- **Input field**: 305x104px text area with contextual placeholder
- **Action button**: Full-width (305x32px) secondary button
- **Animation**: Slide-in from right with backdrop overlay
- **Validation**: Real-time validation with error states
- **Accessibility**: Focus management, keyboard navigation, screen reader support

## UI Components and Patterns

### Form Fields
- **Text fields**: White background with subtle border, rounded corners
- **Large text areas**: Multi-line input for detailed responses
- **Dropdown selectors**: With chevron icon on the right
- **Numeric inputs**: For age, dependents, monetary values

### Interactive Elements
- **Toggle switches**: Two-option toggles for yes/no questions
- **Chip components**: Removable tags with X button
- **Add buttons**: Secondary style with plus icon
- **Section cards**: Light gray background with rounded corners
- **Modal dialogs**: Overlay modals for complex input forms (e.g., Topics to avoid)

### Visual Hierarchy
- **Section headers**: Bold, 20px font size
- **Field labels**: Medium weight, 14px font size
- **Input text**: Regular weight, 16px font size
- **Placeholder text**: Muted color for guidance

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

    # Financial Information
    income_format: str | None = None  # "Range" or "Exact amount"
    income: str | None = None
    money_feelings: list[str] = Field(default_factory=list)

    # Vera's Personality
    tone_preference: str | None = None
    safety: Safety = Field(default_factory=Safety) 
    style: Style = Field(default_factory=Style)
    topics_to_avoid: list[str] = Field(default_factory=list)  # Topics user wants to avoid

    # Housing and Household
    housing: str | None = None 
    household: Household = Field(default_factory=Household)
    dependents: int | None = None
    rent_mortgage: float | None = None
    rent_mortgage_type: str | None = None  # "Rent" or "Mortgage"

    # Learning and Interests
    learning_interests: list[str] = Field(default_factory=list)

    # Health Insurance
    health_insurance: str | None = None 
    health_cost: str | None = None 

    # Additional Information
    expenses: list[str] = Field(default_factory=list)
    identity: Identity = Field(default_factory=Identity)
    goals: list[str] = Field(default_factory=list)
    assets_high_level: list[str] = Field(default_factory=list)
```

### Hidden/Inferred Fields

The following fields are automatically populated from conversations and are not visible to users in the profile interface:

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
These endpoints work for all sections with "Add" functionality (learning interests, assets, goals, topics to avoid):

- `POST /user/profile/add/{item_type}` - Add new item to list
  - **item_type**: `interests`, `assets`, `goals`, `topics_to_avoid`
  - **Body**: `{"item": "string", "description": "string"}` (optional)
- `DELETE /user/profile/remove/{item_type}` - Remove item from list
  - **item_type**: `interests`, `assets`, `goals`, `topics_to_avoid`
  - **Body**: `{"item": "string"}`
- `GET /user/profile/{item_type}` - Get items for specific type
  - **item_type**: `interests`, `assets`, `goals`, `topics_to_avoid`

## User Experience Considerations

### Mobile-First Design
- **Card-based layout** for easy scrolling
- **Touch-friendly** input fields and buttons
- **Progressive disclosure** with toggles and conditional fields
- **Chip-based selection** for easy multi-select

### Data Entry Flow
- **Logical grouping** of related fields
- **Conditional fields** that appear based on previous selections
- **Real-time validation** with clear error messages
- **Auto-save** functionality for better UX
