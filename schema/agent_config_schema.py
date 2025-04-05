# schema/agent_config_schema.py

agent_config_schema = {
    "type": "object",
    "properties": {
        "hertz": {"type": "number"},
        "name": {"type": "string"},
        "api_key": {"type": "string"},
        "system_prompt_base": {"type": "string"},
        "system_governance": {"type": "string"},
        "system_prompt_examples": {"type": "string"},
        "agent_inputs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"type": {"type": "string"}},
                "required": ["type"]
            }
        },
        "simulators": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string"},
                    "config": {"type": "object"}
                },
                "required": ["type"]
            }
        },
        "cortex_llm": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "config": {
                    "type": "object",
                    "properties": {
                        "agent_name": {"type": "string"},
                        "history_length": {"type": "integer"},
                        "base_url": {"type": "string"},
                        "api_key": {"type": "string"}
                    },
                    "additionalProperties": True
                }
            },
            "required": ["type"]
        },
        "agent_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "llm_label": {"type": "string"},
                    "implementation": {"type": "string"},
                    "connector": {"type": "string"}
                },
                "required": ["name", "implementation", "connector"]
            }
        }
    },
    "required": ["hertz", "name", "api_key", "agent_inputs", "cortex_llm", "simulators", "agent_actions"],
    "additionalProperties": True
}
