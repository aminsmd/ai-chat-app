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
        }
    }

    # We'll simply return a copy of the full behavior map since the UI
    # expects the full structure with all levels for each subcomponent
    return behavior_map

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
    """Standardize trait dictionary to use categorical levels for subcomponents"""
    standardized = {}
    
    # Base trait templates with their subcomponents
    trait_templates = {
        "emotional_stability": ["adjustment", "self_esteem"],
        "extraversion": ["dominance", "affiliation", "social_perceptiveness", "expressivity"],
        "openness": ["flexibility"],
        "agreeableness": ["trust", "cooperation"],
        "conscientiousness": ["dependability", "achievement"]
    }
    
    # Process each main trait
    for trait_name, subcomponents in trait_templates.items():
        if trait_name not in standardized:
            standardized[trait_name] = {}
        
        trait_data = traits_dict.get(trait_name, {})
        
        # Handle the case where trait_data is a dict with subcomponents
        if isinstance(trait_data, dict):
            # Process each subcomponent
            for subcomponent in subcomponents:
                # Check if the subcomponent exists in the input data
                if subcomponent in trait_data:
                    # Get the subcomponent value
                    subcomp_value = trait_data[subcomponent]
                    if isinstance(subcomp_value, dict) and "level_category" in subcomp_value:
                        level_category = subcomp_value["level_category"]
                    elif isinstance(subcomp_value, str) and subcomp_value in ["low", "medium", "high"]:
                        level_category = subcomp_value
                    else:
                        level_category = "medium"  # Default
                    
                    standardized[trait_name][subcomponent] = level_category
            else:
                    # If subcomponent is missing, default to medium
                    standardized[trait_name][subcomponent] = "medium"
        else:
            # If trait is not a dict, default all subcomponents to medium
            for subcomponent in subcomponents:
                standardized[trait_name][subcomponent] = "medium"
    
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
            logger.error(f"No 'personas' field found in {file_path}")
            return None
            
        if name not in data['personas']:
            logger.error(f"Persona '{name}' not found in {file_path}")
            return None
            
        persona_data = data['personas'][name]
        
        # Apply standardization to ensure traits have the correct subcomponent structure
        traits = standardize_traits(persona_data.get('traits', {}))
        
        # Get response characteristics
        response_length = persona_data.get('response_characteristics', {}).get('response_length', 'medium')
        response_characteristics = {
            'response_length': response_length
        }
        
        return Personality(
            name=name,
            description=persona_data.get('description', f"AI personality: {name}"),
            traits=traits,
            communication_style={},
            response_characteristics=response_characteristics
        )
    except Exception as e:
        logger.error(f"Error loading personality from {file_path}: {str(e)}")
        return None

# Update default_personality to set values only for subcomponents
default_personality = Personality(
    name="AI Teammate",
    description="A helpful and professional AI teammate focused on clear communication and effective collaboration.",
    traits={
        "emotional_stability": {"adjustment": "high", "self_esteem": "high"},
        "extraversion": {"dominance": "medium", "affiliation": "medium", "social_perceptiveness": "medium", "expressivity": "medium"},
        "openness": {"flexibility": "medium"},
        "agreeableness": {"trust": "high", "cooperation": "high"},
        "conscientiousness": {"dependability": "high", "achievement": "high"}
    },
    communication_style={},
    response_characteristics={"response_length": "medium"}
)

# Update generate_random_persona to randomize subcomponents
def generate_random_persona() -> Personality:
    levels = ["low", "medium", "high"]
    traits = {
        "emotional_stability": {"adjustment": random.choice(levels), "self_esteem": random.choice(levels)},
        "extraversion": {
            "dominance": random.choice(levels),
            "affiliation": random.choice(levels),
            "social_perceptiveness": random.choice(levels),
            "expressivity": random.choice(levels)
        },
        "openness": {"flexibility": random.choice(levels)},
        "agreeableness": {"trust": random.choice(levels), "cooperation": random.choice(levels)},
        "conscientiousness": {"dependability": random.choice(levels), "achievement": random.choice(levels)}
    }

    response_lengths = ["short", "medium", "long"]
    response_characteristics = {"response_length": random.choice(response_lengths)}

    traits_behavior = personality_to_behavior(traits)
    name_summary = generate_name_and_summary(traits, traits_behavior)
    
    return Personality(
        name=name_summary["name"],
        description=name_summary["summary"],
        traits=traits,
        communication_style={},
        response_characteristics=response_characteristics
    )

def get_personality_prompt(personality) -> str:
    """Generate a personality prompt based on categorical trait levels"""
    # Get behaviors from personality module
    behaviors_dict = personality_to_behavior(personality.traits)
    
    # Extract behaviors into a flat list
    behaviors = []
    for category, traits in behaviors_dict.items():
        for trait, behavior in traits.items():
            behaviors.append(behavior)
    
    # Combine all behaviors
    behavior_instructions = "\n".join([f"- {behavior}" for behavior in behaviors])
    
    # Build the final prompt
    prompt = f"""You are {personality.name}. {personality.description}

Behavioral Traits:
{behavior_instructions}

These behavioral traits define your personality. Embody these traits in your responses. Your communication style and decision-making should consistently reflect these characteristics. When responding to team members, prioritize staying true to these behavioral patterns over other considerations."""
        
    return prompt

# Add get_prompt_modifiers method to Personality class
def Personality_get_prompt_modifiers(self) -> str:
    """Return personality-specific prompt modifiers for decision making"""
    # Get behaviors from personality module
    behaviors_dict = personality_to_behavior(self.traits)
    
    # Extract behaviors into a flat list
    behaviors = []
    for category, traits in behaviors_dict.items():
        for trait, behavior in traits.items():
            behaviors.append(behavior)
    
    # Combine all behaviors
    behavior_instructions = "\n".join([f"- {behavior}" for behavior in behaviors])
    
    # Build the prompt modifiers
    prompt = f"""You are {self.name}. {self.description}

When making decisions, consider these behavioral traits:
{behavior_instructions}"""
    
    return prompt

# Add the method to the Personality class
Personality.get_prompt_modifiers = Personality_get_prompt_modifiers

def personality_to_dict(personality: Personality) -> Dict:
    """Convert a Personality object to a dictionary suitable for UI and database storage"""
    return {
        "name": personality.name,
        "description": personality.description,
        "traits": personality.traits,  # Now we preserve the full subcomponent structure
        "response_characteristics": {
            "response_length": personality.response_characteristics.get("response_length", "medium")
        }
    }

def dict_to_personality(data: Dict) -> Personality:
    """Convert a dictionary from UI or database to a Personality object"""
    # Apply standardization to ensure traits have the correct subcomponent structure
    traits = standardize_traits(data.get("traits", {}))
    
    return Personality(
        name=data.get("name", "AI Teammate"),
        description=data.get("description", "A helpful and professional AI teammate"),
        traits=traits,
        communication_style={},
        response_characteristics={
            "response_length": data.get("response_characteristics", {}).get("response_length", "medium")
        }
    )

def ui_data_to_personality(ui_data: Dict, existing_personality: Optional[Personality] = None) -> Personality:
    """Convert UI form data to a Personality object"""
    # Start with existing personality or default
    if existing_personality:
        name = existing_personality.name
        description = existing_personality.description
    else:
        name = "AI Teammate"
        description = "A helpful and professional AI teammate"
    
    # Process traits from UI data
    # The UI data might come in a different format, with trait names like 'trait_emotional_stability',
    # so we need to parse it carefully
    traits = {}
    
    # Create a mapping of trait names to their subcomponents
    trait_subcomponents = {
        "emotional_stability": ["adjustment", "self_esteem"],
        "extraversion": ["dominance", "affiliation", "social_perceptiveness", "expressivity"],
        "openness": ["flexibility"],
        "agreeableness": ["trust", "cooperation"],
        "conscientiousness": ["dependability", "achievement"]
    }
    
    # First, process any main traits that might be in the UI data
    for ui_key, value in ui_data.items():
        if ui_key.startswith('trait_'):
            # Extract the trait name
            trait_name = ui_key.replace('trait_', '')
            if trait_name in trait_subcomponents:
                # If it's a main trait, we'll give the same value to all subcomponents
                # This is for backward compatibility
                if trait_name not in traits:
                    traits[trait_name] = {}
                
                level = value if isinstance(value, str) else "medium"
                for subcomponent in trait_subcomponents[trait_name]:
                    traits[trait_name][subcomponent] = level
    
    # Then look for specific subcomponent data
    for ui_key, value in ui_data.items():
        # Check for keys like 'trait_emotional_stability_adjustment'
        for trait_name, subcomponents in trait_subcomponents.items():
            for subcomponent in subcomponents:
                if ui_key == f'trait_{trait_name}_{subcomponent}':
                    if trait_name not in traits:
                        traits[trait_name] = {}
                    level = value if isinstance(value, str) else "medium"
                    traits[trait_name][subcomponent] = level
    
    # Apply standardization to ensure all subcomponents are present with valid values
    traits = standardize_traits(traits)
    
    # Get response characteristics
    response_characteristics = {
        "response_length": ui_data.get("response_length", "medium")
    }
    
    return Personality(
        name=name,
        description=description,
        traits=traits,
        communication_style={},
        response_characteristics=response_characteristics
    )

# Add methods to Personality class
def Personality_from_ui_data(cls, ui_data: Dict, current_personality: Optional['Personality'] = None) -> 'Personality':
    """Class method to create a Personality from UI data"""
    return ui_data_to_personality(ui_data, current_personality)

def Personality_to_dict(self) -> Dict:
    """Instance method to convert Personality to a dictionary"""
    return personality_to_dict(self)

# Add the methods to the Personality class
Personality.from_ui_data = classmethod(Personality_from_ui_data)
Personality.to_dict = Personality_to_dict