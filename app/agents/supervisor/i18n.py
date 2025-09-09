from __future__ import annotations

import random


def _get_random_step_planning_current() -> str:
    """Get random current state message for step planning."""
    options = [
        "Just a sec, I'm thinking...",
        "Let me think this through...",
        "Let me figure out the best approach..."
    ]
    return random.choice(options)

def _get_random_step_planning_completed() -> str:
    """Get random completed state message for step planning."""
    options = [
         "All done here!",
        "That's everything for now",
        "Response complete"
    ]
    return random.choice(options)

def _get_random_finance_current() -> str:
    """Get random current state message for FinanceAgent."""
    options = [
        "Diving into your financial information...",
        "Taking a quick look at your finances...",
        "Analyzing your financial info..."
    ]
    return random.choice(options)

def _get_random_finance_completed() -> str:
    """Get random completed state message for FinanceAgent."""
    options = [
        "Done, I've scanned your finances.",
        "All set, financial statements checked!",
        "Financial analysis complete!"
    ]
    return random.choice(options)

def _get_random_budget_current() -> str:
    """Get random current state message for BudgetAgent (goal agent)."""
    options = [
        "Reviewing your goals...",
        "Checking progress on your goals...",
        "Analyzing your goals to see the path ahead..."
    ]
    return random.choice(options)

def _get_random_budget_completed() -> str:
    """Get random completed state message for BudgetAgent (goal agent)."""
    options = [
        "Done, goals checked!",
        "All set, here's your goals update",
        "Finished! Your goals review is complete"
    ]
    return random.choice(options)

def _get_random_wealth_current() -> str:
    """Get random current state message for Education & Wealth CoachAgent."""
    options = [
        "Switching to guide mode for a sec...",
        "Switching to brainy mode...",
        "Activating coaching expertise..."
    ]
    return random.choice(options)

def _get_random_wealth_completed() -> str:
    """Get random completed state message for Education & Wealth CoachAgent."""
    options = [
        "Done, here's a clear explanation",
        "All set, here's the wisdom straight up",
        "All set, here's the insight you need!"
    ]
    return random.choice(options)

