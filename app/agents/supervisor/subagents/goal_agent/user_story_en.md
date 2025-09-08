# User Story: Financial Goals Management with VERA

## 📋 Summary
**As** a VERA user  
**I want** to create and manage my financial goals  
**So that** I can achieve my savings targets and control my spending with the help of my intelligent financial assistant

---

## 🎯 Main Scenario: Discovering VERA's Capabilities

### **Initial Context**
- User: Maria, 28 years old, employee
- Situation: Has been using VERA for basic financial queries
- Discovery: Learns that VERA can help her create and manage financial goals
- Goal: Wants to save $5,000 for a trip in 6 months

### **Interaction Flow**

#### **Step 1: Discovery and Initial Request**
```
Maria: "Hi VERA, I've been thinking about saving for a trip I want to take in 6 months. Can you help me with that?"

VERA: "Of course, Maria! I love helping you with your financial goals. I can help you create a structured savings goal that will help you reach your trip target. How much money do you need to save and in what timeframe?"

Maria: "I need $5,000 for the trip in 6 months. How does this goal thing work?"

VERA: "Perfect, Maria. Let me explain: I can create a personalized goal that includes:
- Your specific target ($5,000 in 6 months)
- An automatic tracking plan
- Alerts when you reach important milestones
- Personalized advice based on your progress

Does it sound good if we create this goal together?"
```

#### **Step 2: Goal Agent Processing**
VERA processes the request internally:

1. **Intent Analysis**: Identifies that Maria wants to create a new goal
2. **State Verification**: Uses `get_goal_requirements` to get required fields
3. **Constraint Validation**: Verifies there are no active "in_progress" goals
4. **Goal Creation**: Uses `create_goal` with provided data

#### **Step 3: VERA's Response**
```
VERA: "Excellent, Maria! I've created your personalized savings goal. Here are all the details:

🎯 **Your Trip Goal**
• Target: $5,000 in 6 months
• Target date: June 15, 2024
• Category: Savings
• Type: Increase savings
• Tracking: Automatic through your linked accounts

📊 **Suggested Savings Plan**
• Recommended monthly savings: ~$833
• Recommended weekly savings: ~$192
• This will allow you to reach your goal comfortably

Would you like to activate this goal now to start automatic tracking, or would you prefer to make any adjustments first?"
```

#### **Step 4: Goal Activation**
```
Maria: "Yes, VERA, please activate the goal. I'm excited to start this savings plan."

VERA: "Perfect, Maria! Your trip goal is now active and starting automatic tracking.

🎉 **Your Goal is Live!**
• Status: In progress and monitored
• Current progress: $0 of $5,000 (0%)
• Days remaining: 180 days
• Next review: Automatic every week

💡 **Tips for Success:**
• I'll send you weekly progress updates
• You'll receive alerts when you reach important milestones (25%, 50%, 75%)
• If you need to adjust anything, just tell me and we'll modify it together

I'm here to accompany you on this journey toward your savings goal! Is there anything else I can help you with regarding your finances?"
```

---

## 🔄 Secondary Scenario: Modify Existing Goal

### **Context**
- Maria already has an "in_progress" goal active
- After 2 weeks, she realizes $5,000 is too ambitious
- Wants to adjust the target amount to something more realistic

#### **Interaction**
```
Maria: "VERA, I've been thinking about my trip goal. I think $5,000 is too ambitious for 6 months. Can I change it to $4,000?"

VERA: "Of course, Maria! It's very smart to adjust your goals to make them achievable. Changing from $5,000 to $4,000 is a very sensible decision.

📊 **Impact of the Change:**
• New monthly savings: ~$667 (instead of $833)
• New weekly savings: ~$154 (instead of $192)
• This will give you more flexibility in your monthly budget

Do you confirm that you want to change your goal to $4,000? This will automatically update your tracking plan."
```

#### **Processing and Confirmation**
```
Maria: "Yes, confirm the change. I feel more comfortable with $4,000."

VERA: "Perfect! I've updated your trip goal.

✅ **Goal Updated:**
• New target: $4,000 (reduced from $5,000)
• Adjusted monthly savings: ~$667
• Your current progress remains: $0 of $4,000 (0%)
• Target date: Still June 15, 2024

Now your goal is more achievable and realistic! I'll continue accompanying you on this journey toward your adjusted goal."
```

---

## ⚠️ Error Scenario: Multiple Active Goals

### **Context**
- Maria tries to create a second goal while having one "in_progress"
- She feels motivated by the success of her first goal and wants to add another

#### **Interaction**
```
Maria: "VERA, I'm doing so well with my trip goal that I want to create another goal to reduce my restaurant spending. Can you help me?"

VERA: "I love your enthusiasm, Maria! It's fantastic that you're doing so well with your trip goal. However, I need to explain something important about how goals work in my system.

⚠️ **System Limitation:**
You currently have an active goal: 'Trip savings' ($4,000 in progress)
My system is designed for you to focus on one goal at a time to maximize your chances of success.

🤔 **What would you prefer to do?**
1. **Pause your trip goal** and create the new restaurant goal
2. **Complete your trip goal first** and then create the new goal
3. **Cancel the new creation** and stay focused on your trip

Which option seems better for your current situation?"
```

#### **Processing and Response**
```
Maria: "You're right, VERA. I better focus on completing my trip first. Can you remind me how much I've saved so far?"

VERA: "Excellent decision, Maria! Focus is key to financial success.

📊 **Current Status of Your Trip Goal:**
• Progress: $1,200 of $4,000 (30% completed)
• Time elapsed: 2 months of 6
• Time remaining: 4 months
• Current monthly savings: $600 (you're doing great!)

🎯 **You're on the right track!** Your 30% progress in 2 months means you're saving at an excellent pace. Keep it up and you'll reach your trip goal without any problems!"
```

---

## ✅ Success Scenario: Complete Goal

### **Context**
- Maria has reached her $4,000 target ahead of schedule
- The system automatically detects the achievement and celebrates the success

#### **Automatic Processing and Celebration**
```
VERA: "🎉 MARIA, YOU DID IT! 🎉

Congratulations! You've reached your savings goal of $4,000 for your trip. Your trip is completely funded!

🏆 **MISSION ACCOMPLISHED!**
• Goal: $4,000 ✅ COMPLETED
• Time: 5 months (1 month ahead of schedule!)
• Final progress: 100% (4,000 of 4,000)
• Achievement date: May 20, 2024

🌟 **What you accomplished:**
• You saved consistently $800 per month
• You exceeded your original goal in record time
• You demonstrated exceptional financial discipline

🎯 **What's next?**
Now that you've completed this goal, you can:
• Create a new financial goal (like reducing restaurant spending)
• Enjoy your trip without financial worries
• Apply the savings strategies you learned

I'm so proud of your achievement, Maria! Would you like to create your next financial goal?"
```

#### **Maria's Response**
```
Maria: "VERA, I can't believe it! Thank you for accompanying me through this process! Now I do want to create that goal to reduce my restaurant spending."

VERA: "Of course, Maria! Now that you've proven you can save successfully, it's the perfect time to create your next goal.

How much would you like to reduce your monthly restaurant spending and in what timeframe?"
```

---

## 🛠️ Tools Used

| Tool | Purpose | When Used |
|------|---------|-----------|
| `get_goal_requirements` | Get required fields | When creating goals |
| `get_in_progress_goal` | Verify active goals | Before creating/activating |
| `create_goal` | Create new goal | Initial request |
| `update_goal` | Modify existing goal | Requested changes |
| `switch_goal_status` | Change goal status | Activation/completion |
| `delete_goal` | Delete goal | Deletion request |

---

## 📊 Goal States

| State | Description | Possible Transitions |
|-------|-------------|---------------------|
| `pending` | Goal created, not active | → `in_progress`, `deleted` |
| `in_progress` | Goal active and monitored | → `completed`, `error`, `paused`, `off_track` |
| `completed` | Goal successfully achieved | → `deleted` |
| `error` | Technical monitoring issue | → `in_progress`, `deleted` |
| `paused` | Goal temporarily paused | → `in_progress`, `deleted` |
| `off_track` | Goal not on track | → `in_progress`, `paused`, `deleted` |
| `deleted` | Goal deleted (soft delete) | - |

---

## 🎯 Acceptance Criteria

- ✅ User can create goals with all required fields
- ✅ Only one "in_progress" goal is allowed at a time
- ✅ Confirmation is requested for destructive actions
- ✅ States transition correctly
- ✅ Errors and edge cases are handled appropriately
- ✅ Responses include structured JSON
- ✅ System state constraints are respected

---

## 🔍 Functionality Validation

This user story demonstrates that the goal_agent:

1. **Understands user intents** correctly
2. **Manages states** according to defined rules
3. **Validates constraints** before executing actions
4. **Provides clear and structured feedback**
5. **Handles errors** gracefully
6. **Follows the decision flow** established in the prompt

The improved system prompt allows the agent to function predictably and reliably for financial goals management.

---

## 📝 Additional Notes

### **Goal Categories Supported**
- **saving, spending, debt** → BudgetAgent responsibility
- **income, investment, net_worth** → BudgetAgent responsibility
- **all categories** → Education & Wealth Coach for guidance

### **Required Fields for Goal Creation**
- goal.title, goal.description
- category.value (saving, spending, debt, income, investment, net_worth, other)
- nature.value (increase, reduce)
- frequency (specific date or recurring pattern)
- amount (absolute USD or percentage with basis)
- evaluation.source (linked_accounts, manual_input, mixed)
- affected_categories (optional, from Plaid categories)

### **State Constraints**
- User can have only ONE goal in "in_progress" status at a time
- User can have multiple goals in "deleted" status
- User can have only ONE goal in any other status at a time (except "deleted" and "in_progress")

This comprehensive user story serves as living documentation of how the goal_agent should function according to the structured system prompt.
