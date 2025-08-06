#!/bin/bash

cleanup() {
    echo "Stopping Ollama model..."
    ollama stop gemma3:1b
    ollama stop mistral:7b-instruct-q4_K_M
}

trap cleanup EXIT INT

export OPENAI_API_KEY=
export API_KEY_HUGGINGFACE=
export GOOGLE_API_KEY="aa"

export MAX_COMPILE_ATTEMPTS=2

source .venv/bin/activate

java_class_src=/home/agustin/university/llm-based-assertion-confirmation/GAssert/subjects/QueueAr_makeEmpty/src/main/java/DataStructures/QueueAr.java
java_test_suite=/home/agustin/university/llm-based-assertion-confirmation/GAssert/subjects/QueueAr_makeEmpty/src/test/java/testers/QueueArTester0.java
java_test_driver=/home/agustin/university/llm-based-assertion-confirmation/GAssert/subjects/QueueAr_makeEmpty/src/test/java/testers/QueueArTesterDriver.java
assertions_file=/home/agustin/university/llm-based-assertion-confirmation/specfuzzer-subject-results/QueueAr_makeEmpty/output/QueueAr-makeEmpty-specfuzzer-1-buckets.assertions
method=makeEmpty
models="L_Mistral7B03Instruct_Q4,L_Gemma31"
prompts="General_V1"

echo "> Running specvalid"
specvalid testgen "$java_class_src" "$java_test_suite" "$java_test_driver" "$assertions_file" "$method" -m "$models" -p "$prompts"
