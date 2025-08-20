# Experiments

To run the experiments setup, you need Python, pip, and megatools (if you don't want to download anything manually).

## Setup

```bash
experiments/setup.sh
```

This creates the virtual environment, installs requirements, downloads subjects under analysis, SpecFuzzer result specifications, and our version of Daikon.

## Run Test Generation and Validation

To run experiments locally, you need Ollama and pull the model you want to use (e.g., llama3.2:3b-instruct-q8_0).

```bash
ollama pull llama3.2:3b-instruct-q8_0
```

Then run the experiments, specifying models and prompts:

```bash
experiments/run-testgen.sh -m "L_Llama323Instruct_Q8" -p "General_V1,GeneralV2"
```
