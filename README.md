
![OM_Banner_X2 (1)](https://github.com/user-attachments/assets/853153b7-351a-433d-9e1a-d257b781f93c)

<p align="center">  <a href="https://arxiv.org/abs/2412.18588">Technical Paper</a> |  <a href="https://docs.openmind.org/examples/conversation">Documentation</a> |  <a href="https://x.com/openmind_agi">X</a> </p>

**Openmind's OM1 is a modular AI runtime for agents and robots with multimodal capabilities including movement and speech.**

OM1 enables the creation and deployment of AI agents across both digital and physical environments. This means you can design a single AI agent and deploy it not only in the cloud but also on a variety of physical robot platforms, including Quadrupeds, with future support for TurtleBot 3 and Humanoids. This flexibility allows for seamless integration and testing of AI capabilities across different domains, from simulation to real-world applications.

An AI agent built on OM1 is capable of ingesting data from multiple sources (the Web, X/Twitter, cameras and LIDAR) and performing various actions like tweeting, exploring your house, shaking your hand or talking to you. With OM1, you can talk to OpenAI's gpt-4o and literally shake hands with it.

## Capabilities of OM1

* **Modular Architecture**: Designed with Python for simplicity and seamless integration.
* **Data Input**: Easily handles new data.
* **Hardware Support via Plugins**: Supports new hardware through plugins for API endpoints and specific robot hardware connections to `ROS2`, `Zenoh`, and `CycloneDDS`.
* **Web-Based Debugging Display**: Monitor the system in action with WebSim (available at http://localhost:8000/) for easy debugging through visuals.
* **Pre-configured Endpoints**: Supports Voice-to-Speech, OpenAI’s `gpt-4o`, DeepSeek, and multiple Visual Language Models (VLMs) with pre-configured endpoints for each service.

## Architecture Overview
  ![Artboard 1@4x 1 (1)](https://github.com/user-attachments/assets/14e9b916-4df7-4700-9336-2983c85be311)

## Hands-On with OM1: 'Hello World' program

In this example program, _Hello World_, let's create an AI agent named Spot. This program enables the '_Spot_' agent to access your webcam to capture and label objects. These label captions are then sent to `OpenAI 4o`, a large language model (LLM) which returns commands like `movement`, `speech` and `face`. These commands are displayed on WebSim along with basic timing and other debugging information.

1. Clone the repo.

```bash clone repo
git clone https://github.com/OpenmindAGI/OM1.git
cd OM1
git submodule update --init
uv venv
```

_Note 1:_ You will need the Rust Python package manager `uv`.
* To install on Mac, use `brew install uv`.
* On Linux, use `curl -LsSf https://astral.sh/uv/install.sh | sh`.

_Note 2:_ If your system doesn't have `portaudio`, you should install it to run the program.
* To install on Mac, use `brew install portaudio`
* On Linux, use `sudo apt-get install libasound-dev`
Similarily, you may need `ffmpeg`.

2. Set the configuration variables. \
Locate the `config` folder and add your Openmind API key in `/config/spot.json`. If you do not already have one, you can obtain a free access key at https://portal.openmind.org/.  

_Note:_ Using the placeholder key **openmind-free** will generate errors.

```bash set api key
# /config/spot.json
...
"api_key": "2f1cf005af........."
...
```

3. Run the program with `Spot`, a `Hello World` agent we created.

```bash run spot
uv run src/run.py spot
```

Please wait for a short while before real time information is displayed. 

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
4. Go to [http://localhost:8000](http://localhost:8000) to see real time logs along with 
 the input and output in the terminal. \
For easy debugging, add `--debug` to see additional logging information.

Congratulations!, you just got started with OM1 and can now explore its capabilities.

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
