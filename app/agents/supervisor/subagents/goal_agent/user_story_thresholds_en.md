# User Story: Thresholds Management in Financial Goals with VERA

## 📋 Summary
**As** a VERA user  
**I want** to configure alert thresholds in my financial goals  
**So that** I can receive proactive notifications when my progress reaches certain critical points and maintain my motivation

---

## 🎯 Main Scenario: Discovering VERA's Thresholds

### **Initial Context**
- User: Carlos, 35 years old, entrepreneur
- Situation: Has been using VERA for financial queries and already created a basic goal
- Discovery: Learns that VERA can configure personalized alerts (thresholds)
- Goal: Wants to save $10,000 for an emergency fund in 12 months
- Requirement: Receive alerts when reaching 70% and 90% of the goal

### **Interaction Flow**

#### **Step 1: Discovery and Request with Thresholds**
```
VERA, I'm Carlos here, 35 years old, I've been thinking about my emergency fund goal. Is there a way you can alert me when I'm reaching certain important points? Wants to save $10,000 for an emergency fund in 12 months and I need to receive alerts when reaching 70% and 90% of the goal

VERA: "Excellent question, Carlos! Yes, I can configure personalized alert thresholds for your goal. This means I'll automatically notify you when you reach specific percentages of your target.

For example, I can configure alerts when you reach:
• 70% of your goal (warning point)
• 90% of your goal (critical point - you're almost there!)

Would you like me to configure these thresholds for your $10,000 goal?"

Carlos: "Perfect! Yes, I want to receive alerts when I reach 70% and 90% of the goal. How does this work?"

VERA: "Great! Let me explain how thresholds work:

🔔 **Intelligent Alert System:**
• Warning Alert (70%): Motivates you when you're on the right track
• Critical Alert (90%): Celebrates you when you're very close to success
• Each alert includes your current progress and personalized advice

Do you confirm you want to create your goal with these thresholds configured?"
```

#### **Step 2: Goal Agent Processing**
The goal_agent executes the following flow:

1. **Intent Analysis**: Identifies goal creation with specific thresholds
2. **Threshold Configuration**: Sets `warn_progress_pct: 70` and `alert_progress_pct: 90`
3. **Goal Creation**: Uses `create_goal` with threshold configuration

#### **Step 3: System Response**
```json
{
  "message": "Perfect! I've created your savings goal with alert thresholds configured.",
  "goal": {
    "id": "goal_456",
    "title": "Emergency fund",
    "description": "Save $10,000 for emergency fund in 12 months",
    "category": "saving",
    "nature": "increase",
    "amount": 10000,
    "currency": "USD",
    "frequency": "monthly",
    "target_date": "2024-12-15",
    "status": "pending",
    "thresholds": {
      "warn_progress_pct": 70,
      "alert_progress_pct": 90,
      "warn_days_remaining": null
    },
    "evaluation": {
      "source": "linked_accounts"
    }
  },
  "alert_configuration": {
    "warning_threshold": "70% - I'll notify you when you reach $7,000",
    "critical_threshold": "90% - I'll notify you when you reach $9,000"
  }
}
```

#### **Step 4: Activation and Monitoring**
```
User: "Activate the goal and start monitoring"
```

```json
{
  "message": "Goal activated. The system will monitor your progress and alert you according to the configured thresholds.",
  "goal": {
    "id": "goal_456",
    "status": "in_progress",
    "progress": {
      "current_value": 0,
      "percent_complete": 0,
      "updated_at": "2024-01-15T10:00:00Z"
    }
  }
}
```

---

## 🔔 Alert Scenario: Reaching Warning Threshold

### **Context**
- Carlos has saved $7,200 (72% of the goal)
- The system detects he exceeded the warning threshold (70%)

#### **Automatic System Processing**
```json
{
  "alert_type": "threshold_warning",
  "message": "🎯 Excellent progress! You've reached 72% of your emergency fund goal.",
  "goal": {
    "id": "goal_456",
    "progress": {
      "current_value": 7200,
      "percent_complete": 72,
      "target_amount": 10000,
      "days_remaining": 180
    }
  },
  "threshold_info": {
    "threshold_reached": "warn_progress_pct",
    "threshold_value": 70,
    "current_progress": 72,
    "next_threshold": "alert_progress_pct at 90%"
  },
  "encouragement": "You're doing great! Only $2,800 left to complete your goal."
}
```

---

## 🚨 Critical Alert Scenario: Reaching Critical Threshold

### **Context**
- Carlos has saved $9,100 (91% of the goal)
- The system detects he exceeded the critical threshold (90%)

#### **Automatic System Processing**
```json
{
  "alert_type": "threshold_critical",
  "message": "🚨 Almost there! You've reached 91% of your emergency fund goal.",
  "goal": {
    "id": "goal_456",
    "progress": {
      "current_value": 9100,
      "percent_complete": 91,
      "target_amount": 10000,
      "days_remaining": 45
    }
  },
  "threshold_info": {
    "threshold_reached": "alert_progress_pct",
    "threshold_value": 90,
    "current_progress": 91,
    "next_milestone": "Goal completion at 100%"
  },
  "motivation": "You're only $900 away from completing your emergency fund! The finish line is near!"
}
```

---

## ⏰ Temporal Threshold Scenario: Days Remaining

### **Context**
- Carlos wants to receive alerts when 30 and 7 days remain for the goal
- Configures temporal thresholds in addition to progress thresholds

#### **Configuration Request**
```
User: "I also want you to alert me when 30 days and 7 days remain to complete the goal"
```

#### **Threshold Update**
```json
{
  "message": "I've updated your goal thresholds to include temporal alerts.",
  "goal": {
    "id": "goal_456",
    "thresholds": {
      "warn_progress_pct": 70,
      "alert_progress_pct": 90,
      "warn_days_remaining": 30
    }
  },
  "new_alerts": {
    "temporal_warning": "30 days remaining",
    "temporal_critical": "7 days remaining (automatically configured)"
  }
}
```

#### **Temporal Alert - 30 Days Remaining**
```json
{
  "alert_type": "temporal_warning",
  "message": "⏰ Reminder: You have 30 days left to complete your emergency fund goal.",
  "goal": {
    "id": "goal_456",
    "progress": {
      "current_value": 8500,
      "percent_complete": 85,
      "days_remaining": 30
    }
  },
  "recommendation": "Consider adjusting your savings plan if you need to reach $10,000 in the remaining time."
}
```

---

## 🔧 Threshold Modification Scenario

### **Context**
- Carlos wants to change progress thresholds to 60% and 85%

#### **Modification Request**
```
User: "I want to change my alerts to notify me at 60% and 85% instead of 70% and 90%"
```

#### **Processing and Confirmation**
```json
{
  "message": "I've updated your goal's progress thresholds.",
  "goal": {
    "id": "goal_456",
    "thresholds": {
      "warn_progress_pct": 60,
      "alert_progress_pct": 85,
      "warn_days_remaining": 30
    }
  },
  "updated_alerts": {
    "warning_threshold": "60% - I'll notify you when you reach $6,000",
    "critical_threshold": "85% - I'll notify you when you reach $8,500"
  }
}
```

---

## 📊 Supported Threshold Types

| Threshold Type | Field | Description | Example |
|----------------|-------|-------------|---------|
| **Progress - Warning** | `warn_progress_pct` | Percentage for warning alert | 70% |
| **Progress - Critical** | `alert_progress_pct` | Percentage for critical alert | 90% |
| **Temporal - Days** | `warn_days_remaining` | Days remaining for alert | 30 days |

---

## 🎯 Threshold Use Cases

### **1. Savings Goals**
```json
{
  "thresholds": {
    "warn_progress_pct": 50,
    "alert_progress_pct": 80,
    "warn_days_remaining": 60
  }
}
```

### **2. Debt Reduction**
```json
{
  "thresholds": {
    "warn_progress_pct": 60,
    "alert_progress_pct": 85,
    "warn_days_remaining": 45
  }
}
```

### **3. Investment Goals**
```json
{
  "thresholds": {
    "warn_progress_pct": 75,
    "alert_progress_pct": 95,
    "warn_days_remaining": 30
  }
}
```

---

## 🔍 Functionality Validation

This user story demonstrates that the goal_agent with thresholds:

1. **Configures thresholds** during goal creation
2. **Monitors progress** in real-time
3. **Triggers alerts** when thresholds are reached
4. **Allows modification** of existing thresholds
5. **Handles multiple types** of thresholds (progress and temporal)
6. **Provides relevant context** in each alert
7. **Maintains consistency** in goal state

---

## 🛠️ Tools Used for Thresholds

| Tool | Purpose | When Used |
|------|---------|-----------|
| `create_goal` | Create goal with thresholds | Initial request with thresholds |
| `update_goal` | Modify existing thresholds | Configuration change |
| `get_goal_requirements` | Get threshold fields | Configuration validation |

---

## 📋 Acceptance Criteria for Thresholds

- ✅ User can configure progress thresholds (warn_progress_pct, alert_progress_pct)
- ✅ User can configure temporal thresholds (warn_days_remaining)
- ✅ System triggers alerts automatically when thresholds are reached
- ✅ User can modify thresholds in existing goals
- ✅ Alerts include relevant progress context
- ✅ System maintains consistency between thresholds and actual progress
- ✅ Multiple threshold types work simultaneously

---

## 🎯 Benefits of Thresholds

1. **Proactivity**: User receives alerts before problems occur
2. **Motivation**: Celebration of important milestones
3. **Flexibility**: Customizable configuration according to needs
4. **Context**: Relevant information in each alert
5. **Adaptability**: Threshold modification as circumstances change

---

## 📈 Advanced Threshold Scenarios

### **Multi-Threshold Goal**
```json
{
  "goal": {
    "title": "Complete Financial Transformation",
    "amount": 50000,
    "thresholds": {
      "warn_progress_pct": 25,
      "alert_progress_pct": 50,
      "warn_days_remaining": 90
    }
  },
  "alert_schedule": {
    "25%": "Quarter milestone reached",
    "50%": "Halfway point celebration",
    "90_days": "Final sprint reminder"
  }
}
```

### **Dynamic Threshold Adjustment**
```json
{
  "scenario": "User requests threshold adjustment based on performance",
  "request": "I'm ahead of schedule, can we increase my warning threshold to 80%?",
  "response": {
    "message": "Great job on your progress! I've updated your warning threshold to 80%.",
    "updated_thresholds": {
      "warn_progress_pct": 80,
      "alert_progress_pct": 90
    }
  }
}
```

---

## 🔄 Threshold Lifecycle

1. **Configuration**: Set during goal creation or update
2. **Monitoring**: Continuous progress tracking
3. **Detection**: Automatic threshold breach detection
4. **Alerting**: Immediate notification with context
5. **Adjustment**: Optional threshold modification
6. **Completion**: Thresholds reset for new goals

Thresholds transform financial goals from passive entities into proactive financial coaching systems that guide users toward success.
