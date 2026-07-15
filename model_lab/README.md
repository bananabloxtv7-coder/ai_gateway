# Model Capability Lab

The Model Capability Lab tests specific AI Gateway routes (`provider::model`) for protocol compatibility, tool-calling abilities, and streaming behaviors.

---

## 1. Architecture & Security
- **Strictly Offline Default:** Runs via pure Python tests against `MockTransport` internally to ensure determinism and zero network calls by default.
- **Strictly Offline Output:** Validates explicit outputs without ever logging or leaking `YOUSSEF_API_KEY`.
- **Append-only Results:** Safe to interrupt and resume using `jsonl`. 
- **Security Redaction:** The client automatically intercepts HTTP Authorization headers and raw exceptions to strip key secrets (e.g. `sk-...` or `YOUSSEF_API_KEY`) and replaces them with `[REDACTED]`.

---

## 2. Safe Environment Setup

Configure the workspace using environment variables:

```bash
export YOUSSEF_BASE_URL="http://localhost:8000"
export YOUSSEF_API_KEY="your-secret-gateway-key"
```

---

## 3. Provider::Model Separation

Every route must follow the format `<provider>::<model>`. 
- `provider` identifies the upstream host or provider (e.g. `openai`, `anthropic`, `cohere`).
- `model` is the identifier resolved by the Gateway.
No implicit fallback is permitted; route mismatch or missing routing headers will result in a failed probe.

---

## 4. CLI Examples

### Discover routes:
```bash
python -m model_lab.cli discover
```

### Dry-run Probe:
Check routes and probes selected without sending requests:
```bash
python -m model_lab.cli probe --routes-file model_lab/routes/phase1.example.json --suite protocol --dry-run
```

### Live Probe:
Probe routes using the `protocol` suite:
```bash
python -m model_lab.cli probe --routes-file model_lab/routes/phase1.example.json --suite protocol --concurrency 4 --repetitions 3
```

### Resume Probe:
Resume a previously interrupted execution without repeating successfully completed attempts:
```bash
python -m model_lab.cli probe --routes-file model_lab/routes/phase1.example.json --suite tool-calling --resume
```

### Force Run Probe:
Ignore completed attempts and run everything from scratch:
```bash
python -m model_lab.cli probe --routes-file model_lab/routes/phase1.example.json --suite tool-calling --force
```

### Aggregate capabilities:
```bash
python -m model_lab.cli aggregate --input model_lab/results/runs.jsonl --output model_lab/results/registry.json
```

---

## 5. Result Schema (AttemptRecord)

Each attempt logged to `runs.jsonl` contains the following fields:

- `run_id`: Uniquely generated UUID for the test runner session.
- `route_id`: The route ID being tested (e.g. `openai::gpt-4o`).
- `probe_id`: The probe name (e.g. `plain_chat`, `single_tool_call`).
- `attempt`: Sequence number (e.g. 1, 2, 3).
- `started_at`/`finished_at`: ISO-8601 timestamps.
- `status`: Result of evaluation (`passed`, `failed`, `error`).
- `failure_type`: Detailed failure classification (e.g., `route_identity_mismatch`, `missing_route_header`, `unexpected_tool_call`, `loop_termination_failure`).
- `failure_message`: String details of failure (redacted of secrets).
- `http_status`: Upstream response status code.
- `stream`: Boolean indicating if request used streaming.
- `request_id`: Extracted `X-Youssef-Request-Id`.
- `requested_route`: Extracted `X-Youssef-Requested-Model`.
- `resolved_route`: Extracted `X-Youssef-Resolved-Route`.
- `route_identity_matched`: Boolean matching identity.
- `valid_openai_shape`: Boolean confirming response structure matches OpenAI specifications.
- `timing`: Object recording `first_byte_ms` and `total_ms`.
- `tool_call_observations`: Key observations (e.g., `parallel_tools`, `sequential_fallback`).

---

## 6. Classifications

Routes aggregated in `registry.json` are classified as:
- **`agent-ready`**: Passed all protocol tests (`plain_chat`, `system_message`, `route_identity`) and basic tool-calling tests (`single_tool_call`, `streaming_tool_call`) with zero failure rate.
- **`tool-capable`**: Route supports at least single tool calls (`single_tool_call`) but did not qualify for `agent-ready`.
- **`text-only-qualified`**: Route supports standard non-tool-calling messages (`plain_chat`, `system_message`, or `route_identity`) but lacks tool-calling capability.
- **`unstable`**: Route possesses qualifications but has a failure rate greater than 0% (some attempts failed).
- **`incompatible`**: Route failed all tests or yielded consistent HTTP/gateway errors.
- **`untested`**: No runs have been completed yet.

---

## 7. Resume Behavior

The runner achieves duplicate-free resumption by reading existing runs from the append-only `runs.jsonl` output path. Completed attempts are identified by a stable composite key:
`{route_id}::{probe_id}::{attempt}`
Unless the `--force` flag is set, any attempt matching a key in this completed set is skipped immediately.

---

## 8. Adding Probes

To add a new capability probe:
1. Create a file in `model_lab/probes/<probe_name>.py`.
2. Inherit from `BaseProbe`.
3. Override:
   - `probe_id` property.
   - `async def run(self, route_id: str, client: GatewayClient) -> ProbeResult`.
   - `def evaluate(self, result: ProbeResult) -> dict` (optional, for custom checks).
4. Register the new probe in `model_lab/probes/__init__.py`.

---

## 9. Adding Routes

Routes are registered using JSON files under `model_lab/routes/`. Create/edit files with format:
```json
{
  "routes": [
    "provider::model"
  ]
}
```

---

## 10. Limitations
- Multi-turn tool calling simulations assume mock tool execution environments.
- High concurrency environments are constrained by upstream provider rate limits.
