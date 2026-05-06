# Security Exception Register

Security exceptions represent confirmed risks that are **accepted** or **deferred** and **cannot be remediated immediately**. Each exception is tracked to closure with a defined resolution path.

---

## S-RTCM-FEISHU-TOKEN-001

**Risk ID**: S-RTCM-FEISHU-TOKEN-001
**Severity**: HIGH (live bot token in untracked operational data)
**Status**: OPEN — DEFERRED_BY_OPERATOR

### Description

A live Feishu bot token (`t-gxxxxx` format) is stored in an untracked file:

```
.deerflow/rtcm/feishu/token_cache.json
```

The token is actively used by the RTCM operational session (not by any tracked Python runtime). The token cannot be rotated by the tracked codebase because:

1. Token storage is in untracked operational data (`.deerflow/rtcm/`), not in any tracked credential store
2. Token rotation requires manual operator action via open.feishu.cn developer console
3. The tracked `app.channels.feishu` module does not own or manage this token

### Threat Model Impact

- **Confidentiality**: If `.deerflow/rtcm/` is inadvertently committed to a public or shared repository, the token is exposed
- **Integrity**: Any process with read access to the token can send Feishu messages on behalf of the bot
- **Availability**: Token revocation by the operator would break RTCM operational sessions without notice

### Compensating Controls

| Control | Status | Evidence |
|---------|--------|----------|
| `.gitignore` for `.deerflow/rtcm/` | ✅ Active | PR #8 merged — `b931d8ff` |
| `.git/info/exclude` broad pattern | ✅ Active | Line 9: `.deerflow/` — local-only |
| Token not printed in reports | ✅ Confirmed | `token_value_repeated=false` in all Feishu card builds |
| No tracked runtime uses token | ✅ Confirmed | `app.rtcm` does not exist in tracked code |
| Hygiene guard verified effective | ✅ Confirmed | R212X — `git check-ignore -v` confirms both layers cover token_cache.json |

### Required Resolution

1. **Operator action required** — rotate token via open.feishu.cn → credentials → revoke
2. After rotation: new token stored in operator-managed credential vault (not in `.deerflow/rtcm/token_cache.json`)
3. Update `FEISHU_TOKEN_ROTATION_ACK=true` env var to unblock full security claim

### Acknowledged By

- Operator: DEFERRED (no explicit ACK recorded)
- Code owner: acknowledged in Phase 7 close docs

### Forbidden Claims While Open

- **"Security fully clean"** — exception is HIGH severity and un-remediated
- **"Feishu token rotated"** — rotation is operator-deferred
- **"No security exceptions"** — S-RTCM-FEISHU-TOKEN-001 is open

---

## Carry-Forward Rule for Asset and RTCM Implementation

Any future Asset (`backend/app/asset_runtime/`) or RTCM (`backend/app/rtcm/`) implementation must:

- **Never read `.deerflow/rtcm/`** — operational data is not runtime source code
- **Never read `token_cache.json`** — token value must never be accessed
- **Never use Feishu token** — credentials must come from `app_config.lark`, never from operational data
- **Never send real Feishu/Lark messages** — dry-run first, `--real` opt-in only after R212 closure
- **Never claim "security clean"** — S-RTCM-FEISHU-TOKEN-001 remains open until rotation is acknowledged

These constraints apply to all R220–R227 implementation stages and are non-negotiable.

---

## Final Carry-Forward Status (R228X)

As of R228X batch close, the following implementation states are confirmed:

| Implementation | Dry-Run Runtime | Real Runtime | Operational Data Access |
|----------------|-----------------|--------------|------------------------|
| `app.asset_runtime` | ✅ IMPLEMENTED (PR #13) | ❌ NOT IMPLEMENTED | ✅ No access confirmed |
| `app.rtcm` | ✅ IMPLEMENTED (PR #14) | ❌ NOT IMPLEMENTED | ✅ No access confirmed |
| `app.nightly_review` | ✅ IMPLEMENTED (PR #9+11) | ⚠️ Not production-verified | ✅ No access confirmed |

All three tracked dry-run runtimes passed cross-runtime safety tests (`test_openclaw_integration_smoke.py`, 19/19 passing).

### Claim Status

- **AVAILABLE_WITH_LIMITS**: Asset, RTCM, Feishu/Report, Nightly Review
- **Forbidden claims** (must not be made): security fully clean, Feishu token rotated, real Agent-S integration, production-verified runtime

---

## Future Implementation Guard

Any future work that attempts to promote Asset, RTCM, or Nightly Review from dry-run to production runtime:

| Guard | Requirement |
|-------|-------------|
| R212 P0 closure | `FEISHU_TOKEN_ROTATION_ACK=true` must be set before real Feishu send |
| Token origin | Credentials must come from `app_config.lark`, never `.deerflow/rtcm/token_cache.json` |
| No operational data as runtime | `.deerflow/rtcm/` and `.deerflow/operation_assets/` are never imported or read |
| Explicit opt-in | `--real` flag required for any real API call; dry-run is always the default |
| Security exception open | S-RTCM-FEISHU-TOKEN-001 remains OPEN until operator rotation is confirmed |

These guards are non-negotiable and apply to all future implementation stages.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-05-06 | Initial — S-RTCM-FEISHU-TOKEN-001 documented |
| 2026-05-06 | R212X — hygiene guard verified effective via git check-ignore |
| 2026-05-06 | R216X — carry-forward rules added for Asset and RTCM R220–R227 |
| 2026-05-06 | R228X — final carry-forward status added; future implementation guard added |