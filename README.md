# Specvalid

![text](docs/logo.png)

A tool for **specification-based test generation** using LLMs to create JUnit tests that violate postconditions, validated through dynamic invariant detection with Daikon.

---

## Experiments

### Setup

```bash
./experiments/setup.sh
```

### Run test generation and validation

```bash
# Using local models (e.g., Ollama)
./experiments/run-testgen.sh -m "L_Llama323Instruct_Q8" -p "General_V1"

# Using multiple models and prompts (output folder optional)
./experiments/run-testgen.sh -m "model1,model2" -p "General_V1,GeneralV2" -o output/
```
