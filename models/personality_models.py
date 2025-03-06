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
    communication_style: str = "standard"
    response_characteristics: Dict = field(default_factory=dict)

    def get_prompt_modifiers(self) -> str:
        """Generate personality-specific prompt modifiers"""
        modifiers = []
        
        # Add trait modifiers based on subcomponents
        for trait_name, subcomponents in self.traits.items():
            for subcomponent, level in subcomponents.items():
                if level == 'high':
                    modifiers.append(f"- High {trait_name.replace('_', ' ')} ({subcomponent.replace('_', ' ')})")
                elif level == 'low':
                    modifiers.append(f"- Low {trait_name.replace('_', ' ')} ({subcomponent.replace('_', ' ')})")

        # Add communication style as a simple note if not standard
        if self.communication_style and self.communication_style != "standard":
            modifiers.append(f"- Use {self.communication_style} communication style")
            
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