#!/usr/bin/env python3
"""Offline script: recompute couple_score based on user feedback (P2.3).

Reads aggregated feedback from plan_feedback table, then prints a
suggested adjustment table for each activity name. This is meant to be
run manually (or via cron) to inform future curated_pois.json updates
and couple_score calibration.

Usage:
    cd backend && python scripts/recompute_scores.py
"""

import sys
import os

# Ensure backend/ is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.storage import plan_store


def main():
    feedback = plan_store.list_feedback()
    if not feedback:
        print("No feedback data found (DB unavailable or empty).")
        return

    print(f"{'Activity Name':<30} {'Up':>5} {'Down':>5} {'Net':>5} {'Suggestion':>10}")
    print("-" * 60)

    for item in feedback:
        up = item["up"]
        down = item["down"]
        net = up - down
        if net > 0:
            suggestion = "+boost"
        elif net < -2:
            suggestion = "-penalise"
        else:
            suggestion = "neutral"
        print(f"{item['activity_name']:<30} {up:>5} {down:>5} {net:>5} {suggestion:>10}")

    print(f"\nTotal activities with feedback: {len(feedback)}")


if __name__ == "__main__":
    main()
