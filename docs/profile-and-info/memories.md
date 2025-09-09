# Memory Management

## Summary

The memory management functionality allows users to control what information Vera remembers about them. Memories are automatically generated from user conversations and categorized by Vera using AI. Users can view, organize, search, and delete their personal memories through a categorized interface.

## Main Features

### 1. Memory Visualization
- **General view**: All memories organized by categories
- **Category view**: Specific filtering by type of information
- **Search**: Memory location by content

### 2. Organization
- **Automatic categorization by Vera**: Memories are automatically grouped into predefined categories using AI (see categories table)
- **Counters**: Visualization of the number of memories per category
- **Metadata**: Temporal and usage information for each memory

### 3. Management
- **Multiple selection**: Batch operations on memories
- **Deletion**: Individual or bulk deletion of memories
- **Filtering**: Search and filtering by content or category

## Memory Creation Process

### Automatic Generation
Memories are created automatically in real-time during user conversations:

1. **Real-time detection**: Vera analyzes each conversation exchange
2. **Automatic classification**: AI determines if information should be stored as memory
3. **Immediate creation**: Memory is created in the hot path during conversation
4. **Intelligent categorization**: Automatically assigns the appropriate category (within existing ones)
5. **Summary extraction**: Generates a concise summary of relevant information
6. **Access assignment**: Determines which agents can access this memory

## Memory update
Existing memories can be updated when:
- Additional information is provided about the same topic
- Previous information is corrected or expanded
- The status of a situation or preference is updated

## Use Cases

### Case 1: Explore Memories by Category
**Actor**: User  
**Objective**: Review memories from a specific category  
**Flow**:
1. User accesses "Your Memories"
2. Selects a category (e.g., "Financial")
3. Views all memories from that category
4. Can navigate between categories

### Case 2: Search for Specific Memory
**Actor**: User  
**Objective**: Find a particular memory  
**Flow**:
1. User accesses the memory view
2. Types search term
3. Views filtered results
4. Can clear search to return to full view

### Case 3: Delete Memories
**Actor**: User  
**Objective**: Remove unwanted memories  
**Flow**:
1. User selects individual memories or "Select all"
2. Confirms deletion
3. System deletes selected memories
4. Updates category counters

## Data Structure

### Individual Memory
```json
{
  "id": "unique_identifier",
  "summary": "memory_summary",
  "category": "assigned_category",
  "category_display": "display_category_name",
  "created_at": "creation_date",
  "updated_at": "update_date",
  "last_accessed": "last_access",
  "importance": "importance_level",
  "pinned": "pinned_status",
  "source": "chat|external",
  "agent_access": ["supervisor", "budget_agent", "finance_agent"]
}
```

### Memory Categories

| Memory Group | Description | Agents with Access |
|--------------|-------------|-------------------|
| **personal_info** | User personal information (name, age, location, etc.) | supervisor, education_agent |
| **financial** | Financial and budget data (income, expenses, budgets) | supervisor, budget_agent, finance_agent |
| **career_studies** | Professional and educational information (work, studies, skills) | supervisor, education_agent |
| **family_relationships** | Family and personal relationships (family, friends, relationships) | supervisor, education_agent |
| **goals_dreams** | Goals and aspirations (personal goals, dreams, plans) | supervisor, education_agent, budget_agent |
| **worries_struggles** | Concerns and challenges (problems, difficulties, challenges) | supervisor, education_agent |
| **preferences_habits** | Preferences and habits (likes, routines, behaviors) | supervisor, budget_agent, finance_agent, education_agent |

### Category View
```json
{
  "category_name": "category_name",
  "memory_count": "number_of_memories",
  "memories": ["array_of_memories"]
}
```

## Interface Components

### 1. Main Components

#### 1.1 Navigation
- **Header**: "Profile & memories" with hierarchical navigation
- **Breadcrumb**: Current navigation path with category counter
- **Side menu**: Access to other sections

#### 1.2 Filters and Search
- **Search bar**: Text field for searching
- **Category list**: Navigation by memory type
- **Counters**: Number of memories per category

#### 1.3 Memory List
- **Memory card**: Individual element with expanded information
- **Category tag**: Visual identifier of the memory category
- **Checkbox**: Selection control
- **Metadata**: Creation/update dates and last usage
- **Action menu**: Individual options (three dots)

#### 1.4 Bulk Actions
- **Selection bar**: Appears when selecting memories
- **Selection counter**: Number of selected elements
- **Action buttons**: Deselect, select all, delete
- **Confirmation modal**: Confirmation before deleting memories

### 2. Interface States

#### 2.1 Initial State
- General view with all categories
- No active selections
- Empty search

#### 2.2 Filtered State
- Memories filtered by category or search
- Updated counters
- Return navigation available

#### 2.3 Selection State
- Memories marked for action
- Action bar visible
- Active selection counter

#### 2.4 Search State
- Results filtered by text
- Real-time search
- Clear filters option

## User Flows

### 1. Main Management Flow

#### 1.1 Access to Memory Management
1. User navigates to "Profile & Info"
2. Selects "Your Memories"
3. System loads general view with all categories
4. Shows memory counters per category

#### 1.2 Category Exploration
1. User selects a specific category
2. System filters and shows memories from that category
3. Maintains search functionality
4. User can return to general view

#### 1.3 Memory Search
1. User types in search field
2. System filters memories in real-time
3. Shows relevant results
4. User can clear search to return to full view

#### 1.4 Selection and Deletion
1. User selects individual memories or "Select all"
2. Action bar appears with counter
3. User confirms deletion
4. System deletes memories and updates counters
5. Shows success confirmation

### 2. Error States

#### 2.1 No Memories
- Shows message: "You have no memories in this category"
- Hides action bar
- Maintains search functionality

#### 2.2 Deletion Error
- Shows specific error message
- Maintains memory selection
- Allows retry operation

#### 2.3 No Search Results
- Shows message: "No memories found with that term"
- Suggests alternative search terms
- Allows clearing search

## Design Considerations

### 1. UX Principles

#### 1.1 Transparency
- Clear memory counters per category
- Visible metadata (dates, importance)
- Immediate feedback on all actions

#### 1.2 User Control
- Granular memory selection
- Confirmation before deletion
- Undo option when possible

#### 1.3 Efficiency
- Real-time search
- Bulk selection
- Intuitive navigation

### 2. Accessibility

- Adequate contrast on all elements
- Appropriate tap sizes
- Keyboard navigation
- Descriptive labels for screen readers

### 3. Responsive Design

- Interface optimized for mobile devices
- Adaptive layout for tablet/desktop
- Intuitive touch gestures

## Memory System Alignment

### LangGraph Store Integration
This management interface is aligned with the V1 memory system defined in `03_Memory_System.md`:

- **Namespaces**: Uses namespaces `(user_id, "memories", "semantic"|"episodic")`
- **Hot-path creation**: Memories are created in real-time during conversations
- **Automatic detection**: Uses LLM (Anthropic Haiku) to detect when to create memories
- **Deduplication**: Verifies similarity before creating new memories
- **Categorization**: Automatically assigns categories based on content

### Data Flow
1. **Conversation** → **Memory detection** → **Immediate creation (hot path)**
2. **Automatic categorization** → **Storage** → **Indexing**
3. **Agent availability** → **User management** → **Update/deletion**