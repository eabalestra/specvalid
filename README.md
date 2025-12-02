<!-- markdownlint-disable -->
<div align="center">
    <img src="docs/icon.png" alt="specvalid-logo" width="200" height="200"/>
</div>

<p align="center">
    <strong>
    A tool for specification-based test generation using LLMs to create JUnit tests that violate postconditions, validated through dynamic invariant detection with Daikon.
    </strong>
</p>

<p align="center">
    <a href="https://github.com/eabalestra/specvalid/stargazers"><img src="https://img.shields.io/github/stars/eabalestra/specvalid?style=social" alt="GitHub stars"/></a>
    <a href="https://github.com/eabalestra/specvalid/blob/main/LICENSE"><img src="https://img.shields.io/github/license/eabalestra/specvalid" alt="License"/></a>
    <!-- <a href="https://github.github.io/spec-kit/"><img src="https://img.shields.io/badge/docs-GitHub_Pages-blue" alt="Documentation"/></a> -->
</p>

<!-- markdownlint-enable -->

---

## Table of Contents

- [Experiments](#experiments)
- [License](#license)

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

## License

This project is licensed under the terms of the MIT open source license. Please refer to the [LICENSE](./LICENSE) file for the full terms.
