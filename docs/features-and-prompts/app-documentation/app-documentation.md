# Vera Mobile App - System Documentation

## App Overview

Vera is a AI assistant mobile application that helps users manage their finances, track goals, and make informed financial decisions. The app is designed for mobile use only and provides a comprehensive financial management and guidance experience through conversational AI.

## Core Features

The app includes the following main functional areas:
- **Financial Dashboard**: Overview of net worth, cash flow, and financial health
- **Goal Tracking**: Create, monitor, and manage financial objectives
- **Account Management**: Connect bank accounts and manage financial data
- **Conversational AI**: Chat with Vera for financial advice and guidance
- **Memory System**: Automatic learning and personalization
- **Reports & Analytics**: Detailed financial insights and trends

## Navigation Structure

The app uses a bottom navigation bar with four main sections:
- **Home**: Main dashboard with financial overview
- **Goals**: Goal management and tracking
- **Pinned Messages**: Saved important conversations
- **Reports**: Financial reports and analytics

Additional features are accessible through a sidebar menu that includes:
- Financial Info (account management)
- Settings (app configuration)
- Memories (AI learning management)
- Help Center (support and documentation)

## Key User Flows

### Connecting Bank Accounts
Users can connect their bank accounts through Plaid integration:
1. Navigate to Sidebar → Financial Info → Accounts and Cards
2. Tap "Add Account" button
3. Follow Plaid's secure connection process
4. Accounts automatically sync financial data

### Creating Financial Goals
Users can set up savings or spending goals:
1. Go to Goals section from main navigation
2. Tap "Set a new goal" card
3. Engage in conversation with Vera to define goal details
4. Goal appears on dashboard with progress tracking

### Viewing Financial Reports
Users can access detailed financial insights:
1. Navigate to Reports section
2. View Net Worth and Cash Flow summary cards
3. Tap "See more" for detailed charts and breakdowns
4. Access historical trends and projections

### Managing Conversations
Users can save important conversations:
1. During any chat, tap pin icon next to messages
2. Pinned messages appear in dedicated section
3. Can resume conversations from pinned context
4. Manage and organize saved conversations

---

# Screen-by-Screen Documentation

## Home Screen

### Purpose
The Home screen serves as the main dashboard where users can view their financial overview and quickly access key features. It provides a centralized view of their financial status and app functionality.

### Layout and Components
The Home screen displays several key components:
- **Navigation Bar**: Bottom navigation with four main sections (Home, Goals, Pinned Messages, Reports)
- **Financial Cards**: Net Worth and Cash Flow summary cards with current values and trends
- **Goal Cards**: Active financial goals with progress indicators and status
- **Pinned Messages**: Quick access to saved important conversations
- **Mood Check**: Daily mood selection interface (appears once per day)
- **Icebreaker Suggestions**: Vera's conversation starters to engage users

### User Interactions
Users can:
- Tap on goal cards to start conversations about specific goals
- Access pinned messages for quick reference to important information
- View financial summaries and tap "See more" for detailed reports
- Select their daily mood to help personalize the experience
- Navigate to other sections using the bottom navigation or sidebar menu

### Conditional Display Rules
- **Goal Cards**: Only displayed when user has active goals
- **Pinned Messages**: Only shown when user has saved conversations
- **Mood Check**: Appears when user enters the app, once daily, persists if not completed
- **Card Order**: Modules can be prioritized by relevance/urgency

### Navigation Options
From Home, users can navigate to:
- Goals section for goal management
- Pinned Messages for saved conversations
- Reports for detailed financial analytics
- Sidebar menu for additional features (Financial Info, Settings, Memories, Help Center)

### Common User Scenarios
- **First-time users**: May see empty states encouraging them to connect accounts or create goals
- **Returning users**: See their financial overview and can quickly access recent activities
- **Goal-focused users**: Can immediately see progress on their financial objectives
- **Data-driven users**: Can quickly access their financial reports and analytics

## Goals Screen

### Purpose
The Goals screen provides users with a comprehensive view of their financial objectives, allowing them to create, monitor, and manage their savings and spending goals. It serves as the central hub for goal-based financial planning.

### Layout and Components
The Goals screen includes:
- **Navigation Bar**: Access to all main app sections
- **Goal Counter**: Shows total number of active goals
- **Status Filter**: Dropdown to filter goals by status (All, On track, Off track, Achieved, Pending)
- **Goal Cards**: Individual cards for each goal showing progress and details
- **Create Goal Card**: Blue card with target icon to create new goals

### Goal Card Information
Each goal card displays:
- **Target Icon**: Color-coded based on goal status
- **Goal Title**: User-defined goal name
- **Status Badge**: Current status (Pending details, On track, Off track, Achieved)
- **Progress Bar**: Visual representation of goal completion
- **Financial Details**: Spent amount vs. target amount
- **Time Remaining**: Countdown to goal deadline

### Goal Status Types
- **Pending Details**: Goal needs additional information to be activated
- **On Track**: Goal is progressing as planned
- **Off Track**: Goal is behind schedule or over budget
- **Achieved**: Goal has been successfully completed

### User Interactions
Users can:
- Filter goals by status using the dropdown menu
- Tap on any goal card to start a conversation about that specific goal
- Create new goals by tapping the "Set a new goal" card
- View progress and financial details for each goal
- Access goal-specific actions and modifications

### Goal Creation Process
When creating a new goal:
1. User taps "Set a new goal" card
2. Conversation interface opens with Vera
3. Vera guides user through goal definition process
4. Goal details are captured through natural conversation
5. Goal appears on dashboard with appropriate status

### Business Rules and Limitations
- **Maximum Active Goals**: No limit - users can have unlimited active goals
- **Progress Updates**: Can be manual or automatic depending on goal type
- **Notifications**: Payment reminders due date notifications
- **Archiving**: Completed goals move to history section
- **Auto-save**: Changes save automatically with option to revert
- **Required Fields**: Title, target amount, and date required before activating goal

### Navigation Options
From Goals, users can navigate to:
- Goal Detail for specific goal conversations
- Chat for creating new goals
- Home for main dashboard
- Pinned Messages for saved conversations
- Reports for financial analytics

### Common User Scenarios
- **New users**: See empty state with option to create first goal
- **Active goal managers**: View progress and status of multiple goals
- **Goal achievers**: Celebrate completed goals and create new ones
- **Struggling users**: Identify off-track goals and get assistance

## Reports Screen

### Purpose
The Reports screen provides users with a comprehensive view of their financial health through key metrics and trends. It displays net worth and cash flow information with detailed analytics and historical data.

### Layout and Components
The Reports screen features:
- **Navigation Bar**: Access to all main app sections
- **Report Counter**: Shows number of available reports
- **Net Worth Card**: Summary of total assets minus liabilities
- **Cash Flow Card**: Summary of income minus expenses
- **Trend Indicators**: Visual arrows showing positive or negative changes
- **Detail Buttons**: "See more" options for comprehensive analysis

### Net Worth Card Information
The Net Worth card displays:
- **Total Net Worth**: Calculated as assets minus liabilities
- **Monthly Trend**: Percentage change from previous month with trend arrow
- **Asset Breakdown**: Total value of all assets
- **Liability Breakdown**: Total value of all debts
- **Last Updated**: Timestamp of most recent data update
- **Detail Access**: Button to view comprehensive charts and analysis

### Cash Flow Card Information
The Cash Flow card shows:
- **Net Cash Flow**: Income minus expenses for the period
- **Monthly Trend**: Percentage change from previous month
- **Income Total**: All money coming in
- **Expense Total**: All money going out
- **Time Period**: "Info from the last 30 days up to today"
- **Detail Access**: Button for detailed breakdowns and categorization

### Data Sources and Updates
- **Automatic Updates**: Data syncs from connected accounts
- **Time Periods**: Cash flow shows last 30 days, net worth is cumulative
- **Color Coding**: Assets in green, liabilities in red, net worth in blue
- **Precision**: Values shown with 2 decimal places, percentages with 1 decimal
- **Dynamic Calculation**: All amounts calculated from actual user data

### User Interactions
Users can:
- View current financial metrics at a glance
- Tap "See more" for detailed analysis and charts
- Access historical trends and projections
- Navigate to detailed views for specific metrics
- Compare current performance with previous periods

### Empty States and Data Requirements
- **No Financial Data**: Users need to connect accounts or add information manually
- **No Connected Accounts**: System suggests connecting bank accounts for automatic updates
- **Incomplete Data**: Partial information shows progress toward complete financial profile

### Navigation Options
From Reports, users can navigate to:
- Net Worth Detail for comprehensive asset/liability analysis
- Cash Flow Detail for income/expense breakdowns
- Home for main dashboard
- Goals for financial objective management
- Pinned Messages for saved conversations

### Common User Scenarios
- **Financial overview seekers**: Quick access to key financial metrics
- **Trend analyzers**: Users wanting to track financial progress over time
- **Detail-oriented users**: Access to comprehensive financial breakdowns
- **New users**: Empty states encouraging data input and account connection

## Pinned Messages Screen

### Purpose
The Pinned Messages screen allows users to save and quickly access important conversations and financial advice from their interactions with Vera. It serves as a personal knowledge base of valuable information.

### Layout and Components
The Pinned Messages screen includes:
- **Navigation Bar**: Access to all main app sections
- **Message Counter**: Shows total number of pinned messages
- **Search Field**: Filter messages by content or topic
- **Message Cards**: Individual cards for each pinned message
- **Icebreaker Suggestions**: Vera's conversation starters at the bottom

### Message Card Information
Each pinned message card displays:
- **Message Title**: Descriptive title of the saved content
- **Pushpin Icon**: Visual indicator that message is pinned
- **Brief Summary**: Short description of the message content
- **Tap to View**: Interactive element to access full message

### Detailed Message View
When users tap a message card, they see:
- **Large Title**: Full message title
- **Options Menu**: Three-dot menu for message management
- **Complete Content**: Full message text with preserved formatting
- **Continue Conversation**: Button to resume dialogue from that context

### Message Management Features
Users can:
- **Search Messages**: Use search field to find specific content
- **Edit Messages**: Modify saved message content
- **Unpin Messages**: Remove messages from pinned collection
- **Delete Messages**: Permanently remove messages
- **Resume Conversations**: Continue discussions from pinned context

### Pinning Process
To pin a message:
1. During any conversation, tap the pin icon next to a message
2. Message is automatically saved to Pinned Messages
3. Message appears in the collection for future reference
4. Users can manage pinned messages through the options menu

### Business Rules and Limitations
- **Maximum Pinned Messages**: No limit - users can pin unlimited messages
- **Message Creation**: Messages are pinned from active conversations
- **Persistence**: Pinned messages remain until manually unpinned
- **Continue Conversation**: Resumes dialogue from the pinned message context
- **Available Actions**: Edit, unpin, or delete messages
- **Categorization**: Messages are not categorized - displayed as a flat list

### Empty States
- **No Pinned Messages**: System encourages users to start pinning important conversations
- **No Data**: Explains the value of pinned messages for quick reference
- **Incomplete Setup**: Suggests identifying valuable messages to pin

### Navigation Options
From Pinned Messages, users can navigate to:
- Pinned Message Detail for full message view
- Home for main dashboard
- Goals for financial objective management
- Reports for financial analytics

### Common User Scenarios
- **Information seekers**: Quick access to previously discussed financial advice
- **Conversation continuers**: Resume important discussions from where they left off
- **Knowledge organizers**: Manage and categorize important financial information
- **New users**: Learn about the value of pinning important conversations

## Mood Check Feature

### Purpose
The Mood Check feature allows users to indicate their daily emotional state, which helps Vera personalize conversations and provide more appropriate financial guidance. It appears once daily on the Home screen.

### Interface Design
The mood check displays:
- **Question**: "How are you feeling today?"
- **Five Face Options**: Emoji scale from very bad (😞) to very good (😊)
- **One-Tap Selection**: Simple tap to select current mood
- **Automatic Recording**: Mood is saved and used for personalization

### User Interaction
Users can:
- **Select Mood**: Tap on the face emoji that best represents their current emotional state
- **Skip Check**: Optionally ignore the mood check if they prefer
- **Help Personalization**: Their mood data helps tailor Vera's responses and suggestions

### Mood Scale
The system uses a 1-5 scale:
- **1 (Very Bad)**: 😞 - User is struggling or stressed
- **2 (Bad)**: 😕 - User is having a difficult day
- **3 (Neutral)**: 😐 - User feels average or neutral
- **4 (Good)**: 😊 - User is having a positive day
- **5 (Very Good)**: 😄 - User is feeling excellent

### Business Rules and Timing
- **Frequency**: Appears when user enters the app, once per day on Home screen
- **Persistence**: Persists until user interacts with it (no time limit)
- **Scale**: 1-5 rating (very bad to very good)
- **Optional**: User can skip if they prefer
- **Personalization**: Mood data helps build rapport, reduce stress, and connect better with the user

### Personalization Impact
The mood check data is used to:
- Adjust conversation tone and approach
- Suggest appropriate financial activities based on emotional state
- Provide more empathetic responses during difficult times
- Celebrate positive moods with encouraging financial guidance

### Common User Scenarios
- **Stressed users**: System can focus on simple, manageable financial tasks
- **Happy users**: Perfect time to tackle challenging financial goals
- **Overwhelmed users**: Start with small steps and build confidence
- **Users who skip**: System adapts without mood data, still providing helpful guidance
- **First-time users**: Guided path to get to know the user better and provide a tailored experience

### Technical Implementation
- **Daily Reset**: System resets mood check availability each day
- **Data Storage**: Mood data is stored for personalization purposes
- **Optional Nature**: Users can skip without affecting app functionality
- **Integration**: Mood data influences conversation flow and suggestions

## Memory Creation System

### Purpose
The Memory Creation system automatically identifies and saves important information from user conversations to provide personalized financial guidance. It creates a knowledge base of user-specific details that enhances future interactions.

### How It Works
The system operates automatically during conversations:
- **Detection**: Identifies relevant information without user intervention
- **Categorization**: Groups memories by type of information
- **Storage**: Saves information for future conversation use
- **Updates**: Can modify existing memories with new information
- **Personalization**: Uses stored information to customize responses

### Memory Preview Interface
When a memory is created, users see:
- **Header**: "Memories detail" with close and edit icons
- **Memory Snippets**: Important information fragments saved
- **Categories**: Badges showing information type (new/updated)
- **Example Content**: "The user has a poodle named Rufus Magnus Snowflake the Third"

### User Control Options
Users can:
- **View Previews**: See what information has been saved
- **Edit Memories**: Modify saved information if needed
- **Close Previews**: Dismiss memory preview cards
- **Manage Memories**: Access full memory management through Memories section

### Business Rules and Privacy
- **Automatic Detection**: System identifies relevant information based on agent relevance assessment or explicit user requests
- **Categorization**: Memories grouped by information type (Personal info, Financial, Career studies, Family relationships, Goals and Dreams, Worries and struggles, Preferences and habits)
- **Persistence**: Stored for future conversation use
- **Updates**: Existing memories can be updated with new information
- **Context**: Used to personalize future responses
- **User Control**: Users can edit, delete, or manage their memories

### Common Scenarios
- **Personal Information**: System saves family details, financial situations, and goals
- **Preference Learning**: Remembers user preferences and communication styles
- **Financial Context**: Stores relevant financial information for better advice
- **Correction Handling**: Users can correct or update stored information

## Sources System

### Purpose
The Sources system provides transparency by showing users the external materials consulted when providing financial advice. It ensures credibility and allows users to verify information independently.

### How It Works
When external sources are used:
- **Automatic Display**: Sources appear automatically when external information is consulted
- **Full Transparency**: All sources used are shown to the user
- **Verification**: Direct links to original sources are provided
- **Credibility**: Only reliable and authoritative sources are used

### Sources List Interface
The sources display includes:
- **Header**: "List of sources" with close and edit icons
- **Source Items**: Each source shows:
  - Source name (e.g., "MyMoney.gov")
  - Brief description of the source
  - Direct link to the original source
- **Example**: "Official U.S. government portal for financial education programs and information"

### Source Types and Credibility
- **Government Sources**: Official government websites for reliable, up-to-date information
- **Financial Institutions**: Established financial institutions with expertise
- **Educational Resources**: Resources designed to help understand financial topics
- **Multiple Sources**: Comprehensive answers from several sources

### Business Rules and Transparency
- **Full Transparency**: All sources used are shown to the user
- **Verifiability**: Direct links to original sources
- **Credibility**: Only reliable and authoritative sources are used
- **Updates**: Sources change based on the specific query
- **Categorization**: Sources are grouped by category (Personal Finance, Mental Health, Career Development, Crisis Resources, Credit & Debt, Student Loans, Budgeting, Building Wealth, Protection, Money Transfers, State Services)

### Common Scenarios
- **Financial Advice**: Government websites and financial institutions
- **Educational Content**: Educational resources for financial topics
- **Regulatory Information**: Official regulatory and compliance sources
- **Market Data**: Reliable financial market information sources

## Sidebar Navigation

### Purpose
The Sidebar provides access to all main app features and settings through a slide-out menu panel. It serves as the primary navigation hub for advanced functionality and account management.

### Interface Design
The sidebar displays:
- **Vera Logo**: App branding with trademark symbol
- **Close Button**: Double left arrow to close the sidebar
- **Menu Items**: Organized list of main app sections
- **Logout Option**: Sign out functionality at the bottom

### Main Menu Sections
- **Home**: Main dashboard access
- **Financial Info**: Account management and financial data
- **Settings**: App configuration and account settings
- **Memories**: AI learning management
- **Help Center**: Support and documentation

### User Interactions
Users can:
- **Open Sidebar**: Tap menu icon (three horizontal lines) in top left
- **Navigate Sections**: Tap on any main menu item
- **Access Submenus**: Tap to expand detailed options
- **Close Sidebar**: Tap outside menu or swipe left
- **Logout**: Access sign out option at bottom

### Business Rules and Navigation
- **Always Accessible**: Sidebar can be opened from any screen
- **Persistent**: Stays open until manually closed
- **Hierarchical**: Main sections have submenus for specific features
- **Subscription-based**: Some features may be limited based on subscription level
- **Logout**: Always available at the bottom of the sidebar

### Common User Scenarios
- **Account Management**: Access Financial Info for account setup and management
- **Settings Configuration**: Use Settings to customize app experience
- **Memory Management**: Check Memories to see AI learning progress
- **Help and Support**: Access Help Center for assistance and resources

### Navigation Options
From Sidebar, users can navigate to:
- Home for main dashboard
- Financial Info for account management
- Settings for app configuration
- Memories for AI learning management
- Help Center for support and resources

## Memories Management Screen

### Purpose
The Memories Management screen allows users to view, search, edit, and delete the information that Vera has automatically learned from their conversations. It provides full control over the AI's knowledge base.

### Layout and Components
The Memories Management screen includes:
- **Search Bar**: Full-text search across all memories
- **Memory Cards**: Individual cards for each saved memory
- **Category Tags**: Visual indicators for memory types
- **Date Information**: When each memory was created
- **Action Buttons**: Edit and delete options for each memory

### Memory Card Information
Each memory card displays:
- **Memory Content**: Snippet of the saved information
- **Category Tags**: Type of memory (Personal, Financial, Preferences)
- **Creation Date**: When the memory was first saved
- **Action Options**: Edit and delete buttons

### Memory Detail View
When users tap a memory card, they see:
- **Full Content**: Complete memory text with all details
- **Category Information**: Type and classification of the memory
- **Creation Date**: Timestamp of when memory was created
- **Edit Button**: Option to modify the memory content
- **Delete Button**: Option to remove the memory

### User Management Features
Users can:
- **Search Memories**: Use search bar to find specific information
- **View Details**: Tap cards to see full memory content
- **Edit Memories**: Modify saved information as needed
- **Delete Memories**: Remove memories they no longer want kept
- **Manage Categories**: See how memories are organized by type

### Business Rules and Privacy
- **Automatic Creation**: Memories are created automatically from conversations
- **User Control**: Users can edit, delete, or search all memories
- **Categorization**: Memories are grouped by type of information
- **Persistence**: Memories persist until manually deleted
- **Privacy**: Users have full control over their personal information
- **Search Functionality**: Full-text search across all memory content

### Common User Scenarios
- **Information Review**: Users can see what Vera has learned about them
- **Data Correction**: Users can edit inaccurate or outdated information
- **Privacy Management**: Users can delete sensitive or unwanted memories
- **Search and Discovery**: Users can find specific information quickly

### Delete Confirmation Modal
When users choose to delete memories, they see:
- **Title**: "Delete all memories?"
- **Description**: "If you delete your memories, Vera won't be able to remember past details or use them to personalize chats"
- **Action Buttons**: "Cancel" and "Delete memories"

### Troubleshooting
- **No memories showing**: System only creates memories when important information is learned
- **Search not working**: Ensure search is being performed in the correct field
- **Can't delete memories**: Tap on memory first, then look for delete option
- **Memories seem wrong**: Users can delete incorrect memories and system will learn correct information

### Navigation Options
From Memories Management, users can navigate to:
- Home for main dashboard
- Financial Info for account management
- Settings for app configuration
- Help Center for support and resources

## Settings Screen

### Purpose
The Settings screen provides users with comprehensive configuration options for customizing their app experience, managing account settings, and controlling privacy and security preferences.

### Layout and Components
The Settings screen includes:
- **Navigation Bar**: Access to all main app sections
- **Settings Categories**: Organized sections for different types of settings
- **Toggle Controls**: On/off switches for various options
- **Action Buttons**: Buttons for account management and security
- **Status Indicators**: Current state of various settings

### Settings Categories
The Settings screen is organized into several categories:
- **Notifications**: Control helpful reminders and alerts
- **Security**: Manage two-factor authentication and account security
- **Account**: Update personal information and account settings
- **Subscription**: Manage billing and subscription details
- **Privacy**: Control data sharing and privacy preferences

### User Interactions
Users can:
- **Toggle Settings**: Turn various options on or off
- **Access Submenus**: Navigate to detailed configuration screens
- **Update Information**: Modify account and personal details
- **Manage Security**: Set up two-factor authentication
- **Control Notifications**: Customize alert preferences

### Common User Scenarios
- **Notification Management**: Users can customize their alert preferences
- **Security Setup**: Users can enable two-factor authentication for better protection
- **Account Updates**: Users can modify personal information and passwords
- **Subscription Management**: Users can view and manage their billing status

### Detailed Settings Options

#### Notifications
- **Title**: "Notifications"
- **Description**: "Get helpful reminders and insights on your phone. No spam!"
- **Control**: Toggle On/Off
- **Default**: Active by default

#### Security (2FA)
- **Title**: "Two-Factor Authentication"
- **Description**: "Add an extra layer of security to your account"
- **Control**: Toggle On/Off
- **Default**: Off by default
- **Setup Process**: Step-by-step instructions with QR code or setup key

#### Account Management
- **Vera Account**: Main account management
- **Change Password**: Update your password
- **Delete Account**: Remove your account (requires confirmation)

### Business Rules and Security
- **Notification Defaults**: Helpful reminders are active by default
- **Security Setup**: Two-factor authentication is optional but recommended
- **Account Changes**: Password changes require current password verification
- **Account Deletion**: Requires confirmation and may have data retention policies
- **Privacy Controls**: Users can control data sharing and privacy preferences

#### Subscription
- **Manage Subscription**: Handle your subscription
- **Billing Info**: View billing information
- **Trial Status**: Check your trial period status

### Navigation Options
From Settings, users can navigate to:
- Home for main dashboard
- Financial Info for account management
- Memories for AI learning management
- Help Center for support and resources

### 2FA Setup Modal
When users enable two-factor authentication, they see:
- **Title**: "Two-Factor Authentication"
- **Instructions**: Step-by-step setup process
- **QR Code**: For authenticator app setup
- **Setup Key**: Alternative manual setup method
- **Setup Data**: Account name, key, and key type information
- **Action Buttons**: "Cancel" and "Validate"

### Troubleshooting
- **Settings not saving**: Ensure internet connection and try again
- **2FA not working**: Use a compatible authenticator app like Google Authenticator
- **Can't change password**: Verify current password before setting a new one
- **Subscription issues**: Subscription changes are handled through app store

### Navigation Options
From Settings, users can navigate to:
- My Account for account management
- My Subscription for subscription management
- Home for main dashboard

## Financial Info Section

### Purpose
The Financial Info section provides comprehensive management of all financial data including accounts, income, expenses, assets, liabilities, and payment reminders. It serves as the central hub for financial data management.

### Layout and Components
The Financial Info section includes:
- **Account Management**: Bank accounts and credit cards
- **Income Tracking**: Salary and other income sources
- **Expense Management**: Spending categories and tracking
- **Asset Management**: Investments and property
- **Liability Tracking**: Debts and loans
- **Payment Reminders**: Bill and payment notifications

### Financial Info Menu

#### Menu Structure
- **Header**: "Financial Info" with navigation
- **Menu Items**: Each option includes:
  - Functionality title (e.g., "Accounts and Cards")
  - Brief functionality description
  - Action button (right arrow)
  - Navigation to specific configuration

#### Visual States
- **With Configuration**: Translucent background, soft borders, action buttons
- **Without Configuration**: Show empty state
- **Advanced Configuration**: Additional screens for each category

### Financial Info Categories

#### Accounts and Cards
- **Title**: "Accounts and Cards"
- **Description**: "Manage your connected bank accounts and cards, or add new ones"
- **Functionality**: Management of connected bank accounts and cards
- **Action**: Navigate to account configuration

#### Income and Expenses
- **Title**: "Income and Expenses"
- **Description**: "See what's coming from your connected accounts and cards, or add info manually"
- **Functionality**: View and manage income and expenses
- **Action**: Navigate to income and expense configuration

#### Assets and Liabilities
- **Title**: "Assets and Liabilities"
- **Description**: "Add and manage what you own and owe to track your net worth"
- **Functionality**: Management of assets and liabilities for net worth tracking
- **Action**: Navigate to assets and liabilities configuration

#### Payment Reminders
- **Title**: "Payment Reminders"
- **Description**: "Set up alerts for upcoming payments so you never miss one"
- **Functionality**: Configuration of alerts for upcoming payments
- **Action**: Navigate to reminder configuration

### Business Rules
- **Account Management**: Connected bank accounts and cards management
- **Income/Expenses**: View from connected accounts or manual entry
- **Assets/Liabilities**: Net worth tracking
- **Reminders**: Customizable payment alerts
- **Persistence**: Configurations save automatically

### Navigation Options
From Financial Info, users can navigate to:
- Accounts and Cards for account management
- Income and Expenses for financial tracking
- Assets and Liabilities for net worth management
- Payment Reminders for bill alerts
- Home for main dashboard

### User Interactions
- **Navigation**: Tap any menu item to access configuration
- **Action Button**: Tap right arrow to navigate
- **Configuration**: Each category leads to specific configuration screen
- **Back**: Standard navigation to return to Financial Info

### Navigation from Financial Info
- **Accounts and Cards** → [Accounts and Cards](#accounts-and-cards)
- **Income and Expenses** → [Income and Expenses](#income-and-expenses)
- **Assets and Liabilities** → [Assets and Liabilities](#assets-and-liabilities)
- **Payment Reminders** → [Payment Reminders](#payment-reminders)
- **Back to Home** → [Home](#home)
- **Back to Sidebar** → [Sidebar](#sidebar)

## Accounts and Cards

- **Purpose**: Management of connected bank accounts and cards, allowing users to view, filter, disconnect, and add new financial accounts.

- **Functionality**:
  - List of connected bank accounts and cards
  - Filters to organize accounts by type
  - Options to disconnect existing accounts
  - Plaid integration for connecting new accounts
  - Connection status and last update

### Accounts and Cards List

#### Content
- **Header**: "Accounts and Cards" with navigation
- **Subheader**: "Connected accounts" with last update
- **Filters**: Segmented buttons to filter by account type
- **Account list**: Each account includes:
  - Account name (e.g., "Citi Checkings account **1234")
  - Connection status (e.g., "Active")
  - Options button (three dots)

#### Visual States
- **With accounts**: List of connected accounts with statuses
- **No accounts**: Empty state with CTA to connect
- **Filtered**: Accounts filtered by selected type

### Connected Account Item

#### Content
- **Name**: Bank account name with last digits
- **Status**: Status badge (Active, Inactive, Error)
- **Options button**: Menu of available actions

#### Visual States
- **Active**: Green text, "Active" status
- **Inactive**: Gray text, "Inactive" status
- **Error**: Red text, "Error" status

### Account Management

#### Available Options
- **Disconnect**: Disconnect account from the application
- **Refresh**: Update account data
- **Settings**: Specific account configuration

#### Disconnection Modal
- **Title**: "Disconnect item?"
- **Description**: "If you disconnect this item, it will be removed from your reports and your insights may be less precise"
- **Buttons**: "Cancel" and "Disconnect item"

### Connect New Account

#### Plaid Integration
- **Header**: Information about Plaid
- **Benefits**:
  - "8000+ apps trust Plaid to quickly connect to financial institutions"
  - "Connect in seconds"
  - "Plaid uses best-in-class encryption to help protect your data"
  - "Keep your data safe"
- **CTA**: Button to start connection process

#### Visual States
- **Connection modal**: Translucent background, Plaid content
- **Connection process**: Guided flow to connect account
- **Confirmation**: Account connection confirmation

### Business Rules
- **Connection**: Plaid integration for connecting bank accounts
- **Updates**: Data updates automatically every 15 minutes
- **Disconnection**: Requires user confirmation
- **Filters**: Accounts can be filtered by type (Banks, Cards, etc.)
- **Persistence**: Changes save automatically

### Interactions
- **Filters**: Tap segmented button to filter accounts
- **Options**: Tap options button to see menu
- **Disconnect**: Tap "Disconnect" to open confirmation modal
- **Connect**: Tap CTA to start connection process
- **Modal**: Tap "X" or "Cancel" to close modals

### Navigation from Accounts and Cards
- **Add Account** → [Add Account](#add-account) (Plaid connection process)
- **Back to Financial Info** → [Financial Info](#financial-info)
- **Back to Home** → [Home](#home)

## Income and Expenses

- **Purpose**: Management of user income and expenses, allowing users to add, edit, and categorize financial transactions for tracking and analysis.

- **Functionality**:
  - List of income and expenses with categorization
  - Filters to organize by type (Income/Expense)
  - Cash flow summary with money in/out breakdown
  - Options to add, edit, and delete items
  - Automatic and manual categorization

### Income and Expenses List

#### Content
- **Header**: "Income & Expenses" with navigation
- **Subheader**: "Items" with counter and "Add" button
- **Cash flow summary**: 
  - Net cash flow: calculated value (e.g., "$26,275.00")
  - Money in: total income (e.g., "$40,432.00")
  - Money out: total expenses (e.g., "$14,157")
- **Filters**: Segmented buttons (Income/Expense)
- **Item list**: Each item includes:
  - Item name (e.g., "Tesla Model 3")
  - Value (e.g., "$32,000")
  - Category (e.g., "Transportation")
  - "Edit" button

#### Visual States
- **With items**: List of income and expenses with values
- **No items**: Empty state with CTA to add
- **Filtered**: Items filtered by selected type

### Income/Expense Item

#### Content
- **Name**: Descriptive item name
- **Value**: Amount in monetary format
- **Category**: Category assigned to the item
- **Edit button**: Option to edit the item

#### Visual States
- **Income**: Green value, income category
- **Expense**: Red value, expense category
- **Edited**: Visual highlight for pending changes

### Add/Edit Item Modal

#### Content
- **Title**: "Add new item" with close button
- **Type**: Segmented buttons (Income/Expense)
- **Category**: Dropdown to select category
- **Name**: Text field for item name
- **Value**: Numeric field for amount
- **Button**: "Add item" to confirm

#### Visual States
- **Modal**: Translucent background, centered content
- **Fields**: Gray borders, informative placeholders
- **Button**: Primary style to confirm action

### Cash Flow Summary

#### Content
- **Net cash flow**: Difference between income and expenses
- **Money in**: Total income for the period
- **Money out**: Total expenses for the period
- **Period**: "Info from the last 30 days up to today"

#### Visual States
- **Positive**: Green net cash flow
- **Negative**: Red net cash flow
- **Neutral**: Gray net cash flow

### Business Rules
- **Categorization**: Items are categorized automatically or manually
- **Values**: Amounts formatted with 2 decimal places
- **Period**: Summary shows last 30 days
- **Validation**: Required fields before adding item
- **Persistence**: Changes save automatically

### Interactions
- **Filters**: Tap segmented button to filter by type
- **Add**: Tap "Add" to open creation modal
- **Edit**: Tap "Edit" to modify existing item
- **Modal**: Tap "X" or outside modal to close
- **Confirm**: Tap "Add item" to save changes

### Navigation from Income and Expenses
- **Add Income/Expense** → [Add Income/Expense](#add-incomeexpense) (creation modal)
- **Back to Financial Info** → [Financial Info](#financial-info)
- **Back to Home** → [Home](#home)

## Assets and Liabilities

- **Purpose**: Management of user assets and liabilities for net worth tracking, allowing users to add, edit, and categorize assets and debts.

- **Functionality**:
  - List of assets and liabilities with categorization
  - Filters to organize by type (Assets/Liabilities)
  - Net worth summary with assets/liabilities breakdown
  - Options to add, edit, and delete items
  - Automatic and manual categorization

### Assets and Liabilities List

#### Content
- **Header**: "Assets & Liabilities" with navigation
- **Subheader**: "Items" with counter and "Add" button
- **Net worth summary**: 
  - Total net worth: calculated value (e.g., "$26,275.00")
  - Assets: total assets (e.g., "$40,432.00")
  - Liabilities: total liabilities (e.g., "$14,157")
- **Filters**: Segmented buttons (Assets/Liabilities)
- **Item list**: Each item includes:
  - Item name (e.g., "Tesla Model 3")
  - Value (e.g., "$32,000")
  - Category (e.g., "Vehicle")
  - "Edit" button

#### Visual States
- **With items**: List of assets and liabilities with values
- **No items**: Empty state with CTA to add
- **Filtered**: Items filtered by selected type

### Asset/Liability Item

#### Content
- **Name**: Descriptive item name
- **Value**: Amount in monetary format
- **Category**: Category assigned to the item
- **Edit button**: Option to edit the item

#### Visual States
- **Asset**: Green value, asset category
- **Liability**: Red value, liability category
- **Edited**: Visual highlight for pending changes

### Add/Edit Item Modal

#### Content
- **Title**: "Add new item" with close button
- **Type**: Segmented buttons (Asset/Liability)
- **Category**: Dropdown to select category
- **Name**: Text field for item name
- **Value**: Numeric field for value
- **Button**: "Add item" to confirm

#### Visual States
- **Modal**: Translucent background, centered content
- **Fields**: Gray borders, informative placeholders
- **Button**: Primary style to confirm action

### Net Worth Summary

#### Content
- **Total net worth**: Difference between assets and liabilities
- **Assets**: Total user assets
- **Liabilities**: Total user liabilities
- **Period**: "Info from the last 30 days up to today"

#### Visual States
- **Positive**: Green net worth
- **Negative**: Red net worth
- **Neutral**: Gray net worth

### Business Rules
- **Categorization**: Items are categorized automatically or manually
- **Values**: Amounts formatted with 2 decimal places
- **Net worth**: Calculated as difference between assets and liabilities
- **Validation**: Required fields before adding item
- **Persistence**: Changes save automatically

### Interactions
- **Filters**: Tap segmented button to filter by type
- **Add**: Tap "Add" to open creation modal
- **Edit**: Tap "Edit" to modify existing item
- **Modal**: Tap "X" or outside modal to close
- **Confirm**: Tap "Add item" to save changes

### Navigation from Assets and Liabilities
- **Add Asset/Liability** → [Add Asset/Liability](#add-assetliability) (creation modal)
- **Back to Financial Info** → [Financial Info](#financial-info)
- **Back to Home** → [Home](#home)

## Payment Reminders

- **Purpose**: Management of user payment reminders, allowing users to create, edit, pause, and activate alerts for recurring and one-time payments.

- **Functionality**:
  - List of payment reminders with states
  - Options to add, edit, pause, and activate reminders
  - Frequency and due date configuration
  - Sync and activation states
  - Manual and automatic reminders

### Payment Reminders List

#### Content
- **Header**: "Payment Reminders" with navigation
- **Subheader**: "Reminders" with counter and "Add" button
- **Reminder list**: Each reminder includes:
  - Reminder name (e.g., "Electricity bill")
  - Status (Active, Paused, Synced)
  - Action buttons (Edit, Pause, Activate)

#### Visual States
- **With reminders**: List of reminders with states
- **No reminders**: Empty state with CTA to add
- **Filtered**: Reminders filtered by state

### Payment Reminder Item

#### Content
- **Name**: Descriptive reminder name
- **Status**: Status badge (Active, Paused, Synced)
- **Action buttons**: Available options based on status

#### Visual States
- **Active**: "Active" status in green
- **Paused**: "Paused" status in gray
- **Synced**: "Synced" status with sync icon
- **Edited**: Visual highlight for pending changes

### Add/Edit Reminder Modal

#### Content
- **Title**: "Add new reminder" with close button
- **What you're paying**: Text field for description
- **Due date**: Frequency configuration:
  - Repeat every: dropdown (Month, Week, etc.)
  - On: dropdown (1st, 2nd, etc.)
- **Button**: "Add reminder" to confirm

#### Visual States
- **Modal**: Translucent background, centered content
- **Fields**: Gray borders, informative placeholders
- **Button**: Primary style to confirm action

### Reminder States

#### Available States
- **Active**: Reminder active and working
- **Paused**: Reminder temporarily paused
- **Synced**: Reminder synced with bank account

#### Actions by State
- **Active**: Edit, Pause
- **Paused**: Edit, Activate
- **Synced**: Edit (cannot be paused)

### Business Rules
- **Frequency**: Reminders can be monthly, weekly, etc.
- **Dates**: Configuration of specific day of month/week
- **Sync**: Automatic reminders cannot be paused
- **Validation**: Required fields before adding reminder
- **Persistence**: Changes save automatically

### Interactions
- **Add**: Tap "Add" to open creation modal
- **Edit**: Tap "Edit" to modify existing reminder
- **Pause**: Tap "Pause" to pause active reminder
- **Activate**: Tap "Activate" to reactivate paused reminder
- **Modal**: Tap "X" or outside modal to close
- **Confirm**: Tap "Add reminder" to save changes

### Navigation from Payment Reminders
- **Add Reminder** → [Add Reminder](#add-reminder) (creation modal)
- **Back to Financial Info** → [Financial Info](#financial-info)
- **Back to Home** → [Home](#home)

## Chat

- **Purpose**: Main conversation with Vera, the financial AI assistant, to get help, create goals, manage finances, and resolve questions.

- **Functionality**:
  - Real-time conversation with Vera
  - Automatic context based on user data
  - Available actions: pin, refresh, thumbs up/down
  - Shortcuts for quick actions
  - Integration with all app functionalities

### Chat Interface

#### Content
- **Header**: "Chat with Vera" with options
- **Conversation**: Messages from Vera and user
- **Input**: Text field with placeholder "Write something..."
- **Actions**: pin, refresh, thumbs up/down, bullet points
- **Shortcuts**: Quick access buttons to functionalities

#### Visual States
- **Active conversation**: Real-time messages
- **Loading**: Indicator that Vera is thinking
- **Error**: Error message with retry option

### Navigation from Chat
- **Moodcheck** → [Mood Check](#mood-check) (if available)
- **Thought process** → [Thought Process](#thought-process) (view reasoning process)
- **Memory creation** → [Memory Creation](#memory-creation) (view created memories)
- **Source detail** → [Sources](#sources) (view used sources)
- **Pin a message** → [Pinned Messages](#pinned-messages) (pin current message)
- **Back to Home** → [Home](#home)

## Goal Detail

- **Purpose**: Specific conversation about an individual goal, allowing users to discuss, update, and manage that particular goal.

- **Functionality**:
  - Specific goal context always visible
  - Conversation focused on that goal
  - Goal-specific actions available
  - Progress and status updated in real-time

### Goal Detail Interface

#### Content
- **Goal Context Card**: Goal information (name, status, progress)
- **Conversation**: Messages specific to the goal
- **Goal actions**: Update, pause, complete, adjust
- **Visual progress**: Progress bar and metrics

#### Visual States
- **Active goal**: Green context, visible progress
- **Paused goal**: Gray context, option to resume
- **Completed goal**: Green context, celebration

### Navigation from Goal Detail
- **Back to Goals** → [Goals](#goals)
- **Back to Home** → [Home](#home)
- **Pin conversation** → [Pinned Messages](#pinned-messages)

## Pinned Message Detail

- **Purpose**: Detailed view of a pinned message, allowing users to see complete content and resume conversation from that point.

- **Functionality**:
  - Complete pinned message content
  - Option to resume conversation
  - Message management actions
  - Context of when it was pinned

### Pinned Message Detail Interface

#### Content
- **Message title**: Descriptive name
- **Complete content**: Formatted message text
- **Metadata**: Pinning date, context
- **Actions**: continue conversation, unpin, delete
- **Continue conversation**: Button to resume dialogue

#### Visual States
- **Complete message**: Content visible with formatting
- **Resumed conversation**: Transition to chat with context

### Navigation from Pinned Message Detail
- **Continue conversation** → [Chat](#chat) (with message context)
- **Back to Pinned Messages** → [Pinned Messages](#pinned-messages)
- **Back to Home** → [Home](#home)

## Net Worth Detail

- **Purpose**: Detailed view of user's net worth with charts, breakdowns, and deep analysis.

- **Functionality**:
  - Net worth evolution charts
  - Detailed assets and liabilities breakdown
  - Trends and projections
  - Temporal comparisons

### Net Worth Detail Interface

#### Content
- **Main chart**: Net worth evolution over time
- **Assets breakdown**: Categories and values
- **Liabilities breakdown**: Categories and values
- **Trends**: Percentage changes and projections
- **Actions**: Update data, export, share

#### Visual States
- **With data**: Complete charts and breakdowns
- **No data**: Invitation to add information
- **Loading**: Skeletons during update

### Navigation from Net Worth Detail
- **Back to Reports** → [Reports](#reports)
- **Back to Home** → [Home](#home)
- **Add Assets** → [Assets and Liabilities](#assets-and-liabilities)
- **Add Liabilities** → [Assets and Liabilities](#assets-and-liabilities)

## Cash Flow Detail

- **Purpose**: Detailed view of user's cash flow with charts, categories, and income/expense analysis.

- **Functionality**:
  - Cash flow charts by period
  - Income and expense categorization
  - Spending patterns and trends
  - Temporal comparisons

### Cash Flow Detail Interface

#### Content
- **Main chart**: Cash flow evolution
- **Income categories**: Breakdown by type
- **Expense categories**: Breakdown by type
- **Trends**: Patterns and projections
- **Actions**: Update data, export, share

#### Visual States
- **With data**: Complete charts and categories
- **No data**: Invitation to add information
- **Loading**: Skeletons during update

### Navigation from Cash Flow Detail
- **Back to Reports** → [Reports](#reports)
- **Back to Home** → [Home](#home)
- **Add Income** → [Income and Expenses](#income-and-expenses)
- **Add Expenses** → [Income and Expenses](#income-and-expenses)

## Paywall

- **Purpose**: Screen shown when user needs a subscription to access certain premium functionalities.

- **Functionality**:
  - Information about subscription benefits
  - Available subscription options
  - Integrated payment process
  - Option to continue with free version

### Paywall Interface

#### Content
- **Title**: "Let's keep the chats going!"
- **Subtitle**: "Continue unlocking smart guidance"
- **Benefits**: List of three main benefits:
  - "Personalized insights on money and life that get better every chat"
  - "From big dreams to small steps, Vera helps you track and reach your goals"
  - "Your data stays private and you're always in control of what you share"
- **Pricing**: 
  - Price: "$5.00"
  - Frequency: "Monthly"
  - Additional info: "Cancel anytime. No ads, no hidden costs."
- **CTA**: "Subscribe now" button
- **Close Button**: "X" button to close modal

#### Visual States
- **Modal**: Translucent background, rounded top corners
- **Title**: Large purple text
- **Benefits**: List with purple checkmark icons
- **Pricing Card**: Light purple card with subscription details
- **CTA Button**: White button with black text
- **Loading**: During payment process
- **Success**: Subscription confirmation

### Business Rules
- **Trial Limitations**: No limitations - users can use all features unlimitedly like a paid user
- **Pricing**: $5.00 monthly subscription
- **Cancellation**: Users can cancel anytime
- **No Ads**: No advertisements in the app
- **No Hidden Costs**: Transparent pricing with no additional fees

### Navigation from Paywall
- **Subscribe** → [My Subscription](#my-subscription) (after payment)
- **Skip** → [Home](#home) (continue free)
- **Back** → previous screen

## Thought Process

- **Purpose**: Visualization of Vera's reasoning process, showing how it reached a specific conclusion.

- **Functionality**:
  - Vera's reasoning steps
  - Consulted sources
  - Applied logic
  - Intermediate conclusions

### Thought Process Interface

#### Content
- **Reasoning steps**: Logical sequence
- **Sources**: Used references
- **Logic**: Process explanation
- **Conclusions**: Final result

#### Visual States
- **Complete process**: All steps visible
- **Partial process**: Some steps hidden
- **Loading**: Generating reasoning process

### Navigation from Thought Process
- **Back to Chat** → [Chat](#chat)
- **View Sources** → [Sources](#sources)
- **Back to Home** → [Home](#home)

### Shortcuts Interface

#### Content
- **Not available**: No shortcuts implemented

#### Visual States
- **Not available**: No shortcuts in the application

### Navigation from Shortcuts
- **Not applicable**: No shortcuts available

## My Account

- **Purpose**: User account management, including personal information, security, and account configuration.

- **Functionality**:
  - User personal information
  - Security configuration
  - Data management
  - Account options

### My Account Interface

#### Content
- **Profile Info**: Personal information
- **Security Settings**: Security configuration
- **Data Management**: Data management
- **Account Options**: Account options

#### Visual States
- **Complete profile**: All information visible
- **Incomplete profile**: Missing fields
- **Loading**: Updating information

### Navigation from My Account
- **Change Password** → [Change Password](#change-password)
- **My Subscription** → [My Subscription](#my-subscription)
- **Back to Settings** → [Settings](#settings)
- **Back to Home** → [Home](#home)

## Change Password

- **Purpose**: User password change with security validation.

- **Functionality**:
  - Current password validation
  - New password creation
  - New password confirmation
  - Security validation

### Change Password Interface

#### Content
- **Current Password**: Field for current password
- **New Password**: Field for new password
- **Confirm Password**: New password confirmation
- **Security Requirements**: Security requirements
- **Save**: Button to save changes

#### Visual States
- **Validation**: Security indicators
- **Error**: Error messages
- **Success**: Change confirmation

### Navigation from Change Password
- **Back to My Account** → [My Account](#my-account)
- **Back to Settings** → [Settings](#settings)

## My Subscription

- **Purpose**: User subscription management, including billing information, renewal, and cancellation.

- **Functionality**:
  - Current subscription status
  - Billing information
  - Renewal options
  - Cancellation management

### My Subscription Interface

#### Content
- **Subscription Status**: Current status
- **Billing Info**: Billing information
- **Renewal Options**: Renewal options
- **Cancel Subscription**: Cancel option
- **Payment Methods**: Payment methods

#### Visual States
- **Active**: Active subscription
- **Expired**: Expired subscription
- **Cancelled**: Cancelled subscription

### Navigation from My Subscription
- **Back to My Account** → [My Account](#my-account)
- **Back to Settings** → [Settings](#settings)
- **Manage Billing** → [Billing Info](#billing-info)

## Billing Info

- **Purpose**: Detailed user billing information, including payment history and payment methods.

- **Functionality**:
  - Invoice history
  - Payment methods
  - Billing information
  - Invoice downloads

### Billing Info Interface

#### Content
- **Payment History**: Payment history
- **Payment Methods**: Payment methods
- **Billing Address**: Billing address
- **Download Invoices**: Download invoices

#### Visual States
- **With history**: Invoices visible
- **No history**: Empty state
- **Loading**: Loading information

### Navigation from Billing Info
- **Back to My Subscription** → [My Subscription](#my-subscription)
- **Back to Settings** → [Settings](#settings)

## Add Account

- **Purpose**: Process of connecting new bank accounts and cards through Plaid integration.

- **Functionality**:
  - Plaid integration for connecting accounts
  - Financial institution selection
  - Secure authentication
  - Successful connection confirmation

### Add Account Interface

#### Content
- **Plaid Integration**: Connection interface
- **Bank Selection**: List of available banks
- **Authentication**: Authentication process
- **Confirmation**: Connection confirmation

#### Visual States
- **Selection**: List of available banks
- **Authentication**: Login process
- **Loading**: Connecting account
- **Success**: Account connected successfully

### Navigation from Add Account
- **Back to Accounts and Cards** → [Accounts and Cards](#accounts-and-cards)
- **Back to Financial Info** → [Financial Info](#financial-info)

## Add Income/Expense

- **Purpose**: Modal to add new income or expenses to the financial tracking system.

- **Functionality**:
  - Type selection (Income/Expense)
  - Automatic or manual categorization
  - Field validation
  - Automatic saving

### Add Income/Expense Interface

#### Content
- **Type Selection**: Segmented buttons (Income/Expense)
- **Category**: Category dropdown
- **Name**: Text field for name
- **Amount**: Numeric field for amount
- **Save**: Confirmation button

#### Visual States
- **Modal**: Translucent background, centered content
- **Validation**: Required field indicators
- **Loading**: Saving item

### Navigation from Add Income/Expense
- **Back to Income and Expenses** → [Income and Expenses](#income-and-expenses)
- **Back to Financial Info** → [Financial Info](#financial-info)

## Add Asset/Liability

- **Purpose**: Modal to add new assets or liabilities to the net worth tracking system.

- **Functionality**:
  - Type selection (Asset/Liability)
  - Automatic or manual categorization
  - Field validation
  - Automatic saving

### Add Asset/Liability Interface

#### Content
- **Type Selection**: Segmented buttons (Asset/Liability)
- **Category**: Category dropdown
- **Name**: Text field for name
- **Value**: Numeric field for value
- **Save**: Confirmation button

#### Visual States
- **Modal**: Translucent background, centered content
- **Validation**: Required field indicators
- **Loading**: Saving item

### Navigation from Add Asset/Liability
- **Back to Assets and Liabilities** → [Assets and Liabilities](#assets-and-liabilities)
- **Back to Financial Info** → [Financial Info](#financial-info)

## Add Reminder

- **Purpose**: Modal to create new payment reminders with frequency and date configuration.

- **Functionality**:
  - Reminder description
  - Frequency configuration
  - Date selection
  - Field validation

### Add Reminder Interface

#### Content
- **Description**: Text field for description
- **Frequency**: Frequency dropdown (Month, Week, etc.)
- **Day**: Specific day dropdown
- **Save**: Confirmation button

#### Visual States
- **Modal**: Translucent background, centered content
- **Validation**: Required field indicators
- **Loading**: Saving reminder

### Navigation from Add Reminder
- **Back to Payment Reminders** → [Payment Reminders](#payment-reminders)
- **Back to Financial Info** → [Financial Info](#financial-info)

## Help Center

- **Purpose**: User help and support center, providing access to documentation, FAQ, and contact.

- **Functionality**:
  - Web view with help content
  - FAQ and documentation
  - Contact options
  - Topic search

### Help Center Interface

#### Content
- **Web View**: Help content in web
- **Search**: Search field
- **Categories**: Help categories
- **Contact**: Contact options

#### Visual States
- **Loading**: Loading web content
- **Error**: Connection error
- **Content**: Help visible

### Navigation from Help Center
- **Back to Sidebar** → [Sidebar](#sidebar)
- **Back to Home** → [Home](#home)

---