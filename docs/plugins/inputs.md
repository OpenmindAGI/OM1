# Input Plugins

## Overview
Input plugins (sensors) are responsible for gathering data from various sources and converting it into a format that can be processed by the agent system.

## Available Input Plugins

### 1. ASRInput (Automatic Speech Recognition)
```python
class ASRInput(FuserInput[str]):
    """
    Handles real-time speech-to-text conversion.
    
    Configuration:
    {
        "type": "ASRInput"
    }
    
    Features:
    - Real-time audio processing
    - Message buffering
    - Configurable ASR service URL
    - Automatic speech detection
    
    Output Format:
    {
        "text": "transcribed speech content"
    }
    """
```

### 2. WalletEthereum
```python
class WalletEthereum(FuserInput[float]):
    """
    Monitors Ethereum wallet for transactions and balance changes.
    
    Configuration:
    {
        "type": "WalletEthereum"
    }
    
    Features:
    - Real-time balance monitoring
    - Transaction detection
    - ETH value tracking
    - Web3 integration
    
    Output Format:
    {
        "balance": "current_balance",
        "transaction": "latest_transaction_details"
    }
    """
```

### 3. FaceEmotionCapture
```python
class FaceEmotionCapture(FuserInput[str]):
    """
    Captures and analyzes facial emotions using webcam.
    
    Configuration:
    {
        "type": "FaceEmotionCapture"
    }
    
    Features:
    - Real-time emotion detection
    - DeepFace integration
    - Multiple face tracking
    - Emotion confidence scores
    
    Output Format:
    {
        "emotion": "detected_emotion",
        "confidence": "confidence_score"
    }
    """
```

## Development Guide

### Creating a New Input Plugin

1. **Basic Structure**:
```python
class CustomInput(FuserInput[DataType]):
    async def listen(self) -> AsyncIterator[DataType]:
        await self.start()
        while True:
            data = await self._poll()
            if data:
                yield data
            await asyncio.sleep(0.1)

    async def _raw_to_text(self, raw_input: DataType) -> Optional[str]:
        # Convert raw input to text format
        pass

    def formatted_latest_buffer(self) -> Optional[str]:
        # Format and return latest buffer contents
        pass
```

2. **Required Methods**:
   - `listen()`: Main input loop
   - `_raw_to_text()`: Convert raw input to text
   - `formatted_latest_buffer()`: Format buffer contents

3. **Best Practices**:
   - Use proper error handling
   - Implement rate limiting
   - Add comprehensive logging
   - Document configuration options
   - Follow async/await patterns

## Configuration Examples

```json
{
    "agent_inputs": [
        {
            "type": "ASRInput"
        },
        {
            "type": "FaceEmotionCapture"
        },
        {
            "type": "WalletEthereum"
        }
    ]
}
```

## Troubleshooting

Common issues and solutions for input plugins:
1. **Connection Issues**:
   - Check network connectivity
   - Verify service URLs
   - Confirm credentials

2. **Performance Issues**:
   - Adjust polling intervals
   - Check resource usage
   - Monitor buffer sizes

3. **Data Quality**:
   - Validate input formats
   - Check conversion logic
   - Monitor error rates 