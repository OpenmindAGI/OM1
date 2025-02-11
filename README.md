
![OM_Banner_X2 (1)](https://github.com/user-attachments/assets/853153b7-351a-433d-9e1a-d257b781f93c)

<p align="center">  <a href="https://arxiv.org/abs/2412.18588">Technical Paper</a> |  <a href="https://docs.openmind.org/examples/conversation">Documentation</a> |  <a href="https://x.com/openmind_agi">X</a> </p>

**Openmind's OM1 is a modular AI runtime for agents and robots with multimodal capabilities including movement and speech.**

OM1 enables the creation and deployment of AI agents across both digital and physical environments. This means you can design a single AI agent and deploy it not only in the cloud but also on a variety of physical robot platforms, including Quadrupeds, with future support for TurtleBot 3 and Humanoids. This flexibility allows for seamless integration and testing of AI capabilities across different domains, from simulation to real-world applications.

For example, an AI agent built on OM1 can ingest data from multiple sources (the web, X/Twitter, cameras, and LIDAR) and can then Tweet and explore your house, shake your hand, or talk to you. In another example, with OM1, you can talk with OpenAI's `gpt-4o` and literally shake hands with it.

## Capabilities of OM1

* Simple, modular architecture
* All python 
* Easy to add new data inputs
* Easy to support new hardware via plugins for API endpoints and specific robot hardware
* Can be connected to `ROS2`, `Zenoh`, and `CycloneDDS`
* Includes a web-based debug display to watch the system work (`WebSim` at http://localhost:8000)
* Preconfigured endpoints for Text-To-Speech (TTS), Speech-To-Text (ASR), OpenAI's `gpt-4o`, DeepSeek, and multiple VLMs

## Architecture Overview
  ![Artboard 1@4x 1 (1)](https://github.com/user-attachments/assets/14e9b916-4df7-4700-9336-2983c85be311)

## Hello World

The `Spot` agent uses your webcam to label objects and sends those captions to `OpenAI 4o`. The LLM returns `movement`, `speech`, and `face` commands, which are displayed in `WebSim`. `WebSim` also shows basic timing and other debug information.

1. Clone the repo

```bash clone repo
git clone https://github.com/OpenmindAGI/OM1.git
cd OM1
git submodule update --init
uv venv
```

Note: If you don't have the Rust python package manager `uv`, please install it via `brew install uv` (for Mac) and `curl -LsSf https://astral.sh/uv/install.sh | sh` for Linux.

Note: If your system doesn't have `portaudio`, you can install it via `brew install portaudio` (Mac) or `sudo apt-get install libasound-dev` (Linux).

2. Set configuration variables

Add your Openmind API key in `/config/spot.json`. You can obtain a free access key at https://portal.openmind.org/. If you use the placeholder key, `openmind-free`, you may be rate limited.

```bash set api key
# /config/spot.json
...
"api_key": "openmind_om1_pat_2f1cf005af........."
...
```

3. Run Spot, a `Hello World` agent

```bash run spot
uv run src/run.py spot
```

After a short delay, you can see real time inputs and outputs in the web debug page at http://localhost:8000 and logging information in the terminal:

```bash
INFO:root:SendThisToROS2: {'move': 'dance'}
INFO:root:SendThisToROS2: {'speak': "Hello, it's so nice to see you! Let's dance together!"}
INFO:root:SendThisToROS2: {'face': 'joy'}
INFO:root:VLM_COCO_Local: You see a person in front of you.
INFO:httpx:HTTP Request: POST https://api.openmind.org/api/core/openai/chat/completions "HTTP/1.1 200 OK"
INFO:root:Inputs and LLM Outputs: {
	'current_action': 'wag tail', 
	'last_speech': "Hello, new friend! I'm so happy to see you!", 
	'current_emotion': 'joy', 
	'system_latency': {
		'fuse_time': 0.2420651912689209, 
		'llm_start': 0.24208617210388184, 
		'processing': 1.4561660289764404, 
		'complete': 1.6982522010803223}, 
	'inputs': [{
		'input_type': 'VLM_COCO_Local', 
		'timestamp': 0.0, 
		'input': 'You see a person in front of you.'}]
	}
```

Success! You have now used OM1 to run your first agent.

Add `--debug` to see more logging information.

## Detailed Documentation

More detailed documentation can be accessed at [docs.openmind.org](https://docs.openmind.org/introduction) and in this repo.

Highlights:

- [Core Architecture and Runtime Flow](./docs/development//architecture.mdx)
- [Quick Start](./docs/quick_start.mdx)
- [Developer Guide](./docs/development/guide.mdx)
- [Example 1 - Using DeepSeek or Gemini as the Core LLM](./docs/examples/llm_models.mdx)
- [Example 2 - Using Cloud Endpoints for Voice Inputs and Text to Speech](./docs/examples/conversation.mdx)
- [Example 3 - An Interactive Smart Toy](./docs/examples/smart_toy.mdx)
- [Robotics - Unitree Dog](./docs/robotics/unitree_robotics.mdx)
- [Robotics - Unitree Dog with Wallet](./docs/robotics/coinbase_hackathon.mdx)

## Contributing

To contribute to this project, follow these steps:

1. **Fork the repository**: Go to the project's GitHub page and click the "Fork" button in the top-right corner. This will create a copy of the project in your own GitHub account.
2. **Create a feature branch**: In your forked repository, create a new branch for your changes. This branch should be named something like `feature/your-feature-name` or `fix/your-fix-name`. This helps to keep your changes organized and makes it easier to manage multiple contributions.
3. **Make your changes**: Make the necessary changes to the code in your feature branch. Ensure that your changes are well-documented and follow OM1's coding style.
4. **Submit a pull request**: Once you've made your changes, submit a pull request to the original repository. This will notify the maintainers of your changes and allow them to review and discuss your contribution.

## License

This project is licensed under the terms of the MIT License, which is a permissive free software license that allows users to freely use, modify, and distribute the software. The MIT License is a widely used and well-established license that is known for its simplicity and flexibility. By using the MIT License, this project aims to encourage collaboration, modification, and distribution of the software.
