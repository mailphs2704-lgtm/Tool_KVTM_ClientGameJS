# KVTM AI Session Coordination

> Tài liệu điều phối bắt buộc cho mọi phiên AI làm việc trên repository này.
> Đọc toàn bộ file trước khi sửa code. Cập nhật trạng thái/handoff trước khi kết thúc một mốc công việc.

## Mục tiêu chung

Xây `KVTM-ClientJS-Suite` gồm Multi, ClientJS Workspace và Auto chạy nền ổn định. Workspace có thể thu nhỏ xuống taskbar mà ClientJS và Auto vẫn tiếp tục chạy. Mọi thao tác thử nghiệm phải chỉ tác động tới client thuộc bộ DEV hiện tại.

Tài liệu chi tiết cho migration máy phụ + runtime updater:

- `docs/SECONDARY_MACHINE_RUNTIME_UPDATE.md`

## Phân nhánh và quyền sở hữu

| Phiên | Nhánh làm việc | Phạm vi sở hữu chính | Không tự ý sửa |
|---|---|---|---|
| AUTO/Multi | `develop/multi-auto-dev` | Logic Auto, workflow Dọn quầy, Multi hiện tại, profile/session, worker/probe, migration máy phụ, runtime updater | `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat` |
| Workspace | `develop/clientjs-workspace` | Workspace host, Live View, attach/detach, capture lifecycle, Control Center Workspace | Logic nghiệp vụ Auto/Dọn quầy đang được phiên AUTO sửa |

Hai phiên không push trực tiếp vào nhánh của nhau. Không force-push, không rebase nhánh đã chia sẻ và không sửa lịch sử Git.

## File dùng chung cần phối hợp trước

Các file sau có khả năng được cả hai phía sử dụng. Phiên muốn sửa phải ghi rõ lý do trong commit và cập nhật mục Handoff:

- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py`
- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py`
- `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1`
- `KVTM_DEV_CONTROL.bat`
- `test-candidates/auto-pro-clientjs-temp/pc_driver.py`
- `test-candidates/auto-pro-clientjs-temp/engine_driver.py`

Ưu tiên mở rộng bằng module mới và interface ổn định thay vì cùng sửa một file lớn.

## Interface giữa Workspace và Auto

Workspace không sở hữu vòng đời Auto. Auto không phụ thuộc việc cửa sổ Workspace đang hiển thị.

- Device identity: `profile_id + PID + HWND`.
- Kích thước logic ClientJS: `1000 x 1000`, DPI mục tiêu `240`.
- Capture chính: OpenGL shared memory theo PID.
- Capture dự phòng: HWND capture.
- Auto input/capture chạy độc lập với Live View.
- Workspace thu nhỏ: dừng hoặc giảm refresh giao diện; không minimize/đóng ClientJS.
- Workspace đóng: mặc định không đóng ClientJS và không dừng Auto.
- Không điều khiển mọi `GameClientJS.exe` trên máy; chỉ nhận client khớp profile DEV.

## Quy trình đồng bộ bắt buộc

1. Đọc file này và xác nhận đúng nhánh trước khi sửa.
2. Kiểm tra working tree; không ghi đè thay đổi chưa commit của người/phiên khác.
3. Mỗi commit chỉ chứa một mục tiêu rõ ràng.
4. Ghi SHA nguồn khi lấy thay đổi từ nhánh bên kia.
5. Dùng `merge --no-commit` hoặc `cherry-pick` có chọn lọc trên nhánh tích hợp; không merge mù toàn nhánh.
6. Nếu cùng cần sửa một file dùng chung, một phiên hoàn tất và commit trước; phiên còn lại lấy commit đó rồi mới tiếp tục.
7. Không coi build thành công là runtime PASS. Chỉ ghi PASS cho hành vi Windows khi có output/live evidence phù hợp.
8. Không upload/commit secret, `.kvtm`, raw `profiles.json`, plaintext launch args, token, cookie hoặc password.

## Trạng thái phiên AUTO/Multi

- Nhánh chính: `develop/multi-auto-dev`.
- Chủ sở hữu cập nhật: phiên AI làm Auto/Multi.
- Trạng thái: `IN_PROGRESS / READY_FOR_NEXT_LIVE_TEST`.
- Migration máy phụ: hoạt động. Main đã export 13 profile; máy phụ đã import. Người dùng mở ít nhất 1 profile và xác nhận vào thẳng game, không đăng nhập lại.
- Máy phụ: Git/Git LFS/Python 3.11 x64/VC++ x86+x64/ZingPlay/GameClientJS/game data đã có diagnostic `ENVIRONMENT_READY` trong các lần kiểm chứng trước.
- GitHub bridge: `[8]` gửi SAFE diagnostic lên branch `machine-sync/cry-pc`; `[9]` pull/deps/LFS/build DEV runtime. Không upload profile/transfer file.
- Runtime updater UI: nút `Cập nhật DEV` đã có trong `BẢNG ĐIỀU KHIỂN`. Người dùng đã xác nhận `giao diện pass` sau bootstrap gần nhất: vị trí nút đúng và chữ tiếng Việt không còn lỗi mojibake.
- Runtime updater code mốc chính: `4806e433591b8623126e11c6e13e6ac1adec5808` (`Make staged runtime activation robust`).
- UI/text fix: `28209c3ab6a53cf90cbb232beecc646928571fa0`.
- PS5.1 branch detection fix: `01690a565c4fcf904d802e1c2d5f359ca3173a2e`.
- CI cho `4806e433...`: FULL PASS.
  - `Multi DEV checks`: `clear-stall-static` PASS, `package-smoke` PASS.
  - `Secondary machine checks`: toàn bộ PowerShell/Python parse, PS5.1 regression, bridge/updater safety, transfer crypto, diagnostic và ignore checks PASS.
- Evidence live gần nhất trước bootstrap cuối: repo source `28209c3`, runtime `01690a5`, updater UI/hook FOUND. Sau đó user chạy `[9]` và báo `pass`, rồi báo `giao diện pass`. Chưa có `[8]` mới sau `giao diện pass`, vì vậy không tự suy đoán runtime SHA hiện tại.
- Known issue đã xử lý: source có thể lên commit mới nhưng runtime vẫn cũ do watcher activation. `4806e433...` làm activation robust hơn và hỗ trợ updater self-update/retry/process tracking.
- **NEXT bắt buộc:** test một vòng update hoàn toàn bằng nút `Cập nhật DEV`, không dùng `[9]`. Có thể dùng commit tài liệu mới nhất làm target harmless. Sau update, đóng/mở Multi, chạy `[8]`, chỉ chốt FULL PASS khi `head == runtime_source_head`, updater UI/hook FOUND, `RESULT=ENVIRONMENT_READY` và profile vẫn hoạt động.
- Nếu `[8]` cho source HEAD mới nhưng `runtime_source_head` cũ: activation là PARTIAL/FAIL; debug staging/status/watcher, không dùng `[9]` như giải pháp lâu dài.
- File chính của luồng này:
  - `tools/KVTM_PROFILE_TRANSFER.ps1`
  - `tools/KVTM_PROFILE_VERIFY.ps1`
  - `tools/KVTM_MACHINE_SETUP.ps1`
  - `tools/KVTM_GITHUB_BRIDGE.ps1`
  - `tools/KVTM_RUNTIME_UPDATE.ps1`
  - `KVTM_MACHINE_TRANSFER_CONTROL.bat`
  - `KVTM_SECONDARY_BOOTSTRAP.ps1`
  - `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`
  - `source-archive/multi-current/kvtm_multi_tool/runtime_update_ui.py`
- DO_NOT_TOUCH cho task updater/migration: `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat`; không thay đổi capture/driver/Dọn quầy nếu không cần cho lỗi updater.

## Quy trình máy phụ nhanh

- `[7]`: verify profile/DPAPI READ-ONLY.
- `[8]`: gửi report an toàn lên GitHub.
- `[9]`: bootstrap/update khẩn cấp; mục tiêu cuối cùng là không cần dùng thường xuyên sau khi updater UI được live-verified.
- Mở DEV runtime: `dist\KVTM-ClientJS-Suite-Multi-DEV\02_START_MULTI_DEV.bat`.
- Khi user nói `đã gửi` sau `[8]`, đọc `machine-sync/cry-pc:machine-reports/CRY-PC/LATEST.txt` trước khi kết luận.

## Trạng thái phiên Workspace

- Nhánh: `develop/clientjs-workspace`
- Nền ban đầu lấy từ AUTO/Multi: `f10d773`
- HEAD trước tài liệu điều phối: `addc02f`
- Đã có:
  - `components/workspace/kvtm_workspace.py`
  - `KVTM_WORKSPACE_CONTROL.bat`
  - `INSTALL_KVTM_WORKSPACE.bat`
  - Workspace worktree riêng tại `Tool_KVTM_Workspace_DEV`.
  - Control Center tự build package nếu `dist` bị thiếu hoặc cũ.
- Đang kiểm thử: Giai đoạn 1, mở Multi + Workspace Live View và thu nhỏ Workspace mà ClientJS/Auto không dừng.
- Chưa bật: click/swipe nền từ Workspace, attach/detach hoàn chỉnh, chế độ host nhiều Device giống video tham chiếu.
- Yêu cầu với phiên AUTO/Multi: khi thay đổi driver/capture/bootstrap, ghi rõ interface và commit SHA tại phần Handoff.

## Handoff log

Thêm bản ghi mới lên đầu bảng. Không sửa hoặc xóa lịch sử cũ.

| Thời gian UTC | Từ phiên | Đến phiên | Commit | Nội dung / hành động cần làm |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `5651463`, `d5d863d` | Máy phụ build dừng hiển thị ngay sau `BRIDGE V3 BUILD VERIFIED`; compiler/hash đã PASS. Builder sau dòng này im lặng copy recursive data-dev/clear-stall và clear-stall-probe trước khi xóa/rebuild runtime; probe chứa nhiều PNG/log nên Copy-Item nhìn như treo. Thay preservation bằng robocopy /MT:8, retry1, heartbeat 15s, timeout600s; timeout/fail dừng trước khi xóa output và giữ nguyên dữ liệu nguồn. Static verifier full PASS, output diagnostic_preservation=robocopy_mt8_heartbeat_timeout600. Chưa Windows/package live PASS. NEXT Ctrl+C build cũ rồi `[1]`, gửi output [DATA]/PACKAGE. Không sửa Workspace/profile/log contents. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `6f638b1`, `1ebda58` | User cung cấp ZIP AUTO KVTM PRO gốc chuẩn. Local-only forensic: ZIP sha256 d3366f3e..., EXE d197f057..., trích PyInstaller Python3.11 thành công; adb_controller.pyc sha256 e0299c6d...; disassembly openChests lines1163..1243. Bằng chứng gốc không có `ruong_bac`; chuỗi exact là chest zone(320,508,128,79) threshold.8 → click371,647 → ruong_go zone(163,520,190,196) threshold.95 timeout1 → recovery check_mo_ruong/check_open_chest → mo_ruong zone(393,505,212,96) threshold.9 click → click433,557 tối đa5 → press_back+fixerr. Đã cài source reconstruction exact cho ClientJS; openGame/reset AUTO PRO và EngineDriver PID reconnect giữ nguyên. ZIP/assets không upload. Pycompile + full static PASS, output chest=supplied_auto_pro_bytecode_exact; chưa LIVE PASS. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `a216108`..`e3acc3f` | Theo yêu cầu user rollback hoàn toàn Mở rương/reset: `clientjs_auto_patch` không còn gán `cls.openGame/openChests`, worker bỏ retry/reset 3 lỗi tự thêm và gọi thẳng `automation.start()`, nên AUTO PRO sở hữu nguyên bytecode openChests + error/reset. Giữ EngineDriver immutable profile/PID rebind, Bridge reconnect và client_pid_changed. Live screenshot bổ sung popup LÊN CẤP bị kẹt (ảnh là crop, không dùng tỷ lệ/tọa độ): thêm monitor chỉ khi match marker len_cap/lencap/level_up, chỉ click tâm template nhan/nhan_thuong, cấm blind coordinate; không thấy button thì trace blocked. Full py_compile + static verifier PASS: chest=auto_pro_original, level_up=template_only_no_blind_coordinate. Chưa LIVE PASS. Không sửa Workspace/profile/Dọn quầy. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `5170278`, `d5ca177` | Live retest phản hồi không vào được giao diện Mở rương: state machine 2 trạng thái trước đã thay cả `original_open_chests`, làm mất navigation AUTO PRO từ farm vào Kho báu. Sửa triệt để: trả quyền điều hướng/thứ tự chung cho `original_open_chests`; wrapper chỉ intercept click chọn gỗ (371,647), exact `ruong_bac` threshold1.0/disappearance, trạng thái modal sẵn, click mở ClientJS (500,470), screen-change và verified exit. Full py_compile + full static verifier PASS. Chưa LIVE PASS; NEXT `[1]` và retest. Không sửa Workspace/profile/Dọn quầy. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `2f63e7e`..`fd42347` | Theo xác nhận nghiệp vụ user, thay wrapper Mở rương PC bằng state machine 2 trạng thái: (1) nếu thấy `ruong_bac` exact threshold1.0 thì click Rương gỗ (371,647), chờ Rương bạc biến mất ổn định rồi mới mở; (2) nếu Rương bạc đã vắng khi vào thì coi modal đã mở sẵn và bỏ qua click chọn. Sau đó click tâm live-verified (500,470), chỉ công nhận mở khi modal-region change>=8, đóng reward/modal và chỉ hoàn tất khi farm anchor thật + không còn chest overlay. Không replay luồng LD trên PC. Python compile và full static verifier PASS; output chest=two_state_silver_exact_modal_skip_verified_exit. Chưa LIVE PASS. Không sửa Workspace/profile. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `37db1a0`, `abf61ea`, `f88896a` | Live screenshot: ClientJS kẹt modal `Chạm để mở rương` nhưng UI báo sai `Bắt Đầu AUTO • đã nhận giao diện hiện tại`, nên không reset. Root cause `_game_anchor` thấy icon farm phía sau overlay và live-frame fallback cũng chấp nhận frame modal; đồng thời điểm live-verified (500,470) đã bị rơi khỏi probe list. Đã khôi phục (500,470) ưu tiên đầu, thêm `_blocking_game_overlay` nhận mo_ruong/ruong_go và cấm cả farm-anchor lẫn 3-frame readiness khi overlay còn hiện. Full Python compile + toàn bộ clear-stall static verifier PASS. Chưa LIVE PASS; NEXT `[1]`, mở lại AUTO tại trạng thái rương để xác nhận click mở hoặc reset đúng ClientJS/PID. Không sửa Workspace/profile. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `4be125fe3bb9e3e0ac9375031f11281eeb4a4df5` | Windows build 46ba4df FAIL trước package vì verifier line361 còn yêu cầu policy cũ `UNTIL_TARGET_OR_STOP`. Đã thay bằng `ONE_SCAN_PER_HOUSE_THEN_NEXT_ROUND`, sau đó dựng đủ toàn bộ 20 dependency của verifier từ HEAD và chạy chính `python tools/verify_clear_stall_contract.py`: PASS, output xác nhận account_concurrency=2, one_scan_per_house_then_next_round, same_friend_reload=disabled, sl10_marker_not_required. Đây là STATIC PASS; package Windows/live vẫn chờ `[1]`. Không sửa runtime logic/profile/Workspace trong commit fix này. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `e745153`..`4d33b5c` | Theo yêu cầu mới: AUTO chính đếm 3 lỗi qua/thoát nhà bạn rồi reset đúng ClientJS; nhận lại bằng immutable profile_id, PID mới và openGame/3 frame hợp lệ, chỉ reset một lần trước khi FAIL rõ. Dọn quầy mỗi nhà đúng 1 scan/vòng, thiếu target thì quay vòng mới nhà1..N. Treo bán không còn bắt buộc template sl10 nhưng vẫn khóa fingerprint mua trong lượt + không đổi giá + screen-change verify. Scheduler DEV cho tối đa 2 profile Dọn quầy độc lập; profile thứ ba giữ due/chờ. 5 file Python py_compile PASS; static/package/live Windows chưa PASS. Không sửa Workspace/profile. NEXT chạy `[1]`, gửi output static/package; sau đó live 2 acc Dọn quầy. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | LIVE build `4b197744879460fcf5eb8e004c29a0080b3e23a9` | SECONDARY RUNTIME BUILD FULL PASS: machine diagnostic trước đó `ENVIRONMENT_READY`; MSVC x86 Developer Command Prompt 17.14.39 build Bridge V3 x86 PASS, SHA256 được ghi, `BRIDGE V3 BUILD VERIFIED`, `PACKAGE OK`; source/runtime DEV cùng HEAD `4b19774`. Builder bảo toàn `data-dev/settings.json` và `profiles.json`; profile merge 20/20 đã PASS riêng. Có thể mở Multi bằng `[2]`. Dọn quầy mua VP vùng giữa vẫn cần live workflow/ZIP để xác nhận hành vi, không suy diễn từ build PASS. Không sửa Workspace. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | LIVE profile merge after `e44e230` | PROFILE TRANSFER MERGE FULL PASS: máy chính export 20 profile, encrypted payload memory round-trip True; máy phụ import incoming20/existing13/preserved-local0/after-merge20, mode MERGE_BY_ID, client/game path rewrite0, settings False. Verify READ-ONLY: profiles20, DPAPI decryptable20, secret JSON20, client paths20, game paths20, DPAPI/LAUNCH READY; không in secret. Phạm vi compiler/bridge build máy phụ vẫn riêng và chưa PASS. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `1f2ea17`..`379f11f` | File `.kvtm` cũ là snapshot nên không có tài khoản thêm tối qua; Import cũ thay toàn bộ profiles. Import mặc định nay `MERGE_BY_ID`: backup đích, giữ profile local-only, thay/cập nhật ID trùng bằng bản DPAPI re-bind từ máy chính, thêm ID mới, chặn incoming/existing ID trùng hoặc thiếu secret, ghi temp + verify rồi mới activate. Có switch `-ReplaceProfiles` cho hành vi thay toàn bộ có chủ ý; menu ghi rõ merge. Static contract cập nhật; chưa live PASS. NEXT máy chính cập nhật, `[M]→[1]` xuất file mới; máy phụ cập nhật, `[M]→[2]` nhập và `[6]`/verify count. Không sửa Workspace. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `560eec5`..`f0fac0f` | Live máy phụ d0fee19: fallback đúng khi chặn binary runtime 87bff934 vì bridge capture đã đổi và Bridge V3 được thêm mới sau runtime đó. Không hạ gate. `[M] → [4]` nay tự phát hiện/cài `Microsoft.VisualStudio.2022.BuildTools` với workload VCTools x86/x64 qua WinGet; diagnostic ghi `vc_build_tools_x86_x64`, coi thiếu compiler là NOT_READY. Menu/tài liệu/static contract đã cập nhật; profile không đổi, không sửa Workspace. NEXT `[1]` lấy HEAD, `[M]`, `[4]` cài một lần, rồi `[1]` build; chưa live PASS. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `1a758e6`, `89ac858` | Live máy phụ tại 1f1aa9a bắt lỗi parser PS5.1 trong fallback: `$Label:` bị hiểu là variable scope/drive. Đã đổi thành `${Label}:` và thêm static regression bắt buộc delimiter, cấm chuỗi cũ. Đây là parser-only fix, không đổi gate PE/source-diff, profile hay Workspace. NEXT máy phụ chạy lại `[1]`; chưa live PASS. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `a0d41a0` | Thêm mục `[M] Chuyển máy` tối giản vào `KVTM_DEV_CONTROL.bat`; dùng `call` để mở công cụ có sẵn `KVTM_MACHINE_TRANSFER_CONTROL.bat` ngay trong cùng cửa sổ rồi quay lại Control Center. Không sao chép logic export/import, không đọc/sửa profile khi chỉ mở menu, không sửa Workspace. NEXT máy phụ `[1]` lấy HEAD mới rồi kiểm tra mục `[M]`; build fallback compilerless vẫn chờ live. |
| 2026-09-05 | AUTO/Multi | AUTO/Multi + Workspace | `3a99c29`..`31fd12a` | Máy phụ `[1]` tại f58972a static PASS nhưng build dừng exit20 vì chỉ có VC++ Runtime, không có MSVC Build Tools. Builder nay fallback dùng 4 binary bridge/loader của runtime DEV cũ chỉ khi `.source-head.txt` là commit hợp lệ, 6 input bridge không đổi tới HEAD và mọi PE là x86 machine 0x014c; nếu bất kỳ gate nào sai vẫn fail và yêu cầu compiler. Profile/data-dev được giữ; không sửa Workspace. Static workflow guard + tài liệu đã cập nhật. GitHub Actions hiện fail trước step như các HEAD trước, chưa live PASS. NEXT máy phụ chạy lại `[1]`, cần log `dung binary x86 tu runtime ...; source bridge khong doi` và package PASS. |
| 2026-09-04 | AUTO/Multi | AUTO/Multi + Workspace | `8f63dfa`..`ae791fd` | Lỗi mua VP vùng giữa quầy: luồng cũ thực hiện liền 2 swipe rồi mới scan nên listing chỉ hiện giữa hai nhịp bị lướt qua. Luồng mua nhà bạn nay giữ đúng 2 swipe nhưng bắt buộc `SWIPE → SCAN → BUY → SWIPE`, lưu PNG/checkpoint `stall-intermediate-swipe-scan` và accounting vẫn chỉ cộng sau giao dịch xác minh. Thêm static guard; 2 file AST PASS. Cơ chế watchdog TẠM PASS 5 phút và profile không đổi. CI Actions vẫn FAIL trước khi chạy step giống HEAD 206d652, nên chưa LIVE PASS. NEXT [1], chạy một acc có VP chọn ở giữa quầy và gửi ZIP clear-stall-probe. Không sửa Workspace. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | Gate3B live + `9da9b76`, `e2d9528` | GATE 3B LIVE PASS ZIP 20260903-132654: target130, purchased130, remaining0, PURCHASE_TARGET_MULTI_HOUSE, SCAN_BUY_THEN_SWIPE, ok=true/exit0. Nhà1 mua60 qua pass1+3, chạy đủ 4 pass tại chỗ rồi nhà2 mua70 và dừng đúng target. Sửa log UI ghi đúng Gate3B thay vì Gate2; AST PASS. Chưa thu vàng/treo bán. NEXT Gate4 thu vàng + treo đúng một batch x10, không đổi giá. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `b43e489`..`1f11c15` | ZIP 20260903-131839: sau swipe scanner chỉ xét new_local 5..8 nên bỏ hàng trên. Đã tách visible_local_slots=1..8 và scan cả hai hàng ở mọi view. Reload cùng nhà nay close→open tại chỗ đủ số lượt cấu hình, kể cả lượt trước mua0; chỉ return_home một lần khi chuyển friend tiếp theo. Giữ bound, accounting verification và no resale. 3 file AST PASS; chưa live PASS. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `b0c6ce8`..`e009fac` | ZIP 20260903-131241: scan-buy-swipe hoạt động nhưng chỉ mua hàng dưới vì coin filter hàng trên đọc nhầm y455..495. Ảnh đo đúng: top y495..530, bottom y685..720; empty/sold=0, available=130..199, cutoff120. Đã sửa riêng top band + static guard; AST PASS. NEXT [1] và rerun. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `b42e189` | Build ac65a5d bị static verifier false-negative vì reload range được format nhiều dòng. Đã sửa verifier kiểm tra policy + bound bằng hai invariant bền vững; verifier/probe AST PASS và 5 Gate3B needles đều FOUND. Đây là build-gate fix, không đổi runtime behavior. NEXT pull/build [1]. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `c59a139`..`c9c5b0c` | ZIP 20260903-125935 xác nhận Gate3B cũ quét đủ 4 view rồi rewind, gây bỏ view giữa khi mua. Đã đổi hoàn toàn sang SCAN_BUY_THEN_SWIPE: mua view hiện tại, vuốt 2 nhịp, mua view mới tới cuối. Listing click không đổi do thiếu level nay skip không accounting và tiếp tục. AST PASS; chưa live PASS. Không sửa Workspace. NEXT [1], chạy lại target150/2 nhà/4 lượt. |
|---|---|---|---|---|
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `bd05c8b`..`653ffc5` | Gate3B live run 20260903-125257 FAIL an toàn: click physical slot1 đang là “Đã bán”, UI không đổi nên không cộng 10 VP. Root cause scanner chỉ đo artwork occupancy. Đã thêm coin-price marker filter trước planning (evidence sold<=72, available>=184, cutoff120), sửa popup hiện đúng Gate3B và static guard; AST PASS. NEXT update/build và chạy lại cùng target 150, nhà1..2, max4. Chưa thu vàng/bán. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `5d07c86`..`463bedd` | Gate 3B source hoàn thiện một lượt: remaining target x10; tải lại tối đa 10 lượt/nhà theo max_scan_pages; lượt không mua thêm thì chuyển nhà; duyệt tuần tự nhà 1..N; mỗi purchase có PNG + friend/pass/view/slot/remaining; dừng ngay khi đủ hoặc FAIL expected/actual/remaining và quay về. DEV UI nhận gate `PURCHASE_TARGET_MULTI_HOUSE`. Thu vàng/treo bán vẫn khóa. Runtime/probe/dev-entry/verifier AST PASS; chưa LIVE PASS. NEXT: Control Center [1], mở một clone, đặt N/target rồi chạy Gate 3B một lần. Không sửa Workspace. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `bf7b0f7` + live UI | GUI Dọn quầy LIVE PASS theo xác nhận user: tab_host 190px + Gate3 hàng riêng không còn bị cắt chiều cao sau update/reopen. Gate3 transaction PASS trước đó giữ nguyên. NEXT: Gate3B tải lại quầy/chuyển nhà theo remaining target; chưa mở bán. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | Gate 3 live + `bf7b0f7`, `5109049` | GATE 3 LIVE PASS run 20260903-123215: target 40, đúng 4 click slot 1..4, PNG sau từng giao dịch cho thấy lần lượt “Đã bán”, accounting 10/20/30/40, return home, exit0; chưa bán/thu vàng. GUI Dọn quầy bị clip vì tab_host 142px; đã tăng 190px, chuyển Gate3 xuống hàng riêng, giảm account workspace tương ứng để tổng window không tăng. Shared kvtm_multi.py chỉ đổi layout; syntax PASS; chưa live GUI verify. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `9829567`..`e05f2c0` | Gate 3 target-purchase đã chuẩn bị sau Gate 2 live PASS: nút/consent riêng, target cấu hình quy đổi ô x10, từng call maximum=1, listing phải đổi trước accounting, PNG sau từng giao dịch, dừng đúng target và quay về; chưa bán/thu vàng. Static Python syntax PASS. Phạm vi Gate 3 hiện là một quầy đã quét; tải lại/chuyển nhiều nhà chưa live. NEXT build rồi thử target tối thiểu 20 VP. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | Gate 2 live + `7c161de` | GATE 2 LIVE PASS từ ZIP 20260903-122225: profile Account số 3 PID 13536, purchase_limit=1, đúng một DOWN/UP (290,435), listing đổi trước accounting, purchased_quantity=10, không click mua thứ hai, quay về nhà, exit 0. Phạm vi PASS chỉ mua một listing x10; chưa PASS mua target/nhiều nhà/treo bán/hàng đợi live. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | Gate 1 live + `994ef08`..`26c2411` | Gate 1 LIVE PASS từ ZIP run 20260903-121121: profile Account số 3 PID 5340, nhà bạn #1 hiển thị Account số 2, shared capture 1000x1000, bốn view khác nhau tới cuối quầy, return home, report v11 ok/capacity=DYNAMIC_REMAINING_COUNTER, activity không có mua/bán. Gate 2 source đã sẵn sàng với nút/hộp consent riêng, giới hạn cứng một listing x10 và chỉ cộng sau listing đổi/biến mất; scheduled worker vẫn READ_ONLY. Chưa build/live Gate 2. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `2e9cfc3` + live build | STATIC/PACKAGE PASS trên Windows: Bridge V3 BUILD VERIFIED, PACKAGE OK, SOURCE HEAD khớp 2e9cfc3; output xác nhận dynamic capacity + x10 remaining counter + serialized queue và clear-stall carryover purged, profile/settings cùng diagnostics được giữ. Đây chưa phải transaction/live workflow PASS; Gate vẫn READ_ONLY. NEXT mở Multi, vào game và chạy Gate 1 current runtime. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `1f84507`, `6bb263b`, `c508347` | Live build 4c4a809 package/V3 PASS nhưng output còn tuyên bố fixed 20 slots và giữ carryover. Verifier đã chuyển vào authoritative BUILD_FULL_PACKAGE.ps1 để cả đường PS5.1/direct đều bắt buộc chạy; builder purge state/carryover cũ nhưng giữ diagnostic runs, output đổi thành dynamic capacity+x10+serialized queue. Shared builder thay đổi chỉ ở preflight/data preservation; không đổi Workspace. Chưa live PASS cho build mới. |
| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `8820fd0`, `c387e3e`, `1e3e1d2` | Dọn quầy đã bỏ hẳn carry-over giữa chu kỳ. Thêm static contract kiểm tra syntax, READ_ONLY gate, đơn vị x10, tải lại quầy, nhà 1..N, concurrency=1; PS5.1 builder shared nay chạy verifier trước đóng gói và fail-fast nếu contract sai. Không đổi Workspace interface. Chưa live PASS; NEXT chạy Control Center [1] và lấy output `CLEAR STALL STATIC CONTRACT VERIFIED` + package build. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `bc1e398`..`82bcdd1` | Dọn quầy bỏ suy luận sức chứa cố định: target dùng bộ đếm VP còn thiếu, mỗi listing xác minh =10 VP; source đã có khung thoát/vào lại quầy và duyệt nhà 1..N, giới hạn lượt cấu hình. Scheduler khóa toàn máy một job; tài khoản đến hạn sau giữ due và hiển thị xếp hàng đến khi job trước thoát. Shared `kvtm_multi.py` chỉ đổi queue/UI semantics; không đổi Workspace interface. Mua/bán vẫn khóa READ_ONLY, chưa live PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `62d756a`, `3ad4ced`, `e855d9b` | Live Gate resident đã login/đóng popup/qua bạn/mở và kéo quầy/rồi về nhà; chưa PASS vì uploader PowerShell lỗi do caret và kéo 0.08s quá nhanh. Đã sửa SAFE uploader pipe parser; Gate v8 dùng đúng nhịp Tốc độ kéo quầy tham chiếu AUTO PRO 0.35s + settle 0.55s mỗi nửa bước, có log từng nhịp. Gate vẫn READ_ONLY, chưa mua/bán. Không sửa Workspace. NEXT: [1], [2], bấm Gate, [4] gửi log. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `71d2c32`..`69eee53` | GATE 1 Dọn quầy chuyển sang probe resident trong tiến trình Multi đã prewarm image runtime; bấm Gate tự ghi activity.log + report.json + PNG, không mở CMD phụ. Shared KVTM_DEV_CONTROL.bat mục [4] chỉ upload whitelist chẩn đoán lên diagnostics/clear-stall và vẫn gửi được activity.log nếu probe lỗi trước khi tạo report. Không upload profile/settings/.kvtm/secret. Chưa live PASS; NEXT: [1] cập nhật, [2] mở Multi, bấm Gate, rồi [4] gửi log. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `b464fe4`, `6d7800f`, `89a87be` | GATE 1 retest vẫn timeout đúng 60s, xác nhận background-thread native import deadlock chứ không phải cold-load chậm. Clean runtime nay import cv2→numpy→PIL đồng bộ trên worker main thread như AUTO PRO/package preflight; worker có watchdog ngoài 90s, os._exit chỉ process worker và emit lỗi trước navigation. Gate mua/bán vẫn khóa. Không sửa Workspace. Chưa live PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `d83d3a3`, `6446125` | GATE 1 live FAIL an toàn trước navigation: clean image runtime cold-load vượt timeout 15s trên Windows. Nâng giới hạn hữu hạn lên 60s, heartbeat 2s và log cold-load; không bỏ timeout, không mở gate mua/bán. Không sửa Workspace. NEXT: update/build và chạy lại GATE 1; nếu vẫn timeout cần log heartbeat/thời điểm thay vì tăng mù. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `e0d3417`..`b4c22bf` | Bắt đầu Dọn quầy clean theo nghiệp vụ user xác nhận. GATE 1 khóa cứng READ_ONLY_SCAN: worker luôn probe_only, chỉ vào đúng clone/bạn, quét 4 view/20 ô và lập kế hoạch ô×10; không thể mua/bán, không đóng clone sau probe. Quantity bắt buộc bội số 10 (10..1000), Multi hiển thị rõ gate và kết quả target. Có sửa shared kvtm_multi.py chỉ cho UI/gate event, không đổi Workspace interface. Tài liệu: docs/CLEAR_STALL_CLEAN_GATES.md. Chưa live PASS. NEXT: build [1], mở một clone vào game, đặt friend + quantity, bấm GATE 1 và gửi log/ảnh diagnostic. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `aceb706` + live | MỞ RƯƠNG CLIENTJS FULL LIVE PASS: user xác nhận bản có render-wait 4s + completion threshold 8.0 đã chọn rương, chờ ảnh/modal, mở được rương, không kẹt modal/không giật sau mở và AUTO tiếp tục. Phạm vi PASS chỉ openChests; nâng/cân bằng kho và reset/re-adopt PID vẫn cần live evidence riêng. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `c1287c9`, `efeec14` | Live retest sau render-wait vẫn kẹt tại “Chạm để mở rương”. Root cause: sau wait 4s, idle animation của rương làm mean frame difference vượt ngưỡng cũ 2.0; wrapper false-positive “đã mở”, chặn legacy replay dù modal còn nguyên. Giữ wait 4s nhưng completion threshold tăng 8.0, trace threshold; chỉ suppress post-open sau thay đổi modal lớn. Không sửa Workspace. Chưa live PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `19bd19d`, `7e54f66` | User cung cấp live timing: sau click chọn loại rương, ClientJS cần khoảng 3–5 giây để render ảnh rương/modal; click mở sớm làm kẹt. Patch thêm wait 4.0s interruptible đúng sau click chọn rương (371,647), chỉ một lần mỗi openChests call, có trace waited_seconds; sau đó mới chạy xác nhận tâm rương và post-open suppression. Không sửa Workspace. Chưa live PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `90a1dd7`, `a432a20` | Sau MỞ RƯƠNG live PASS xuất hiện lỗi mới: AUTO đứng/giật ở màn hình chính. Phân tích luồng bytecode cho thấy original_openChests vẫn phát lại click LD (433,557) sau khi wrapper ClientJS đã xác nhận modal đổi; click có thể lọt xuống home. Patch nay coi modal change là completion signal cho legacy ruong_go, chặn đúng post-open replay (433,557), trace suppression và luôn restore driver click trong finally. Không sửa Workspace. Chưa live PASS cho trạng thái sau mở rương. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `cf290c9` + live | MỞ RƯƠNG CLIENTJS LIVE PASS: user cập nhật runtime cf290c9, vào game, bật tùy chọn Mở rương và xác nhận rương thực sự mở. Fix luôn xác nhận mo_ruong theo ClientJS, ưu tiên tâm rương (500,470), giữ LD fallback. Phạm vi PASS chỉ mở rương; reset PID và nâng/cân bằng kho vẫn cần live evidence riêng. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `285bdf5`, `9fb5e91`, `6f3a45f` | Live chest retest tại runtime 2ee637e vẫn FAIL, modal “Chạm để mở rương” không đổi. Nguyên nhân patch cũ chỉ chạy fallback khi template mo_ruong không match; nếu template LD match thì ClientJS tiếp tục dùng click/điểm LD. Ảnh live mới xác định tâm rương được chọn gần (500,470) trong hệ 1000. Patch nay luôn chạy xác nhận ClientJS khi click mo_ruong, ưu tiên tâm rương (500,470), lặp tối đa 5 và dừng khi modal đổi; LD (433,557) chỉ fallback. Không sửa Workspace. Chưa live PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `3b28f03`, `2163099` | Live FAIL sau luồng mở rương: “ClientJS đã mở nhưng không nhận được màn hình game sau 180 giây”. Worker trước đây tạo EngineDriver từ PID nên việc khớp profile có thể thất bại; khi reset, driver không có identity bền vững để chuyển PID. Worker nay tạo EngineDriver bằng immutable profile_id DEV, còn FarmAutomation vẫn giữ device string tương thích; restart/rebind chỉ đúng profile đã chọn. Thêm CI guard, không sửa Workspace. Chưa live PASS. NEXT: [1] build, mở profile, chạy AUTO và xác nhận reset đổi PID nhưng profile trở lại Online/game trước timeout. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `f8df67e`, `f835deb` | Live FAIL mở rương ClientJS: đã chọn đúng rương nhưng đứng tại modal “Chạm để mở rương”. READ-ONLY bytecode AUTO PRO xác nhận LD lặp tối đa 5 click tại (433,557); ảnh ClientJS live cho thấy modal được render thấp hơn. Patch nay ưu tiên điểm ClientJS (500,660), lặp tối đa 5 lần và dừng ngay khi modal đổi; giữ điểm LD làm fallback, thêm CI guard. Không sửa Workspace. Chưa live PASS. NEXT: Control Center [1], mở lại Multi/client, bật Mở rương và xác nhận modal thực sự mở. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `bbb0b9f`, `5c1aeb5`, `733835f` | Đối chiếu READ-ONLY AUTO PRO ZIP: Tuychon đọc `time_nang_kho`/`balance_nang_kho`, Autonangkho nhận type số 1/2/3/4; worker trước đó truyền tên khác và type chuỗi. Đã map đúng, bind kill-switch mở rương, và cho Multi DEV isolated re-adopt PID mới chỉ khi khớp chính xác profile DEV; injection vẫn giới hạn self.processes nên không đụng client bộ cũ. Không sửa Workspace. Chưa live PASS. NEXT: build [1], chạy tùy chọn mở rương+nâng/cân bằng kho, reset ClientJS và xác nhận cùng profile tự Online với PID mới. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `6b9fc0c`, `40b8396`, `06e6221`, `51060e2`, `50db542` | READ-ONLY bytecode AUTO PRO LD xác nhận waypoint chỉ đầu/cuối tầng và uiautomator2 gửi một RPC với `steps=int(duration/0.005)`. V3 INPUT4 nay gửi một SWIPE batch, DLL nội suy theo bước 5ms; bỏ hoàn toàn sampling 8px/64px và hàng trăm pipe request. Có sửa shared `test-candidates/.../engine_driver.py`; không đổi Workspace/V1. Chưa runtime PASS. NEXT: Control Center [1] build, mở đúng một client DEV, live thu hoạch/trồng và xác nhận đủ 6 cây/tầng + telemetry batch. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `709723f`, `ada66fd`, `ec97104` | Thêm telemetry READ-ONLY cho từng `swipe_points`: caller, requested/actual duration, point count, pipe mode; worker phát `gesture_timing`, Multi hiển thị dòng timing. Mục tiêu xác định live vì sao UI harvest_speed đang thấy tác động ở makeItems nhưng chưa thấy ở harvestTrees/plantTrees. Có sửa shared `kvtm_multi.py` chỉ để hiển thị diagnostic; không đổi interface Workspace. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `c769752`..`94034da` + live | Production EngineDriver V3 LIVE PASS: đúng profile DEV, capture 1000x1000 trước/sau PASS; gesture 80px/0.500s thực tế 0.512134s, sai số +12.134ms, 11 điểm. Bridge V1 vẫn side-by-side cho Workspace. Gate transport/timing PASS; chưa suy diễn template/threshold/workflow nghiệp vụ AUTO PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `dc3d317`..`eb2171c` | Bridge V3 isolated đã live PASS capture 1000x1000 frame tăng và swipe 0.500s thực tế 0.513934s (+13.934ms). Đã chuẩn bị EngineDriver production V3: protocol/mapping/KCAP v3, strict no-HWND-fallback, tổng duration monotonic; PCDriver bỏ sleep DOWN/MOVE/UP; builder ship V1 và V3 side-by-side nên Workspace V1 chưa bị đổi. `[4]` khóa cứng đến package CI + live AUTO recognition PASS. |
| 2026-09-02 | AUTO/Multi | AUTO/Multi + Workspace | `13585a9`..`42d0678` | Khởi tạo Bridge V3 cô lập: DLL/loader x86 chỉ capture+input, protocol/KCAP v3 riêng; loại bỏ toàn bộ resize/DPI/layout/window placement; Python là timing owner duy nhất; thêm một `bridge-v3/KVTM_BRIDGE_V3_CONTROL.bat`, static/live probe, rollback, tài liệu chứa toàn bộ source và CI build x86. Runtime install vẫn LOCKED, chưa thay bridge production. Không sửa `components/workspace/**` hoặc `KVTM_WORKSPACE_CONTROL.bat`. NEXT: chờ CI thật; sau đó chạy BAT [3] capture và swipe 0.50s trên client DEV trước mọi cutover. |
| 2026-09-01 | AUTO/Multi | AUTO/Multi | `bdaed5a`, `6056d1c` | Theo quyết định người dùng, máy chính bỏ updater bên trong Multi. `[1]` của `KVTM_DEV_CONTROL.bat` nay pull + LFS + build runtime cố định bằng PS5.1 builder, bảo toàn data-dev/profile; Multi host không cài nút `Cập nhật DEV`. Lần bootstrap đầu có thể cần chạy `[1]` hai lần vì chính BAT được cập nhật ở lần đầu. Chưa live PASS. |
| 2026-09-01 | AUTO/Multi | Workspace | `2f4d127` | Live bridge mới đã trả frame nhưng Python từ chối `pixel_format=2` (BGRA8 top-down) do chỉ nhận `1`. Đã cho `Multi/pc_driver.py` nhận cả format 1/2; source native mới chủ động xuất format 2 sau chuẩn hóa ảnh. Chưa runtime PASS; NEXT: update runtime, restart toàn bộ và xác nhận `OpenGL shared`. |
| 2026-09-01 | AUTO/Multi | Workspace | `2714438` | Live evidence Workspace: bridge runtime cũ trả `ERR PARSE`, đỗ ClientJS ngoài desktop 4px/32px đều làm Cocos dừng render. Đã sửa `BUILD_FULL_PACKAGE.ps1` để build source bridge x86 có `CAPTURE1/KCAP`, xác minh binary và overlay vào `AUTO_PRO/bin` của runtime staging. Chưa runtime PASS; NEXT: cập nhật bằng nút `Cập nhật DEV`, đóng toàn bộ Multi + ClientJS để DLL cũ unload, mở lại và xác nhận Workspace hiện `OpenGL shared`. |
| 2026-09-01 | AUTO/Multi | AUTO/Multi phiên kế tiếp | `51c0fed`, `d734f5b`, `1fd34ec` | Đã xác định bằng READ-ONLY bytecode evidence rằng công thức `6 Tinh Dầu Hoa Hồng + 6 Vải Vàng + 8 Táo Sấy` là Function `98` (`produceItems_98`), không phải `97` vì `97` còn sản xuất Nước Hoa Hồng. Đã thêm catalog + worker allowlist + tài liệu. Chưa gọi runtime PASS; NEXT: pull DEV, mở Multi, xác nhận chức năng xuất hiện, chạy live trên đúng clone DEV và gửi log an toàn. |
| 2026-09-01 | AUTO/Multi | AUTO/Multi phiên kế tiếp | `4806e433`, `28209c3`, docs hiện tại | Migration máy phụ + GitHub bridge + runtime updater đã vào DEV. UI vị trí/chữ được user báo PASS. CI `4806e433` FULL PASS. Việc còn lại: live test 1 vòng chỉ bằng nút `Cập nhật DEV`, sau đó `[8]` xác minh `head == runtime_source_head`; không dùng `[9]` để che lỗi activation. Đọc `docs/SECONDARY_MACHINE_RUNTIME_UPDATE.md`. |
| 2026-09-01 | AUTO/Multi | Workspace | `feature/secondary-machine-migration` | Thêm riêng luồng chuyển máy/profile + machine setup. Không sửa `kvtm_multi.py`, capture, driver hoặc Workspace; Workspace không cần merge. |
| 2026-09-01 | AUTO/Multi | Workspace | `cf32eb0`, `70a5cc3` | SAFE Step 1 chỉ thay `ai-don-quay/step1_probe.py` và `KVTM_DON_QUAY_SAFE.bat`. Bổ sung identity fallback qua `running_clients.json` còn mới <=30 giây do Multi DEV publish; không đổi interface capture/driver/bootstrap và Workspace không cần merge. |
| 2026-09-01 | Workspace | AUTO/Multi | `addc02f` | Đã tách nhánh Workspace. Không yêu cầu merge. Xin giữ ổn định interface capture theo PID/HWND và báo SHA khi thay đổi. |
| 2026-09-01 | AUTO/Multi | Workspace | `a5b4310` | HEAD AUTO/Multi được quan sát khi tạo tài liệu; Workspace chưa lấy các thay đổi sau nền `f10d773`. Cần review diff trước khi đồng bộ. |

| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | `20260903-200838` live + source lifecycle | Dọn quầy FULL LIVE PASS: mua 100/100, thu vàng 16 ô, treo đúng 100/100, chuyển own-stall view bằng hai nhịp, giá không đổi, exit0. Source tiếp theo nối PASS accounting vào đóng đúng ClientJS, reset countdown từ finished_at và scheduler hàng đợi toàn máy; thêm backup local [B] cùng docs/CLEAR_STALL_AUTO_HANDOFF.md. Lifecycle/backup mới chờ build + live verify; không sửa Workspace. |

| 2026-09-03 | AUTO/Multi | AUTO/Multi + Workspace | source after `20260903-200838` live | Một lượt source sửa 4 nhóm: reset ClientJS nhận PID/bridge bằng 3 frame hợp lệ thay vì lệ thuộc 2 template; rương chờ modal ổn định 3–8s và xác nhận prompt/change; VongQuay giữ logic gốc rồi thoát overlay có xác nhận; Dọn quầy lặp nhà 1..N đến đủ target hoặc Stop, thêm whitelist GUI/runtime 5 VP (nước hoa hồng, tinh dầu hoa hồng, vải vàng, táo sấy, trà đá). GUI dành thêm chiều cao, verifier/docs cập nhật. Chưa LIVE PASS cho thay đổi mới; không sửa Workspace. |

## Mẫu cập nhật cho mỗi phiên

```text
SESSION: AUTO/Multi | Workspace
BRANCH: tên-nhánh
HEAD: SHA
STATUS: IN_PROGRESS | BLOCKED | READY_FOR_HANDOFF | VERIFIED
FILES_CHANGED: danh sách file
INTERFACE_CHANGED: không | mô tả cụ thể
TEST: lệnh/menu đã chạy và kết quả
NEXT: hành động tiếp theo
DO_NOT_TOUCH: file/phạm vi tạm khóa
```

## Điều kiện tích hợp Workspace

Chỉ đưa thay đổi Workspace về nhánh tích hợp sau khi đạt đủ:

- Multi mở được từ Control Center.
- Workspace nhận đúng client DEV, không nhận client bộ cũ.
- Live View hoạt động ở chế độ một Device và All.
- Thu nhỏ Workspace tối thiểu 5 phút không làm dừng Auto/ClientJS.
- Mở lại Workspace không đen hình, không sai tỷ lệ.
- Không chiếm chuột thật khi Auto chạy.
- Logs không chứa secret, cookie, session hoặc launch arguments đã giải mã.

## Cách tương tác với người dùng cho phiên AI tiếp theo

- Hướng dẫn ngắn, từng bước một.
- Ưu tiên command copy/paste chính xác.
- Không đưa 5-10 bước cùng lúc nếu chỉ cần một bước để lấy evidence tiếp theo.
- PASS/PARTIAL/FAIL chỉ theo log/CI/live evidence thật; không tự điền số liệu chưa thấy.

- 2026-09-05: Fixed silent AUTO stop after a successful ClientJS restart. Recovered FarmAutomation.start is continuous, but some recovered recovery paths may return after EngineDriver has rebound to a replacement PID while stop_event remains clear. The worker now resumes start only when that exact PID transition is proven; normal completion and user stop remain terminal. Event: worker_resumed_after_client_restart. Static contract and py_compile pass.

- 2026-09-05: Bridge V3 shared capture now treats an in-progress/changed frame as a transient renderer race. EngineDriver validates frame_id/status again after copying pixels and retries CAPTURE up to 12 times with 10 ms backoff. HWND fallback remains disabled; immutable profile/PID binding is unchanged. py_compile and full static contract pass.

- 2026-09-05: Multi DEV now exposes AUTO PRO Function 0 as “Cào Cây Event - Cây Sao”. The worker allow-list includes 0 and GuiProxy.get_wait_time returns numeric zero for the optional post-event delay used by recovered produceItems_0. The workflow remains AUTO PRO-native: cay_ong_sao, floors 1..5 and 6..10, plant/harvest cycle. No profile, login, Workspace, or coordinate logic changed. py_compile, JSON parse, and static contract pass.

- 2026-09-05: Began the clean AUTO PRO reconstruction surface inside Multi DEV. The AUTO CLIENTJS feature row is now a horizontally scrollable center strip with fixed themed left/right arrow buttons. “AUTO MULTI DEV” is immediately after “Chức năng chính” and opens an isolated clean-runtime scaffold; existing AUTO PRO execution remains unchanged as the migration reference. No profile, login, Workspace, or recovered runtime was removed. py_compile and full static contract pass; live Windows GUI verification remains required after [1].

- 2026-09-05: First executable clean AUTO layers added beside the clean Dọn quầy Python package. Multi AUTO MULTI DEV now launches/stops clean_auto_worker.py for checked, running, non-busy profiles. GameSessionWorkflow connects the clean KVAutomation stack, enters the ClientJS portal/game, dismisses AUTO PRO-derived template-guarded x/lv_up/quay_hang popups, and requires the clone main screen before PASS. Clean driver identity is profile_id + active profiles.json; ProfileProcessResolver matches game_dir and in-memory DPAPI-decrypted launch args, never logs secrets. On ClientJS restart CocosBridgeDriver waits up to 120s for that exact replacement PID, resets capture capability, reinjects/reconnects Bridge, then continues. Legacy automation.pyc remains reference only and is not imported by clean_auto_worker. Syntax parse PASS for 10 clean/source verifier files. GitHub Actions currently reports infrastructure/config startup failure with zero executed steps, so CI is NOT PASS; Windows [1] build and live session verification required.


## 2026-09-05 — AUTO MULTI DEV clean image-runtime startup fix

- User live symptom: clicking “Vào game + đóng popup” stopped at the OpenCV import status, so no game input or popup action was reached.
- The AUTO PRO third-party image runtime is now synchronized into the packaged AUTO_PRO tree once during `[1]` build.
- Clean workers no longer import `local_launcher`; that launcher performs runtime file copies and loads legacy GUI/business modules.
- At button runtime, the clean worker only registers packaged DLL/search paths and imports the already-present cv2/numpy/PIL files.
- A 90-second startup watchdog terminates a stuck image-runtime worker with an explicit error instead of leaving the GUI indefinitely busy.
- Python syntax: PASS for `runtime/bootstrap.py` and `worker/clean_auto_worker.py`.
- Windows PS5.1 build and live ClientJS navigation remain required before declaring end-to-end PASS.


## 2026-09-05 — AUTO sạch mở/nhận lại ClientJS từ chính nút Vào game

- `_start_clean_auto_session` quét lại các `GameClientJS.exe` và nhận đúng profile/PID ngay khi bấm, không chờ bridge monitor định kỳ.
- Nếu profile đã chọn thật sự offline, nút `Vào game + đóng popup` tự mở đúng ClientJS/profile trước khi tạo worker.
- Tách báo lỗi: tài khoản đang có worker và ClientJS mở thất bại; không còn gộp sai thành `bận/offline`.
- Giữ nguyên profile/secret; worker vẫn xác nhận lại đúng PID/profile và Bridge sau khi ClientJS restart.
- Python syntax: PASS. Windows live verification: pending operator test after `[1]`.


## 2026-09-05 — Chuẩn hóa Clean Main dùng runtime resident chung

- Người dùng xác nhận AUTO MULTI DEV và Dọn quầy là hai Main chính của dự án từ thời điểm này.
- Chọn kiến trúc ít thay đổi/rủi ro nhất: tiếp tục một image runtime resident đã có và đã được Dọn quầy dùng trong tiến trình Multi DEV; không tạo thêm runtime service/process trùng lặp.
- AUTO MULTI DEV trong `MultiDevApp` nay chạy `GameSessionWorkflow` bằng context/thread riêng với `KVAutomation(..., image_runtime_ready=True)`; không spawn `clean_auto_worker.py`, không cold-load lại cv2/numpy/PIL khi bấm.
- Runtime vẫn nạp một lần trước GUI. Mỗi profile độc quyền giữa AUTO MULTI DEV/Dọn quầy/AUTO cũ; Dọn quầy vẫn tối đa hai profile độc lập.
- Stop-event, work-dir, PID/profile identity và Bridge rebind riêng cho từng tác vụ. Đóng Multi phát stop cho cả hai nhóm resident task.
- `clean_auto_worker.py` chỉ còn CLI/fallback diagnostic, không phải đường Main DEV.
- Tài liệu chuẩn: `docs/CLEAN_MAIN_ARCHITECTURE.md`. Verifier đã khóa resident reuse/per-profile exclusivity/stop registry.
- AST syntax PASS cho DEV entry và verifier. Windows build/live chưa xác nhận; không gọi runtime PASS.


## 2026-09-05 — Chặn false PASS khi Bảng tin sự kiện còn mở

- Live evidence: AUTO MULTI DEV báo PASS trong khi modal `BẢNG TIN SỰ KIỆN` không có nút X vẫn phủ màn hình; HUD phía sau làm main-screen templates match sai.
- Popup clean thêm guard hình học: khung sáng trung tâm + backdrop tối, không lệ thuộc OCR/chữ hoặc ảnh cắt.
- Khi nhận diện, runtime click điểm backdrop an toàn `(500,185)`, chụp lại và chỉ coi đã đóng khi modal geometry biến mất.
- `is_own_main_screen` trả False khi modal còn tồn tại, nên không thể phát PASS giả.
- Heuristic chạy trên frame live người dùng gửi: bright_ratio=0.8377, background_mean=49.69, đạt guard.
- AST syntax PASS cho popup.py và verifier. Windows click/close live vẫn cần test sau `[1]`.


## 2026-09-05 — Popup policy tổng quát cho hai Clean Main

- Không duy trì allow-list theo tên cho popup sự kiện thay đổi. Template biết trước chỉ là đường ưu tiên.
- Guard tổng quát nhận diện blocker từ vùng trung tâm nổi bật trên backdrop tối; popup không có X được thử đóng ở backdrop an toàn và bắt buộc capture lại để xác nhận.
- Popup lạ không đóng được giữ trạng thái blocked/timeout; không PASS giả và không click mù vào nút nghiệp vụ/phần thưởng.
- `is_own_main_screen` không thể PASS khi generic blocker còn tồn tại. Áp dụng chung AUTO MULTI DEV và Dọn quầy.
- Frame live Bảng tin sự kiện đạt generic guard: bright_ratio=0.3642, outer_mean=39.54, center_mean=123.47.
- AST syntax PASS cho popup.py và verifier; live Windows pending.


## 2026-09-05 — Hai log riêng cho AUTO MULTI DEV

- Tab AUTO MULTI DEV có `Log hành động` và `Log chi tiết`, mở thành hai cửa sổ nền tối/font Consolas, live-tail 500ms như hai console AUTO PRO tham chiếu.
- Mỗi profile/mỗi run lưu riêng tại `data-dev/auto-multi-dev/<profile>/<run>/action.log` và `detail.log`.
- Action log chỉ nhận stage/nghiệp vụ/retry/kết quả. Detail log nhận Bridge/PID/capture và mọi template match gồm context, score, threshold, zone, scale, PASS/FAIL.
- Writer che các trường password/token/cookie/authorization/secret/launch_args trước khi ghi.
- Hai module mới có `FILE_FUNCTIONS` và `__all__`, dưới giới hạn 10 chức năng/file. Builder và static verifier bắt buộc đóng gói/kiểm tra cả hai.
- AST syntax PASS cho 8 file Python liên quan. Windows GUI/live log pending sau `[1]`.


## 2026-09-05 — Module nhận diện VP AUTO Main READ-ONLY

- Ba mẫu đầu tiên theo user: Táo sấy (`tao_say`/`kho_tao_say`), Vải vàng (`vai_vang`/`kho_vai_vang`), Tinh dầu hoa hồng (`tinh_dau_hh`/`kho_tinh_dau_hh`). Không thêm vật phẩm vàng riêng.
- Thêm `actions/item_recognition.py` dùng lâu dài, không phải module tạm; có `FILE_FUNCTIONS`, `__all__`, năm trách nhiệm.
- Thêm `workflows/vp_recognition`: vào home, mở own stall, mở kho thành phẩm, scan ba mẫu không click item/không đặt bán, luôn đóng dialog trong finally.
- Nút `Kiểm tra nhận diện VP (READ-ONLY)` chạy trên resident runtime; action/detail logs ghi kết quả và từng score/threshold//zone PASS/FAIL.
- Static contract khóa ba item, `click=False`, read_only=True và resident wiring. AST syntax PASS cho chín file liên quan; Windows live pending.


## 2026-09-05 — VP READ-ONLY thu vàng trước khi mở kho

- Live FAIL: NoEmptyStallSlot vì probe tìm ô trống trước khi thu vàng các ô đã bán.
- Workflow mới mở own stall, duyệt đủ bốn view và thu vàng, rewind về view đầu, rồi tìm ô trống qua tối đa bốn view để mở kho.
- Chỉ khi đã thu/quét đủ bốn view mà vẫn không có ô trống mới báo NoEmptyStallSlot rõ ràng.
- `collected_gold_slots` được trả trong result và ghi action log. Nhận diện item vẫn click=False/không đặt bán.
- AST syntax PASS cho workflow và verifier; live Windows pending.


## 2026-09-05 — Own-stall order corrected to one per-view loop

- Authoritative order: open own stall; on the current view collect gold; sell VP into the freed slot; perform exactly two swipe pulses; scan the next view; then repeat collect/sell through the final view.
- The rejected two-pass design (collect all views, rewind, then seek empty slots) is forbidden by the static contract.
- The current VP probe follows the same per-view transaction skeleton but remains READ_ONLY: inventory recognition replaces the real sell click until live recognition is confirmed PASS.
- The probe always closes an opened inventory and the clone's own stall; profile storage remains READ_ONLY.
- Static syntax verification: PASS. Live ClientJS verification: PENDING.


## 2026-09-06 — AUTO MULTI DEV: lớp bán VP chính tách biệt Dọn quầy

- Người dùng xác nhận Dọn quầy đang ổn định và chuyển sang theo dõi; mọi thay đổi có thể chạm phần ổn định phải được báo và giải thích trước.
- Thêm nút riêng `▶ Bán VP AUTO` trong tab AUTO MULTI DEV. Nút vào game/đóng popup và probe READ-ONLY vẫn giữ nguyên.
- Luồng mới: về home, mở quầy clone; từng view thu vàng nếu có; mở ô trống; chỉ nhận diện Táo sấy, Vải vàng hoặc Tinh dầu hoa hồng; chọn match tốt nhất; treo bằng cổng xác minh screen-change; kéo đúng hai swipe; lặp tối đa bốn view.
- Nếu view không còn ô trống thì chuyển view; nếu kho không còn ba VP được phép thì dừng treo an toàn. Không click vật phẩm không nhận diện.
- Logic nằm riêng tại `actions/auto_main_selling.py` và `workflows/auto_vp_sale/`. Không sửa `selling.py`, `stall.py`, `clear_stall_probe_runtime.py`, hàng đợi hoặc kế toán Dọn quầy.
- Chạm dùng chung có giới hạn: thêm một nút trong khối GUI AUTO MULTI DEV, thêm nhãn log tùy ngữ cảnh với mặc định tương thích, và thêm verifier vào build.
- Mỗi file Python mới có `FILE_FUNCTIONS`, không quá 10 trách nhiệm. AST syntax PASS; static contract được khóa bởi `tools/verify_auto_main_sale_contract.py`. Windows [1] build và live sale vẫn cần người vận hành xác minh trước khi gọi runtime PASS.


## 2026-09-06 — AUTO Main sửa xác nhận giả khi chọn kho thành phẩm

- Live log cho thấy `InventoryActions.select_storage(2)` ghi “Đã chọn” ngay sau click dù chưa xác minh tab giỏ hàng đã mở; AUTO quét sớm và kết luận sai ba VP đều NOT_FOUND.
- Không sửa `inventory.py` vì đây là lớp dùng chung với Dọn quầy đang theo dõi ổn định.
- `auto_main_selling.py` nay bấm trực tiếp nút kho thành phẩm số 2/biểu tượng giỏ hàng tại điểm AUTO PRO 1000x1000 `(450, 442)`, chờ render và quét tối đa ba fresh frame.
- Log chỉ nói “đã bấm nút” thay vì báo chọn thành công giả. Chỉ kết luận `NO_ALLOWED_ITEM` sau ba lượt không nhận ra VP.
- Static contract cấm AUTO Main quay lại dùng `self.inventory.select_storage()`. AST syntax PASS; live Windows cần chạy lại sau `[1]`.


## 2026-09-06 — AUTO Main bán cân bằng ba VP, bắt buộc lô x10

- Quy tắc người dùng xác nhận: bán luân phiên Táo sấy → Vải vàng → Tinh dầu hoa hồng → lặp lại.
- Sau khi chọn vật phẩm và mở dialog đặt bán, AUTO bắt buộc thấy marker `sl10`. Marker được thử tối đa ba fresh frame để tránh loại nhầm khi UI đang render.
- Nếu loại hiện tại còn 1..9, AUTO hủy dialog, đánh dấu loại đó không còn lô x10 trong lượt chạy và chuyển ngay sang loại kế tiếp; không thử lại loại đã thiếu.
- Dừng khi quầy hết ô trống hoặc cả ba loại đều không còn lô x10. Chỉ ghi nhận sau khi screen-change vượt ngưỡng xác minh.
- Action log dùng câu AUTO Main và tên VP thật; không còn phát câu `CLEAR_STALL resale` / `VP đã mua` cho luồng này.
- Kết quả có kế toán riêng `sold_by_item` và tổng kết số lô x10 của từng VP.
- Thay đổi chỉ ở `auto_main_selling.py`, `auto_vp_sale/workflow.py` và verifier AUTO Main; không sửa các file runtime Dọn quầy ổn định.
- AST syntax PASS; Windows live cần chạy lại sau `[1]`.


## 2026-09-06 — Khóa giao dịch AUTO Main sau live sai VP/dưới x10

- Live evidence: AUTO đã treo nhầm một VP gần giống và treo các stack x3/x7. Nguyên nhân: match trong kho chưa được kiểm tra lại sau click; template `sl10` dùng threshold 0.62 chỉ là match hình ảnh nên có thể PASS nhầm chữ số 1..9.
- Quy tắc chuẩn: tồn kho mỗi VP phải >=10; dialog bán phải mặc định hiển thị chính xác 10 trước khi được phép đặt bán.
- Thêm post-selection guard trong vùng icon lớn của dialog: template `tao_say`, `vai_vang` hoặc `tinh_dau_hh` phải khớp đúng loại đã chọn. Sai loại thì hủy dialog và khóa loại đó trong lượt.
- Marker số 10 tăng threshold lên 0.95 và phải PASS hai frame liên tiếp trong tối đa ba lần. Không đạt thì hủy, đánh dấu loại dưới x10 và chuyển loại khác.
- Chỉ khi cả item guard và exact-10 guard PASS mới bấm Đặt bán; screen-change verification vẫn là cổng kế toán cuối.
- Thay đổi chỉ trong action/workflow/verifier AUTO Main. Không sửa Dọn quầy.
- Log mới người dùng gửi lúc 12:57 kết thúc bằng `AutomationStopped` do yêu cầu dừng, không phải crash Bridge.


## 2026-09-06 — AUTO Main tiếp tục đủ ba VP sau một loại dưới x10

- Live run 13:08: Táo sấy được phát hiện còn 5 và exact-x10 guard đã chặn đúng, nhưng action quay lại tìm ô trống khi dialog/kho còn mở nên trả sai `NO_EMPTY_SLOT`; workflow bỏ qua hai loại còn lại.
- Sửa transaction scope: click ô trống đúng một lần, mở kho một lần, rồi kiểm tra tối đa đủ ba loại trong cùng chức năng.
- Khi một loại dưới x10 hoặc sai icon, nhấn Back để hủy dialog; bắt buộc xác minh `dat_ban` biến mất và `kho_thanh_pham` vẫn hiện trước khi chọn loại kế tiếp.
- Nếu không chứng minh được đã trở lại kho sau ba lần thì dừng bằng ScreenTimeout, không thao tác mù.
- Chỉ kết luận hết lựa chọn sau khi đã kiểm tra đủ ba loại hoặc cả ba đã bị đánh dấu thiếu/không an toàn.
- Không sửa workflow/runtime Dọn quầy.


## 2026-09-06 — AUTO Main: lớp trồng 27 cây Hoa hồng

- Đối chiếu trực tiếp AUTO PRO trong `source-archive/auto-pro-reference/recovery_notes/raw_marshal/constants.marshal` và `automation.marshal`.
- Khóa đúng hình học gốc 1000x1000: start `(325,799)`; tầng 1..5 có Y `940,725,505,280,40`; đường 27 cây là 4 tầng đủ 24 chậu và ba chậu tầng 5, kết thúc `(578,40)`.
- Runtime thực tế bắt đầu swipe tại tâm template `cay_hong`, sau đó đi qua các waypoint; threshold hạt Hoa hồng 0.87 và vùng search-gieo `(179,773,230,166)`.
- Thêm module riêng `actions/planting.py`, workflow `auto_planting`, nút thử riêng `Trồng 27 Hoa hồng` và static contract trong build.
- Fail-closed: nếu chậu đầu có cây chín, không nhận ra hạt hoặc không mở được bảng gieo thì dừng, không kéo mù.
- Không sửa `auto_main_selling.py`, `auto_vp_sale`, `stall.py`, Dọn quầy, queue, bridge hay driver.
- Static contract/syntax cần build Windows xác nhận; LIVE planting PENDING.


## 2026-09-06 — Sửa lớp trồng: định vị tầng và kiểm tra trạng thái chậu

- Live FAIL 14:44: luồng vào farm PASS nhưng chưa thực hiện bước `goUp(4)` của AUTO PRO.
- Đối chiếu `produceItems_293`: trước `plantTrees(cay_hong, num_tree=27, gieo_tang=1, next_gieo_trai)` có `goUp(4)`.
- Module nay đóng panel cạnh `(975,316)`, kéo `(387,69)->(387,918)`, rồi click chậu đầu `(388,946)`.
- Phải nhận ra `harvestBasket` threshold 0.80 hoặc `next_gieo_trai` threshold 0.70 trên cùng fresh frame.
- Nếu cây chín thì thu hoạch đúng đường 27 chậu và quét lại; chỉ khi chậu trống mới gieo.
- Chỉ sửa module/verifier trồng và tài liệu; không sửa bán VP, Dọn quầy, GUI, queue, bridge hoặc driver.
- Static syntax PASS; Windows build/LIVE retest PENDING.


## 2026-09-06 — Loại false PASS và bỏ goUp(4) thừa trong Clean Main

- Live 14:52 báo `planted=27/27` dù người vận hành xác nhận camera đã bỏ qua khoảng hai tầng.
- Nguyên nhân: `goUp(4)` trong AUTO PRO là thao tác tương đối phụ thuộc trạng thái camera của chuỗi sản xuất cũ; Clean Main vừa vào farm đã có mốc tầng 1 nên gọi lại làm lệch mốc.
- Lớp trồng không gọi `goUp(4)` nữa; giữ mốc farm vừa được `ensure_main_screen` xác nhận và kiểm tra trực tiếp chậu đầu `(388,946)`.
- Bổ sung cổng hậu kiểm 27 vùng chậu: tối thiểu 20/27 vùng phải thay đổi sau swipe. Không đạt thì ScreenTimeout, tuyệt đối không ghi `planted=27/27`.
- Chỉ sửa planting/verifier/docs; bán VP, Dọn quầy, GUI, queue, Bridge và driver không đổi.
- Static syntax PASS; LIVE retest PENDING.


## 2026-09-06 — Chốt định vị trồng từ Clean Main bằng goUp(1)

- Live 14:59 khi bỏ toàn bộ goUp: năm lần click `(388,946)` đều không thấy `harvestBasket` hoặc `next_gieo_trai`; người vận hành xác nhận game vẫn ở màn hình chính.
- Đối chiếu chuỗi AUTO PRO: ngay sau trạng thái `goDownLast`, lượt gieo đầu gọi `goUp(1)` rồi mới `plantTrees(... gieo_tang=1)`. `goUp(4)` chỉ xuất hiện ở đoạn sau khi camera đã bị các công đoạn khác di chuyển.
- Clean planting nay dùng đúng goUp(1): đóng panel `(975,316)`, swipe nhỏ `(514,214)->(514,314)`, chờ ổn định, chụp baseline rồi kiểm tra chậu đầu.
- Cổng xác minh cây chín/chậu trống và hậu kiểm tối thiểu 20/27 vùng chậu vẫn giữ nguyên.
- Chỉ sửa planting/verifier/docs; bán VP, Dọn quầy, GUI, queue, Bridge và driver không đổi.
- Static syntax PASS; LIVE retest PENDING.


## 2026-09-06 — Sửa ánh xạ giỏ thu hoạch trong Clean Vision

- Live 15:05: người vận hành nhìn thấy giỏ thu hoạch sau click chậu đầu nhưng action ghi UNKNOWN; đến lần 3 match `next_gieo_trai` rồi không thấy `cay_hong`.
- Nguyên nhân xác định: AUTO PRO gọi khóa logic `harvestBasket`, nhưng `GameConstants` ánh xạ khóa đó tới file thật `assets/items/thu_hoach.png`. Clean `AssetLibrary.candidates` chỉ tra theo stem/tên file và không tự ánh xạ khóa.
- Planting dùng template thật `thu_hoach`, giữ threshold 0.80 và mở rộng scale 0.70..1.30.
- Trạng thái EMPTY nay cần đồng thời thấy `next_gieo_trai` và `cay_hong` trên cùng fresh frame; không còn nhận false empty khi giỏ thu hoạch đang mở.
- Không sửa AssetLibrary dùng chung, bán VP, Dọn quầy, GUI, Bridge hoặc driver.
- Static syntax PASS; LIVE retest PENDING.


## 2026-09-06 — Sửa hậu kiểm trồng false FAIL do shared capture buffer

- Live 15:29 xác nhận thu hoạch và trồng đúng, nhưng hậu kiểm báo `0/27`.
- Nguyên nhân: baseline giữ trực tiếp ndarray do shared capture trả về; frame kế tiếp có thể tái sử dụng/ghi đè cùng vùng nhớ, làm before và after trở thành cùng dữ liệu.
- Baseline và after nay bắt buộc `.copy()` ngay khi capture để tạo hai snapshot bất biến trước khi so sánh 27 vùng chậu.
- Không đổi thao tác goUp(1), nhận diện thu hoạch, đường kéo hay ngưỡng hình ảnh; không sửa bán VP, Dọn quầy, GUI, Bridge hoặc driver.
- User live xác nhận nghiệp vụ thu hoạch + trồng PASS; hậu kiểm mới cần retest sau build.


## 2026-09-06 — Bỏ cổng lỗi sai dựa trên waypoint của đường swipe

- Live 15:37 lần thứ hai xác nhận game thu hoạch và trồng đúng, nhưng `changed_pots=0/27` vẫn phát ScreenTimeout.
- Kết luận: các điểm trong `FARM_PATH_27` là waypoint điều khiển đường swipe liên tục, không phải tâm hình học của 27 chậu. Dùng crop quanh waypoint để đếm chậu đổi trạng thái là mô hình sai.
- Giữ phép đo này ở detail log với `non_blocking=true` để chẩn đoán; tuyệt đối không dùng nó làm cổng FAIL.
- Cổng nghiệp vụ vẫn gồm: nhận đúng `thu_hoach`, thực hiện harvest path, nhận đồng thời `next_gieo_trai+cay_hong`, rồi thực hiện đúng swipe path 27.
- Hai lượt live 15:29 và 15:37 đã được người vận hành xác nhận thu hoạch/trồng đúng. Runtime planting transaction: PASS; heuristic waypoint: DISABLED_AS_GATE.
- Không đổi thao tác trồng đang PASS và không sửa bán VP, Dọn quầy, GUI, queue, Bridge hoặc driver.


## 2026-09-06 — Tách ba tốc độ độc lập cho AUTO MULTI DEV

- Đối chiếu AUTO PRO: `harvest_speed` cũ bị dùng chung cho kéo tầng và trồng/thu cây; `production_wait` là độ trễ sản xuất.
- AUTO MULTI DEV có ba khóa riêng: `floor_swipe_duration`, `plant_harvest_duration`, `vp_production_delay`.
- Mặc định bảo toàn tốc độ đã chạy PASS: kéo tầng 0.35s, trồng/thu 0.035s; sản xuất VP dùng mốc AUTO PRO 0.40s.
- GUI Cấu hình hiển thị ba dòng MULTI DEV riêng; khóa AUTO PRO cũ vẫn giữ để tương thích worker lịch sử.
- Runtime resident chụp snapshot cấu hình khi bắt đầu và ghi cả ba giá trị vào action log.
- Module trồng chỉ nhận hai tốc độ tương ứng. Tốc độ sản xuất VP được chuẩn hóa/lưu sẵn, chưa nối vào nghiệp vụ vì module sản xuất chưa xây.
- Không sửa logic bán VP, Dọn quầy, queue, bridge hay driver.
- Có static contract riêng và được chèn vào build trước đóng gói; Windows build/LIVE retest PENDING.


## 2026-09-06 — AUTO MULTI DEV: module chuyển tầng trước sản xuất VP

- Yêu cầu người dùng: hoàn thiện chuyển tầng chính xác trước khi xây module sản xuất VP, vì chỉ sau khi camera nằm đúng view mới được quét/chọn máy.
- Đối chiếu điểm LIVE đã PASS của AUTO PRO trong luồng trồng: một nhịp `goUp(1)` dùng tọa độ 1000x1000 `(514,214)->(514,314)`. Không dùng lại `goUp(4)` vì đã có bằng chứng live bỏ qua khoảng hai tầng.
- Thêm `actions/floor_navigation.py`: mỗi tầng đúng một swipe; hướng DOWN đảo đối xứng; tối đa năm tầng cho một yêu cầu; dùng riêng `floor_swipe_duration`.
- Mỗi nhịp bắt buộc chụp fresh frame trước/sau, chờ 0.65s và dừng trước khi quét/chọn máy nếu không thấy phản hồi hình ảnh.
- Module chỉ cung cấp primitive chuyển tầng `up/down/move`; module sản xuất kế tiếp phải quét máy sau từng tầng, không suy đoán máy theo số lần kéo.
- Wiring mới là `automation.floors` trong resident runtime. Không sửa `planting.py`, bán VP, Dọn quầy, queue, Bridge hoặc driver.
- Builder chạy `verify_auto_floor_navigation_contract.py`; static contract cấm `goUp(4)`, khóa hình học, giới hạn năm tầng và ranh giới an toàn trước sản xuất.
- Trạng thái: source/static ready; Windows build và LIVE chuyển tầng vẫn PENDING.


## 2026-09-06 — Nút Bắt đầu chuyển sang workflow tổng bán → trồng

- Live/GUI inspection xác nhận nút tổng trước đây vẫn chỉ gọi `GameSessionWorkflow`; ba workflow nghiệp vụ phụ thuộc cờ từ các nút thử đã bị xóa và dùng `if/elif`, nên không thể chạy tuần tự.
- Thêm `workflows/auto_main`: một lần bấm chạy vào game/đóng popup, gọi nguyên trạng `AutoVpSaleWorkflow`, sau đó gọi nguyên trạng `RosePlantingWorkflow`.
- Nếu bán hoặc trồng phát lỗi, exception chặn toàn chuỗi; không chuyển tầng/chọn máy tiếp. Khi cả hai hoàn tất mới phát `auto-main-production-ready`.
- DEV entry dùng `AutoMainWorkflow(automation).run()`; GUI báo tổng số ô bán, vàng thu và cây đã trồng. Các handler thử cũ còn tồn tại để tương thích source nhưng không còn nút GUI và không tham gia nút tổng.
- Static contract bán/trồng được chuyển từ wiring nút thử sang wiring workflow tổng. Nội bộ bán VP, trồng Hoa hồng và Dọn quầy không đổi.
- Thêm công cụ chỉ đọc `tools/inspect_autopro_production_reference.py` để trích `makeItems/goUp/goDownLast/produceItems_293` từ marshal AUTO PRO trước khi viết click máy sản xuất; không đoán tọa độ.
- Trạng thái: AST syntax PASS cho workflow, DEV entry và ba verifier; Windows build/LIVE pipeline PENDING. Sản xuất VP chưa được phép click cho tới khi trích xong reference.


## 2026-09-06 — AUTO MULTI DEV chức năng 1: 27 Táo → 9 Táo sấy

- Xác nhận kiến trúc: đây là AUTO MULTI DEV sạch hoàn toàn. AUTO PRO chỉ cung cấp bằng chứng đối chiếu tọa độ/thứ tự; runtime mới không gọi `makeItems`, `goUp`, `goDownLast` hay pyc cũ.
- Sửa công cụ trích xuất để quét toàn bộ `raw_marshal/*.marshal`; reference đầy đủ xác nhận máy sấy tầng 1 `(262,917)`, Táo sấy slot 0 `(252,421)`, điểm thả hàng chờ `(400,719)`, vùng tìm sản phẩm `(9,341,402,386)`.
- `PlantingActions` được tham số hóa tối thiểu: giữ nguyên `plant_27_roses()` đã PASS và thêm `plant_27_apples()`; cùng dùng hình học 27 chậu đã xác minh. Không sửa Dọn quầy hoặc bán VP.
- Thêm `ProductionActions`: chỉ mở máy tầng 1; bắt buộc nhận đúng `tao_say` threshold 0.95 và đếm được ít nhất 9 `o_trong` trước khi thao tác.
- Mỗi Táo sấy là một swipe riêng từ slot 0 tới hàng chờ; dùng `vp_production_delay` độc lập. Nếu hiện dấu lỗi nguyên liệu thì dừng ngay.
- Kế toán không dựa trên số lệnh đã gửi: sau 9 swipe, số ô trống phải giảm ít nhất 9 mới trả PASS.
- Thêm `AppleDryerWorkflow` và đổi nút tổng sang: bán VP ổn định → trồng/thu 27 Táo → sản xuất 9 Táo sấy. Kết quả GUI ghi riêng `planted_apples` và `dried_apples`.
- Builder chạy `verify_auto_main_production_contract.py`. AST PASS cho action, workflow, automation, DEV entry và toàn bộ verifier liên quan. Windows build/LIVE vẫn PENDING.


## 2026-09-06 — AUTO MULTI DEV là sản phẩm thay thế

- Tài liệu chuẩn bắt buộc: `docs/AUTO_MULTI_DEV_PRODUCT_ARCHITECTURE.md`.
- AUTO PRO chỉ là bằng chứng tham chiếu read-only và sẽ bị xóa sau khi Multi Dev live-stable.
- Asset nghiệp vụ thuộc `components/clientjs-auto/assets`; runtime lookup không fallback sang AUTO PRO.
- Ảnh debug chỉ là bằng chứng, không tự động trở thành template.
- Chuẩn hóa lỗi `fullkho` thành asset thật `full_kho`.
- Full Build chạy `verify_multi_dev_asset_contract.py`.
- Chức năng 1 vẫn là `9 Táo sấy → 9 Vải vàng`; hiện tiếp tục LIVE lớp sản xuất Táo sấy.


## 2026-09-06 — Mốc tiếp theo Chức năng 1: Nước táo

- Táo sấy đã LIVE PASS `9/9`: match `tao_say=1.000`, đường kéo động tới ô top và ô trống giảm `9→0`.
- Công thức tiếp theo: `36 Táo → 9 Nước táo` tại máy tầng 2 → `9 Vải vàng`.
- Hình học gieo: 5 tầng × 6 cây, sau đó từ tầng 1 lên tầng 6 và gieo thêm 1 hàng × 6 cây.
- Mốc hiện tại chỉ thêm nút demo độc lập `Demo tầng 1 → 6`; operator đặt clone ở tầng 1, demo chạy đúng 5 nhịp UP có hậu kiểm thay đổi frame.
- Ghi backlog: tách thao tác sửa quầy sau sản xuất thành module dùng chung cho tất cả máy rồi mới ghép vào các workflow.


## 2026-09-07 — Demo tầng 1 → 6 lần đầu NOT PASS

- Live log xác nhận bản cũ gửi 5 gesture rời `(514,214)→(514,314)`, mỗi gesture chờ `0.65s`; kết quả thực tế chỉ tới tầng 5.
- Sửa contract: từ màn hình chính cần sáu đơn vị tầng và phải lướt một mạch theo Auto Pro.
- Demo mới gọi `floors.glide_up(6)`, tạo đúng một gesture `(514,214)→(514,814)` rồi hậu kiểm frame một lần.
- Không được ghi LIVE PASS trước khi người dùng retest và xác nhận đang ở đúng tầng 6.


## 2026-09-07 — TẠM DỪNG: glide tầng 6 lần hai NOT PASS

- User retest commit `7e9f613`: một gesture `(514,214)→(514,814)` trong `0.060s` chỉ lên tầng 1, không phải tầng 6.
- Bridge đã gửi đủ `DOWN → MOVE 364/514/664/814 → UP`; `frame_change=75.49`. Điều này chứng minh input có phản hồi nhưng detector hiện tại đã báo PASS sai ngữ nghĩa vì không nhận dạng số tầng.
- Không sửa thêm trong phiên này. Nút demo vẫn là experimental và tuyệt đối không ghép pipeline.
- Trạng thái chức năng 1: bán VP/trồng 27 Táo/sản xuất Táo sấy đã đạt mốc trước; Táo sấy LIVE PASS `9/9`. Nước táo và Vải vàng chưa triển khai.
- NEXT: forensic `Auto Pro goUp(n)` chính xác; xác định cadence touch/gesture và bằng chứng tầng 6; sửa demo rồi LIVE retest.
- Backlog giữ nguyên: `36 Táo = 30 + 6 tầng 6`, máy Nước táo tầng 2, module sửa quầy dùng chung sau sản xuất.
