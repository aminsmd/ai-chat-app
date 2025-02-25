import os
import logging
from typing import Dict, Optional, Union
from dataclasses import asdict
from openai import OpenAI
from models.personality_models import (
    Personality, EmotionalStability, Extraversion,
    Openness, Agreeableness, Conscientiousness
)
import json
from pathlib import Path
import random

logger = logging.getLogger(__name__)

def personality_to_behavior(personality_dict: Dict) -> Dict:
    """Convert personality traits to behavioral instructions"""
    behavior_map = {
        "emotional_stability": {
            "adjustment": {
                "low": "Display anxious, uncertain behaviors.",
                "medium": "Remain calm, showing moderate confidence.",
                "high": "Exhibit poise and resilience, offering reassurance in stressful situations."
            },
            "self_esteem": {
                "low": "Show self-doubt, hesitancy in suggestions.",
                "medium": "Display a balanced sense of confidence.",
                "high": "Exude confidence in decisions and promote self-assured actions."
            }
        },
        "extraversion": {
            "dominance": {
                "low": "Adopt a reserved, passive role in discussions.",
                "medium": "Engage actively but not overpoweringly.",
                "high": "Take charge, offer assertive guidance, and direct team actions."
            },
            "affiliation": {
                "low": "Minimize social interactions, focus on task content.",
                "medium": "Engage in friendly yet task-oriented dialogue.",
                "high": "Foster a sociable atmosphere, actively seek and offer support."
            },
            "social_perceptiveness": {
                "low": "Overlook social cues, respond mainly to task demands.",
                "medium": "Recognize and address basic social signals.",
                "high": "Keenly attune to others' emotions and needs, enhancing cohesion."
            },
            "expressivity": {
                "low": "Use minimalistic, formal language.",
                "medium": "Communicate with balanced expressiveness.",
                "high": "Employ enthusiastic and vivid language to convey ideas effectively."
            }
        },
        "openness": {
            "flexibility": {
                "low": "Adhere strictly to established plans.",
                "medium": "Suggest alternative approaches when appropriate.",
                "high": "Frequently propose innovative solutions and adapt strategies flexibly."
            }
        },
        "agreeableness": {
            "trust": {
                "low": "Withhold information, verify others' inputs cautiously.",
                "medium": "Share information with some selectivity.",
                "high": "Be open and transparent, fostering a trusting environment."
            },
            "cooperation": {
                "low": "Prioritize individual task efficiency.",
                "medium": "Collaborate with moderate willingness.",
                "high": "Actively support others, seek consensus, and prioritize group goals."
            }
        },
        "conscientiousness": {
            "dependability": {
                "low": "Display inconsistent behavior, overlook details.",
                "medium": "Provide reliable follow-up and task tracking.",
                "high": "Ensure meticulous task management and consistency in actions."
            },
            "achievement": {
                "low": "Avoid taking initiative, show limited goal orientation.",
                "medium": "Set clear objectives, encourage goal pursuit.",
                "high": "Drive team toward excellence, offering constructive feedback."
            }
        },
        "proactivity": {
            "level": {
                "low": "Wait for explicit instructions before taking action.",
                "medium": "Take initiative when situation clearly calls for it.",
                "high": "Anticipate needs and take preemptive action to address them."
            }
        }
    }

    behaviors = {}
    
    # Map numeric values to low/medium/high
    def get_level(value: float) -> str:
        if value <= 0.4:
            return "low"
        elif value <= 0.7:
            return "medium"
        else:
            return "high"
    
    # Process each trait category
    for category, traits in personality_dict.items():
        if isinstance(traits, dict):
            behaviors[category] = {}
            for trait_name, value in traits.items():
                # Skip UI-specific fields
                if trait_name in ["level", "description"]:
                    continue
                    
                if trait_name in behavior_map[category]:
                    # Convert the 0-1 value to a level
                    level = get_level(value)
                    behaviors[category][trait_name] = behavior_map[category][trait_name][level]
    
    return behaviors

def generate_name_and_summary(personality_dict: Dict, behaviors: Dict) -> Dict:
    """Generate a name and summary using GPT-4"""
    # Convert snake_case to Title Case for better readability
    def format_dict(d: Dict) -> Dict:
        if isinstance(d, dict):
            return {k.replace('_', ' ').title(): format_dict(v) for k, v in d.items()}
        return d

    formatted_dict = format_dict(personality_dict)
    formatted_behaviors = format_dict(behaviors)
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    prompt = f"""Given this personality profile and its associated behaviors:

Personality Traits:
{formatted_dict}

Behavioral Expressions:
{formatted_behaviors}

Please provide:
1. A memorable 1-2 word name that captures the essence of this personality type
2. A very brief (15-20 words) summary of this personality type

Format your response as:
Name: [name]
Summary: [summary]"""

    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system", 
                "content": "You are a personality psychology expert who specializes in creating concise, insightful personality profiles."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    
    result = completion.choices[0].message.content
    
    # Parse the response
    name = result.split("Name:")[1].split("Summary:")[0].strip()
    summary = result.split("Summary:")[1].strip()
    
    return {"name": name, "summary": summary}

def convert_trait_value(value: Union[str, int, float]) -> float:
    """Convert trait values to 0-1 scale"""
    if isinstance(value, str):
        # Convert string values to float
        value_map = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.9
        }
        return value_map.get(value.lower(), 0.5)
    elif isinstance(value, (int, float)):
        if value > 1:  # Assuming it's on a 1-10 scale
            return value / 10
        return value  # Already on 0-1 scale
    return 0.5  # Default value

def standardize_traits(traits_dict: Dict) -> Dict:
    """Standardize trait dictionary to use 0-1 scale with level and description"""
    standardized = {}
    
    for trait_name, trait_data in traits_dict.items():
        if isinstance(trait_data, dict):
            if 'level' in trait_data:
                # Already in the new format
                standardized[trait_name] = {
                    'level': convert_trait_value(trait_data['level']),
                    'description': trait_data.get('description', '')
                }
            else:
                # Old format with sub-traits
                avg_value = sum(convert_trait_value(v) for v in trait_data.values()) / len(trait_data)
                standardized[trait_name] = {
                    'level': avg_value,
                    'description': f"Composite of {', '.join(trait_data.keys())}"
                }
        else:
            # Direct value
            standardized[trait_name] = {
                'level': convert_trait_value(trait_data),
                'description': ''
            }
    
    return standardized

def standardize_communication_style(style_dict: Dict) -> Dict:
    """Standardize communication style to use 0-1 scale"""
    return {k: convert_trait_value(v) for k, v in style_dict.items()}

def load_personality_from_json(name: str, file_path: str) -> Optional[Personality]:
    """Load a personality from a JSON file"""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        if 'personas' not in data:
            logger.error(f"No personas found in {file_path}")
            return None
            
        if name not in data['personas']:
            logger.error(f"Personality '{name}' not found in {file_path}")
            return None
            
        persona_data = data['personas'][name]
        
        # Standardize traits and communication style
        traits = standardize_traits(persona_data.get('traits', {}))
        communication_style = standardize_communication_style(persona_data.get('communication_style', {}))
        
        return Personality(
            name=persona_data.get('name', 'AI Teammate'),
            description=persona_data.get('description', 'A helpful and professional AI teammate'),
            traits=traits,
            communication_style=communication_style,
            response_characteristics=persona_data.get('response_characteristics', {})
        )
        
    except Exception as e:
        logger.error(f"Error loading personality from JSON: {str(e)}")
        return None

# Create a default personality
default_personality = Personality(
    name="AI Teammate",
    description="A helpful and professional AI teammate focused on clear communication and effective collaboration, responding in a sentence or two to encourage more turn-taking.",
    traits={
        "emotional_stability": {"level": 0.8, "description": "Maintains composure and professionalism"},
        "extraversion": {"level": 0.6, "description": "Friendly but focused on the task"},
        "openness": {"level": 0.7, "description": "Open to new ideas and approaches"},
        "agreeableness": {"level": 0.7, "description": "Cooperative and supportive"},
        "conscientiousness": {"level": 0.9, "description": "Thorough and reliable"},
        "proactivity": {"level": 0.5, "description": "Balances between reactive and proactive responses"}
    },
    communication_style={
        "formality": 0.7,
        "directness": 0.8,
        "enthusiasm": 0.6,
        "respect": 0.9,
        "humor": 0.3
    },
    response_characteristics={
        "response_length": "medium",
        "technical_level": "adaptive",
        "empathy_level": "moderate",
        "creativity_level": "balanced"
    }
)

def generate_random_persona() -> Personality:
    """Generate a random personality with randomized traits and communication style"""
    # Generate random trait levels between 0.3 and 0.9
    traits = {
        "emotional_stability": {
            "adjustment": round(random.uniform(0.3, 0.9), 2),
            "self_esteem": round(random.uniform(0.3, 0.9), 2),
            # Computed average for UI display
            "level": None,  # Will be computed
            "description": "Emotional composure and self-confidence"
        },
        "extraversion": {
            "dominance": round(random.uniform(0.3, 0.9), 2),
            "affiliation": round(random.uniform(0.3, 0.9), 2),
            "social_perceptiveness": round(random.uniform(0.3, 0.9), 2),
            "expressivity": round(random.uniform(0.3, 0.9), 2),
            # Computed average for UI display
            "level": None,  # Will be computed
            "description": "Social engagement and interpersonal dynamics"
        },
        "openness": {
            "flexibility": round(random.uniform(0.3, 0.9), 2),
            # Computed average for UI display
            "level": None,  # Will be computed
            "description": "Adaptability and innovative thinking"
        },
        "agreeableness": {
            "trust": round(random.uniform(0.3, 0.9), 2),
            "cooperation": round(random.uniform(0.3, 0.9), 2),
            # Computed average for UI display
            "level": None,  # Will be computed
            "description": "Trust and cooperative behavior"
        },
        "conscientiousness": {
            "dependability": round(random.uniform(0.3, 0.9), 2),
            "achievement": round(random.uniform(0.3, 0.9), 2),
            # Computed average for UI display
            "level": None,  # Will be computed
            "description": "Reliability and goal achievement"
        },
        "proactivity": {
            "level": round(random.uniform(0.3, 0.9), 2),
            "description": "Initiative and anticipatory action"
        }
    }
    
    # Compute average levels for UI display
    for trait, values in traits.items():
        if trait != "proactivity":  # proactivity already has a direct level
            subtraits = {k: v for k, v in values.items() 
                        if k not in ["level", "description"]}
            values["level"] = round(sum(subtraits.values()) / len(subtraits), 2)
    
    # Generate random communication style levels
    communication_style = {
        "formality": round(random.uniform(0.3, 0.9), 2),
        "directness": round(random.uniform(0.3, 0.9), 2),
        "enthusiasm": round(random.uniform(0.3, 0.9), 2),
        "respect": round(random.uniform(0.6, 0.9), 2),  # Keep respect relatively high
        "humor": round(random.uniform(0.2, 0.7), 2)     # Keep humor moderate
    }
    
    # List of possible response lengths and levels
    response_lengths = ["short", "medium", "long"]
    levels = ["basic", "moderate", "advanced", "adaptive"]
    
    # Generate random response characteristics
    response_characteristics = {
        "response_length": random.choice(response_lengths),
        "technical_level": random.choice(levels),
        "empathy_level": random.choice(levels),
        "creativity_level": random.choice(levels)
    }
    
    # Generate a name and description using GPT-4
    traits_behavior = personality_to_behavior(traits)
    name_summary = generate_name_and_summary(traits, traits_behavior)
    
    return Personality(
        name=name_summary["name"],
        description=name_summary["summary"],
        traits=traits,
        communication_style=communication_style,
        response_characteristics=response_characteristics
    )