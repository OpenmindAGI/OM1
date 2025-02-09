# Output Plugins (Action Connectors)

## Overview
Output plugins (action connectors) handle the execution of actions in response to agent decisions. They translate agent commands into actual system actions.

## Available Output Plugins

### 1. TTS (Text-to-Speech)
```python
class TTSConnector(ActionConnector[SpeakInput]):
    """
    Converts text to speech output.
    
    Configuration:
    {
        "name": "speak",
        "implementation": "passthrough",
        "connector": "tts"
    }
    
    Features:
    - Audio stream management
    - Multiple voice support
    - Real-time synthesis
    - Volume control
    
    Input Format:
    {
        "sentence": "text to speak",
        "voice": "voice_id"  # optional
    }
    """
```

### 2. ROS2 Face Expression
```python
class FaceRos2Connector(ActionConnector[FaceInput]):
    """
    Controls robot facial expressions via ROS2.
    
    Configuration:
    {
        "name": "face",
        "implementation": "passthrough",
        "connector": "ros2"
    }
    
    Features:
    - Multiple expression support
    - ROS2 integration
    - Real-time control
    
    Input Format:
    {
        "action": "smile|frown|cry|think|joy"
    }
    """
```

### 3. Movement Control
```python
class MoveRos2Connector(ActionConnector[MoveInput]):
    """
    Controls physical movement through ROS2.
    
    Configuration:
    {
        "name": "move",
        "implementation": "passthrough",
        "connector": "ros2"
    }
    
    Features:
    - Multiple movement types
    - Safety constraints
    - Position control
    
    Input Format:
    {
        "action": "stand_still|sit|dance|shake_paw|walk|run"
    }
    """
```

### 4. Twitter API
```python
class TweetAPIConnector(ActionConnector[TweetInput]):
    """
    Posts content to Twitter via the Twitter API.
    
    Configuration:
    {
        "name": "tweet",
        "implementation": "passthrough",
        "connector": "twitterAPI"
    }
    
    Features:
    - Twitter API v2 integration
    - Rate limiting handling
    - Tweet status verification
    - URL generation for posted tweets
    
    Input Format:
    {
        "tweet": "content to be tweeted"  # Must be <= 280 characters
    }
    
    Required Environment Variables:
    - TWITTER_API_KEY
    - TWITTER_API_SECRET
    - TWITTER_ACCESS_TOKEN
    - TWITTER_ACCESS_TOKEN_SECRET
    - TWITTER_BEARER_TOKEN
    """
```

## Development Guide

### Creating a New Output Plugin

1. **Basic Structure**:
```python
class CustomConnector(ActionConnector[OutputType]):
    async def connect(self, output_interface: OutputType) -> None:
        try:
            # Process output_interface and send to target system
            await self._send_output(output_interface)
        except Exception as e:
            logging.error(f"Output error: {str(e)}")
            raise
```

2. **Required Methods**:
   - `connect()`: Main output handling
   - `tick()`: Optional periodic updates

3. **Best Practices**:
   - Implement proper error handling
   - Add rate limiting where needed
   - Use comprehensive logging
   - Document required credentials
   - Follow async patterns

## Configuration Examples

```json
{
    "agent_actions": [
        {
            "name": "speak",
            "implementation": "passthrough",
            "connector": "tts"
        },
        {
            "name": "face",
            "implementation": "passthrough",
            "connector": "ros2"
        },
        {
            "name": "move",
            "implementation": "passthrough",
            "connector": "ros2"
        }
    ]
}
```

## Troubleshooting

Common issues and solutions for output plugins:
1. **Connection Issues**:
   - Check system connectivity
   - Verify service status
   - Confirm permissions

2. **Performance Issues**:
   - Monitor response times
   - Check resource usage
   - Verify rate limits

3. **Integration Issues**:
   - Validate interface formats
   - Check system compatibility
   - Monitor error logs 