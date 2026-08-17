# Optional CPU GGUF Runtime with llama.cpp

PenG supports an optional LLM runtime that loads a local GGUF file through
`llama-cpp-python`. This is useful for CPU-only machines or when you want to
avoid downloading Hugging Face checkpoints at runtime.

> **GGUF support is optional.** The default runtime remains
> `transformers` + `BitsAndBytes` and is the recommended path for CUDA/Google
> Colab T4. Switching to GGUF does not change any API contract; callers still
> use `app.services.llm.complete()`.

## When to use this runtime

- You want to run the LLM on a machine without NVIDIA GPU.
- You already have a compatible quantized GGUF file.
- You prefer a single local file instead of a Hugging Face cache directory.

## Installation

`llama-cpp-python` is **not** in `requirements.txt` or `requirements-colab.txt`
because its wheels are platform-sensitive. Install it separately after the main
requirements.

```bash
# Basic CPU build
pip install llama-cpp-python --no-cache-dir

# CPU with OpenBLAS (Linux/WSL2, faster on most machines)
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" \
  pip install llama-cpp-python --no-cache-dir

# macOS Metal (Apple Silicon)
CMAKE_ARGS="-DLLAMA_METAL=on" \
  pip install llama-cpp-python --no-cache-dir
```

On Windows without a compiler, use a pre-built wheel or run under WSL2. A
helper file `requirements-cpu.txt` lists all non-GPU dependencies plus
`llama-cpp-python` as the optional runtime package.

```bash
# Optional: install CPU dependencies + llama-cpp-python
pip install -r requirements-cpu.txt
```

## Obtaining a compatible GGUF

PenG's default chat prompts assume an instruction-tuned model that understands
a system/user/assistant chat format (ChatML/Qwen style). A good default match
for the project's prompts is **Qwen2.5-1.5B-Instruct** quantized to Q4_K_M or
Q5_K_M.

Example sources (verify license and provenance before use):

- Hugging Face `bartowski/Qwen2.5-1.5B-Instruct-GGUF`
- Hugging Face `QuantFactory/Qwen2.5-1.5B-Instruct-GGUF`

Download one `.gguf` file, place it in a `models/` directory at the repo root,
and do **not** commit model weights to git.

```bash
mkdir models
curl -L -o models/qwen2.5-1.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/bartowski/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/Qwen2.5-1.5B-Instruct-Q4_K_M.gguf"
```

> Model weights, GGUF quants, and upstream projects have their own licenses.
> PenG's MIT license applies only to its own source code. Always check the
> license of the model you download.

## Configuration

Add to `.env`:

```ini
LLM_RUNTIME=llama_cpp
LLM_GGUF_MODEL_PATH=models/qwen2.5-1.5b-instruct-q4_k_m.gguf
LLM_GGUF_CHAT_FORMAT=chatml
LLM_GGUF_N_THREADS=4
LLM_GGUF_N_CTX=4096
```

Relative paths resolve from the project root, like `upload_dir` and
`sqlite_path`. Absolute paths are kept as-is.

`LLM_GGUF_CHAT_FORMAT` is passed to `llama_cpp.Llama`. Common values:
`chatml`, `qwen`, `llama-2`, `gemma`. If the model fails with chat completion,
PenG falls back to a plain prompt string.

## Benchmark

Measure prompt latency and approximate tokens per second:

```bash
python scripts/benchmark_llm.py --runtime llama_cpp --runs 3 --warmup
```

## Limitations

- GGUF runtime is CPU-focused; GPU offloading is not configured by default.
- No model weights are downloaded automatically.
- `llm_model` is ignored when `LLM_RUNTIME=llama_cpp`; the GGUF path is used
  instead.
- If the GGUF file is missing or `llama-cpp-python` is not installed, the
  service logs an error and falls back to the deterministic fake completion,
  which is safe for tests and health checks.
