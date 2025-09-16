# 💰 Wealth Agent

A specialized financial education agent that retrieves authoritative information from the knowledge base to help users with personal finance topics and wealth-building guidance.

## 🎯 Purpose

Provides reliable information about:

- **Personal Finance** - Budgeting, saving, and money management
- **Government Programs** - Benefits, assistance, and financial aid
- **Educational Resources** - Financial literacy and learning materials
- **Crisis Support** - Emergency financial assistance programs
- **Credit & Debt** - Management strategies and tools
- **Investment & Wealth Building** - Growth and planning guidance

## 🏗️ Architecture

The Wealth Agent is a LangGraph ReAct agent that uses a knowledge base search tool to find relevant financial information.

### Components
- **Agent**: ReAct agent with AWS Bedrock LLM
- **Tool**: `search_kb` - searches the knowledge base
- **Knowledge Sources**: Government agencies, official portals, and trusted non-profits

## 🔧 Implementation

- **Framework**: LangGraph with MessagesState
- **LLM**: AWS Bedrock with guardrails
- **Tool**: Async knowledge base search
- **Response Style**: Warm, empathetic, actionable guidance

## 📋 Knowledge Base Sources

### ✅ Government Agencies
- CFPB, SEC, FTC, IRS, Department of Education

### ✅ Official Portals  
- MyMoney.gov, StudentAid.gov, Investor.gov

### ✅ Trusted Organizations
- FINRA, FDIC, HUD

## 🔍 Search KB Tool

The `search_kb` tool is the core functionality that enables the wealth agent to retrieve information.

### Input
- **Query** (string): Natural language search query about financial topics
- Example: `"emergency fund building strategies"`

### Process
1. Searches the curated knowledge base using semantic search
2. Retrieves relevant documents and resources
3. Extracts metadata including source URLs and descriptions
4. Formats results with source attribution

### Output
- **JSON Array**: Structured results with source information
- Each result contains:
  - `source`: URL reference (section_url or source_url)
  - `metadata`: Source details (name, type, category, description)
  - `source_url`: Original document URL
  - `section_url`: Specific section reference

### Example Output
```json
[
  {
    "source": "https://www.consumerfinance.gov/about-us/newsroom/",
    "metadata": {
      "name": "CFPB Emergency Fund Guide",
      "type": "Government Guide", 
      "category": "Personal Finance",
      "description": "Official guidance on building emergency savings"
    }
  }
]
```

## 🚀 Example Usage

```python
# The agent responds to queries like:
"How do I apply for student loan forgiveness?"
"What government programs help with housing costs?"  
"How can I dispute errors on my credit report?"
"What are the best savings strategies for emergencies?"
```

## 📁 Files

```
wealth_agent/
├── agent.py      # Agent graph compilation
├── prompts.py    # System prompt and guidelines  
├── tools.py      # Knowledge base search tool
└── README.md     # Documentation
```

## 🔍 How It Works

1. **Search**: Uses `search_kb` tool to query knowledge base
2. **Retrieve**: Gets authoritative financial information
3. **Format**: Provides user-friendly, actionable guidance
4. **Cite**: Includes source attribution and metadata

**Example Response**: "Building an emergency fund is crucial for financial stability! The CFPB recommends starting with just $5-10 per week if that's what you can manage..."
