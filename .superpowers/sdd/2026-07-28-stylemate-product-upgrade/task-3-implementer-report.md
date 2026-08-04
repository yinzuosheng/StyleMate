# Task 3 Implementer Report

## Scope

Implemented the wardrobe onboarding workflow from recorded base
`836735dae079d1c1fc8484967b5765b1bf7cec69` in the assigned linked worktree.
The change adds typed vision and image-storage boundaries, upload validation,
confirmed garment persistence, and a draft-first onboarding Skill.

## RED evidence

- `C:\Users\Administrator\.conda\envs\LLM\python.exe -m pytest tests/services/test_wardrobe_service.py tests/skills/test_wardrobe_onboarding.py -v`
- Result before production modules: two collection errors, both expected:
  `ModuleNotFoundError: No module named 'services.wardrobe_service'`.
- A later narrow storage test for an RGBA source saved as JPEG failed as expected
  with `OSError: cannot write mode RGBA as JPEG`; the encoder conversion was
  then added.

## GREEN and regression evidence

- Focused Task 3 suite: 16 passed (`services`, `storage`, `skills`, and
  no-network `gateways` tests).
- Full suite: 36 passed in 2.35s.
- Ruff changed paths: `All checks passed!`.
- `compileall gateways services storage skills`: completed successfully.
- `git diff --check`: no output.

## Safety coverage

- Exact MIME allowlist, non-empty bytes, and 8 MB ceiling.
- SHA-256 duplicate detection is owner-scoped; confirmation stores the image
  before persisting the garment.
- Local files use hash-derived owner directories plus UUID filenames, root
  containment checks, and Pillow decode/re-encode metadata stripping.
- Vision calls use a 30-second configured timeout, one retry, typed unavailable
  and response errors, and manual editable fallback. The final provider test
  uses an injected recording fake; the no-key test explicitly clears the
  ambient key before calling the adapter.
- Trace summaries are fixed safe text and contain no key, prompt, data URL, or
  raw image bytes.

## Concern

The DashScope adapter is intentionally tested through an injected client only;
live provider payload compatibility remains outside this offline Task 3 scope.
An initial local test run resolved an ambient `DASHSCOPE_API_KEY` before the
test was isolated; it was immediately changed to clear that environment value,
and no subsequent verification invokes the provider.

## Review Fix Round

### RED evidence

- An SDK-signature fake that accepts `request_timeout` and rejects unsupported
  keywords failed with `TypeError: ... unexpected keyword argument 'timeout'`.
- The cross-format privacy test found that a PNG saved through the old store
  retained `icc_profile` in `Image.info`.
- A failing repository left the just-created `memory://` entry in session image
  state after `save_confirmed` raised.
- Extra provider keys, blank required text, and confidence `1.1` all passed
  through the old gateway; an invalid direct Skill payload was accepted on its
  first call instead of retrying.

### GREEN evidence

- DashScope now receives `request_timeout=settings.model_timeout_seconds`; the
  signature-compatible boundary fake passes.
- A fresh Pillow image is rebuilt from pixels before save. JPEG, PNG, and WebP
  tests each confirm EXIF, ICC, XMP, and comment markers are absent.
- Repository errors cause the newly saved image to be deleted before the
  original error is re-raised.
- `VisionGarmentPayload` strictly requires exactly `name`, `category`,
  `primary_color`, `material`, `seasons`, `styles`, and `confidence`; extras,
  blank required text, and out-of-range confidence become `VisionResponseError`.
  The Skill independently validates gateway payloads, retries once, then
  returns its editable manual-entry fallback.
- Focused Task 3 verification: 24 passed. Full regression: 44 passed in
  1.86s. Ruff changed paths: `All checks passed!`; `compileall` succeeded;
  `git diff --check` produced no diff errors.
