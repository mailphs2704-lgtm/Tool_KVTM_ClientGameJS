# AUTO MULTI DEV — OPERATIONS LOG / COUNTERS / ERROR RECOVERY CHECKPOINT

Date: 2026-09-15
Branch: `develop/multi-auto-dev`
Status: **SOURCE COMPLETE — BUILD/LIVE PENDING**

## Operator contract

Log hành động is reserved for concise account milestones only. Normal technical chatter, recognition details, navigation evidence, timing, stage transitions and diagnostics belong to Log chi tiết.

Expected operator-facing shape:

```text
[time] . <account> . Đã bán ... tổng số VP bán trong ngày ...
[time] . <account> . Mở rương thành công N lần hôm nay
[time] . <account> . Gieo thành công ...
[time] . <account> . Sản xuất ...
[time] . <account> . Lỗi ..., chuyển trạng thái xử lí
```

`AutomationContext.action()` owns concise progress. `AutomationContext.log()` and `detail()` go to the detail stream when `detail_logger` is present. Worker/bootstrap chatter is also routed to detail; the context logger is now the action-only emitter.

## Daily counters

Persistent per-profile counters:

- Sale: one successfully posted x10 listing = one sale turn; survives tool/ClientJS restart and resets on the local calendar day boundary.
- Pirate chest: increments only on `OPENED`; survives tool/ClientJS restart and resets at local midnight.

The selected account information panel now installs the existing daily-counter integration and shows:

```text
LƯỢT BÁN AUTO
RƯƠNG HẢI TẶC
```

with a 1-second UI refresh.

## Runtime error policy

Known typed policies remain closest to the failing module. Handled production errors such as warehouse full / wrong production machine and material shortage emit one concise action line and are persisted to the per-profile error journal.

Any exception escaping installed AUTO Main policies is globally recovered instead of ending the AUTO run:

```text
record Vietnamese error diagnostics
→ recover unknown camera to exact MAIN
→ friend #1
→ return own home
→ prove exact MAIN
→ restart selected AUTO Main workflow
```

Recovery itself retries until it succeeds or the operator explicitly stops AUTO. `AutomationStopped` and `ClientRestartRequested` remain control/lifecycle signals, not errors.

Bootstrap/Bridge failures that happen before the business recovery graph exists remain fatal lifecycle failures; they cannot safely perform in-game exact-main recovery because no valid automation graph exists yet.

## Error journal

Every persisted record is per-profile and includes timestamp, account, error class, Vietnamese explanation, original message, phase, recovery state and traceback when available. Sensitive-looking token/password/cookie/authorization values are redacted by the journal helper.

Multi DEV now installs the error journal UI:

```text
⚠ Log lỗi
⇩ Xuất lỗi TXT
```

TXT export is intended for collecting live failures to implement future typed fixes.

## Wiring changed in this checkpoint

- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py`
  - installs daily sale/pirate counters after Builder/Profile integration;
  - installs per-account error journal viewer/export UI;
  - keeps recorder installation last.
- `components/clientjs-auto/worker/auto_multi_dev_worker.py`
  - worker/bootstrap `log()` now writes detail;
  - `AutomationContext.logger` is action-only.
- `components/clientjs-auto/kvtm_automation/recovery/material_shortage.py`
  - material shortage writes error journal + concise action line.
- `components/clientjs-auto/kvtm_automation/workflows/auto_main/pirate_chest_schedule.py`
  - pirate SAFE_ABORT/exception is journaled;
  - concise error action is emitted before scene reset.

Existing concise Function milestones, daily sale summary, daily chest OPENED count, typed production error journal/action lines, and global AUTO Main unhandled recovery were preserved.

## Verification gate

Do not call build/static PASS from source inspection.

Operator gate:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

After build succeeds, live-check one account for:

1. Log hành động contains only concise milestone/error rows with account name.
2. Log chi tiết keeps full runtime diagnostics.
3. Pirate chest daily count appears in selected-account details and survives tool restart; midnight rolls it to zero/new day.
4. A controlled recoverable error writes `Log lỗi` and can be exported to TXT.
5. An unhandled runtime error follows exact MAIN → friend #1 → own home → AUTO restart instead of ending normal AUTO Main.

Runtime PASS requires operator evidence.