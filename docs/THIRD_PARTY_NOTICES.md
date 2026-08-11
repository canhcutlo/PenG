# PenG Third-Party Notices

This is a conservative, point-in-time license audit for the components named
by PenG's requirements, model configuration, and static frontend. It is not
legal advice and is not a complete transitive-dependency inventory.

Audit date: 2026-08-11

`[MANUAL VERIFY]` means that the available package metadata or upstream page
does not establish a license clearly enough for redistribution. Do not treat a
license of a wrapper, framework, or base model as the license of a downloaded
model or external executable.

| Component | Purpose | Declared/upstream license | Source | Redistribution caveat |
|---|---|---|---|---|
| Qwen2.5-3B-Instruct (`Qwen/Qwen2.5-3B-Instruct`) | Default local instruction LLM | **Qwen Research License** is the license label shown on the Hugging Face model card; exact applicable terms must be reviewed. **[MANUAL VERIFY]** | [Hugging Face model card](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) | Do not label this model Apache-2.0 based on Transformers or other Qwen repositories. Review the model repository license/terms, permitted use, notices, and any gated or third-party asset terms before redistributing weights or a service containing them. |
| `keepitreal/vietnamese-sbert` | Vietnamese sentence embeddings | No license is displayed on the accessible Hugging Face model card. **[MANUAL VERIFY]** | [Hugging Face model card](https://huggingface.co/keepitreal/vietnamese-sbert) | Obtain a clear license or permission from the model author before redistributing weights. The Apache-2.0 license of `sentence-transformers` does not license this model. Also review the underlying pretrained model and training-data provenance. |
| faster-whisper | Speech-to-text wrapper/runtime | MIT (upstream repository LICENSE; installed metadata: 1.2.1) | [Upstream repository](https://github.com/SYSTRAN/faster-whisper) | Preserve the MIT notice. Downloaded Whisper model weights and runtime dependencies have separate terms; audit those artifacts independently. CUDA, cuDNN, FFmpeg, and other system components are not covered by this row. |
| Surya OCR (optional `surya-ocr`) | Optional OCR and layout recognition | Upstream license was not established from the accessible repository metadata. **[MANUAL VERIFY]** | [Upstream repository](https://github.com/VikParuchuri/surya) | Optional and not installed in the audited Python 3.14 environment. Do not redistribute Surya code, weights, or generated bundle until the version-specific license and model-weight terms are confirmed. |
| pytesseract | Python wrapper for Tesseract OCR | Apache-2.0 (installed metadata: 0.3.13; upstream LICENSE) | [Upstream repository](https://github.com/madmaze/pytesseract) | The wrapper license does not cover the Tesseract executable or language data. Preserve Apache notices for the wrapper and audit the separately installed Tesseract distribution. Tesseract was not found as an executable in this environment. |
| Tesseract OCR | External OCR engine used by pytesseract | Apache-2.0 for the Tesseract project, subject to its own distribution contents | [Upstream repository](https://github.com/tesseract-ocr/tesseract) | Package/installer builds may include separate language data and libraries with their own notices. Audit the exact binary and traineddata files shipped with a deployment; do not assume the wrapper's license covers them. |
| PyMuPDF (`pymupdf`) | PDF text extraction and rendering | Dual licensed: GNU AGPL-3.0 or Artifex Commercial License (installed metadata: 1.28.0) | [PyMuPDF licensing](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright) | Choose and comply with one licensing route. AGPL obligations can affect distribution and network-deployed modifications; a commercial license may be required for incompatible proprietary use. Review bundled dependencies and the exact version before redistribution. |
| MoviePy | Video editing and keyframe extraction | MIT (installed metadata: 2.2.1; upstream repository) | [Upstream repository](https://github.com/Zulko/moviepy) | Preserve the MIT notice. MoviePy invokes or bundles integrations such as FFmpeg/ImageMagick depending on use; those components and codecs have separate licenses and patent considerations. |
| PySceneDetect (`scenedetect`) | Video scene/shot detection | BSD-3-Clause (installed metadata: 0.7.1; upstream LICENSE) | [Upstream repository](https://github.com/Breakthrough/PySceneDetect) | Preserve BSD notices and do not imply endorsement. OpenCV and other dependencies bundled or installed alongside it require their own notices. |
| LightRAG (`lightrag-hku`) | Retrieval-augmented generation pipeline | MIT (installed metadata: 1.5.5; upstream repository) | [Upstream repository](https://github.com/HKUDS/LightRAG) | Preserve MIT notices. LightRAG's dependencies, vector storage, embedding models, and generated model outputs are separate items. This row does not cover deprecated or optional integrations that are not installed/used by PenG. |
| sentence-transformers | Embedding model loading and encoding | Apache-2.0 (installed metadata: 5.6.1; upstream repository) | [Upstream repository](https://github.com/UKPLab/sentence-transformers) | Preserve Apache notices and audit its transitive dependencies. This license covers the library, not downloaded model weights such as `keepitreal/vietnamese-sbert`. |
| Transformers | Transformer model loading and generation | Apache-2.0 (installed metadata: 5.14.1; upstream repository) | [Upstream repository](https://github.com/huggingface/transformers) | Preserve Apache notices. Model repositories, tokenizers, weights, and optional native backends can have separate terms. |
| BitsAndBytes | 4-bit quantization support for Colab/GPU | Upstream project is commonly published under MIT, but the package was not installed in this environment and the exact version-specific notice was not verified. **[MANUAL VERIFY]** | [Upstream repository](https://github.com/bitsandbytes-foundation/bitsandbytes) | Verify the exact installed/released version, license file, compiled binaries, and CUDA dependencies before shipping a Colab image or other redistribution. |
| FastAPI | HTTP API framework | MIT (installed metadata: 0.140.0; upstream repository) | [Upstream repository](https://github.com/fastapi/fastapi) | Preserve MIT notices. Starlette, Pydantic, Uvicorn, and other dependencies remain separate notices. |
| Markmap CDN (`markmap-autoloader@0.17.0`) | Browser rendering of Markdown mindmaps | Markmap upstream is MIT; the exact CDN artifact and bundled dependency notices were not independently enumerated. **[MANUAL VERIFY]** | [CDN reference in `static/index.html`](../static/index.html), [Markmap repository](https://github.com/markmap/markmap) | The page loads a remote, version-pinned CDN script rather than the local `markmap-lib` package entry. Review the exact `markmap-autoloader@0.17.0` package contents, transitive notices, CDN integrity/version policy, and network-delivery implications before bundling or redistributing it. |

## Audit Evidence

- Python requirements were read from `requirements.txt` and
  `requirements-colab.txt`; the frontend dependency declaration was read from
  `package.json`.
- Installed metadata was checked with `python -m pip show` on Python 3.14.2.
  Installed versions are included only where they were observed locally and
  should not be read as version pins unless the repository pins them.
- Optional Surya and BitsAndBytes were not installed locally. Tesseract was not
  available as a system executable locally.
- The model-card license fields are intentionally reported as observed. A
  missing or non-standard field is not converted into an SPDX assertion.

## Manual Verification Checklist

Before publishing a binary, container, hosted service with redistributed
weights, or a bundled frontend, verify:

- The exact Qwen model license and current Qwen terms for the intended use.
- A written license for `keepitreal/vietnamese-sbert`, its underlying model,
  and any redistributed weights.
- The exact Surya release and model-weight terms if the optional OCR path is
  enabled.
- The exact BitsAndBytes release and licenses for its compiled CUDA artifacts.
- Tesseract executable, language-data, FFmpeg, OpenCV, and other system/media
  artifacts included in the deployment.
- The complete dependency and notice set for the exact Markmap CDN artifact,
  or vendor a reviewed, integrity-pinned copy instead.
