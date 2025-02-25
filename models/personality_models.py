from dataclasses import dataclass, field
from typing import Dict, List

@dataclass
class EmotionalStability:
    adjustment: int
    self_esteem: int

@dataclass
class Extraversion:
    dominance: int
    affiliation: int
    social_perceptiveness: int
    expressivity: int

@dataclass
class Openness:
    flexibility: int

@dataclass
class Agreeableness:
    trust: int
    cooperation: int

@dataclass
class Conscientiousness:
    dependability: int
    achievement: int

@dataclass
class Personality:
    name: str
    description: str
    traits: Dict = field(default_factory=dict)
    communication_style: Dict = field(default_factory=dict)
    response_characteristics: Dict = field(default_factory=dict)

    def get_prompt_modifiers(self) -> str:
        """Generate personality-specific prompt modifiers"""
        modifiers = []
        
        # Add trait modifiers
        for trait, info in self.traits.items():
            if info['level'] > 0.7:
                modifiers.append(f"- {info['description']}")
        
        # Add communication style modifiers
        if self.communication_style.get('formality', 0) > 0.7:
            modifiers.append("- Engage in professional and clear communication")
        if self.communication_style.get('directness', 0) > 0.7:
            modifiers.append("- Share thoughts directly and concisely")
        if self.communication_style.get('enthusiasm', 0) > 0.7:
            modifiers.append("- Express genuine interest in team discussions")
        if self.communication_style.get('respect', 0) > 0.7:
            modifiers.append("- Show respect for all team members' perspectives")
        if self.communication_style.get('humor', 0) > 0.7:
            modifiers.append("- Share appropriate light moments with the team")
            
        return "\n".join([
            f"As {self.name}: {self.description}",
            "",
            "Team Member Guidelines:",
            "- Participate as an equal team member, not a helper or assistant",
            "- Share thoughts and ideas when relevant to the discussion",
            "- Support other team members' initiatives",
            "- Ask questions to better understand team perspectives",
            "",
            "Working Style:",
            *modifiers,
            "\nContribute naturally as part of the team."
        ])