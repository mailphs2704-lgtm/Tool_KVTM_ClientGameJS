# AUTO MULTI DEV CAPTURE3 WRITERMSG1 handoff

## Live evidence that triggered this change

An uninterrupted AUTO MULTI DEV run negotiated the current WRITERMAP2 bridge and later failed with:

`ERR WRITER <non-zero current writer id> 0000000000000000`

This is not a stale-frame retry problem. In the WRITERMAP2 native contract, `dispatch_capture()` writes the current `g_writer_id` into `CaptureCommand.writer_id` before returning `ERROR_SUCCESS`. A successful capture result with a zero writer-id tail therefore means the pipe-side writer and the window-proc that consumed the capture message were not the same capture ABI/generation.

The remaining collision surface was the shared private window message `WM_APP + 0x418`. A different resident/subclass proc could consume that message before the current writer's proc and return success using an older `CaptureCommand` layout, leaving the new writer-id tail at zero.

## Root fix

Commit chain:

- `3ce96ff4b2078994f4c8c49f8ce6292622d8e326` — native writer-specific render-thread capture dispatch.
- `0a04dd984290a6d1ecf99ffbe36a984bf89ce829` — driver/factory revision gate.
- `310c7d7061ff5b475e62b29fdc35e9344253e753` — isolated worker exact protocol requirement/live marker.
- `5610bfa3cf2acf5c3c90ce31203ffb025b6f6f07` — static contract lock.

The new native revision adds `CAPTURE3_WRITERMSG1`:

- Generate a registered Windows message name containing PID + current writer id.
- `CAPTUREW` dispatches to the render thread using that writer-specific registered message.
- The current bridge window proc handles its registered writer message.
- An older/different subclass proc does not know that registered message and must pass it down its window-proc chain instead of treating it as the legacy capture command.
- Legacy `CAPTURE` remains on `WM_APP + 0x418` for packaged consumers that still need the old interface.
- WRITERMAP2 remains unchanged: reader opens only `Local\KVTM-CaptureV3-{pid}-{writer_id}` and requires exact writer, exact request frame, exact dimensions and stable post-copy header.

Current required protocol prefix:

`OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP CAPTURE3_WRITERMAP2 CAPTURE3_WRITERMSG1`

## Safety invariants

Do not repair future failures by accepting writer id `0`, accepting stale/newer frames, lowering capture validation, restoring HWND fallback, or increasing retry loops to hide identity errors. The reader stays fail-closed.

Do not change stable Dọn quầy or AUTO PRO business logic for this transport issue.

## Next live gate

Because the DLL is resident inside ClientJS and cannot be hot-swapped safely, close Multi DEV and the DEV ClientJS instances before rebuilding/reopening.

User update/build path remains root `KVTM_DEV_CONTROL.bat` Control Center `[1] Cap nhat source + build runtime DEV`, then `[2]` to launch Multi DEV.

Expected new live evidence:

- `DLL bridge V3: CAPTURE3 WRITERMAP2+WRITERMSG1 ENABLED`
- PING contains `CAPTURE3_WRITERMSG1` followed by a non-zero 16-hex writer id.
- No `ERR WRITER ... 0000000000000000` during uninterrupted capture.

Build/static success is not runtime PASS. Runtime PASS requires an uninterrupted Windows live run through normal game startup and subsequent workflow capture.