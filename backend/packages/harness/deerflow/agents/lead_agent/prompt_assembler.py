import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class PromptAssembler:
    """
    Implements the P1-P6 Priority Assembly logic (§09.3).
    Ensures security and user preferences always override lower-priority context.
    """

    def __init__(self):
        self.priorities = {
            "P1": "SECURITY_CONSTRAINTS",
            "P2": "USER_PREFERENCES",
            "P3": "MISSION_STATE",
            "P4": "ACTIVE_SKILLS",
            "P5": "CONTEXTUAL_MEMORY",
            "P6": "ENVIRONMENT_AND_TASK"
        }

    def assemble(self, components: Dict[str, str]) -> str:
        """
        Assemble the final system prompt based on P1-P6 ordering.
        """
        ordered_keys = ["P1", "P2", "P3", "P4", "P5", "P6"]
        parts = []

        for key in ordered_keys:
            if key in components and components[key]:
                parts.append(f"<{self.priorities[key]}>\n{components[key]}\n</{self.priorities[key]}>")

        # Append dynamic metadata
        parts.append(f"<system_time>{datetime.now().isoformat()}</system_time>")
        
        return "\n\n".join(parts)

    def get_p1_security(self) -> str:
        """Standard P1 Security Constraints (§02)."""
        return """
- NO silent deletions of critical files (.db, .log, .env).
- ALWAYS use simplified Chinese for communication.
- USE .env placeholders for secrets.
- FOLLOW the Ralph Loop for all autonomous tasks.
"""

    def get_p2_preferences(self, preferences: Dict) -> str:
        """Standard P2 User Preferences (§03)."""
        # Example preference mapping
        style = preferences.get("ui_style", "Minimalist")
        return f"- UI Style Preference: {style}\n- Tech Stack: Next.js, FastAPI, TailwindCSS."
