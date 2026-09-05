# KVTM Secondary Machine + Runtime Update

> Tài liệu vận hành và handoff cho luồng máy phụ của `develop/multi-auto-dev`.
> Không ghi secret/profile plaintext vào tài liệu, GitHub report hoặc CI.

## Phạm vi

Luồng này giải quyết 3 việc:

1. Chuyển profile Multi DEV từ máy chính sang máy phụ bằng gói `.kvtm` mã hóa và re-bind DPAPI trên máy đích.
2. Giao tiếp máy phụ với GitHub qua menu `[8]`/`[9]` mà không upload profile/secret.
3. Cập nhật DEV runtime từ GitHub bằng nút `Cập nhật DEV`, có staging và bảo toàn `data-dev`.

## Nhánh và đường dẫn chính

- Repository: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`
- DEV branch: `develop/multi-auto-dev`
- Machine report branch: `machine-sync/cry-pc`
- Repo máy phụ: `C:\Users\15130\Desktop\Tool_KVTM_Multi_DEV`
- Runtime cố định: `C:\Users\15130\Desktop\Tool_KVTM_Multi_DEV\dist\KVTM-ClientJS-Suite-Multi-DEV`
- Profile runtime: `...\data-dev\profiles.json`

## Menu máy phụ

`KVTM_MACHINE_TRANSFER_CONTROL.bat` có các mục quan trọng:

- `[7]` Xác minh profile/DPAPI READ-ONLY.
- `[8]` Gửi report máy phụ lên GitHub, chỉ SAFE diagnostic text.
- `[9]` Nhận cập nhật DEV từ GitHub, pull/deps/LFS/build runtime.
- Trong Control Center chính, `[M]` mở công cụ chuyển máy; tại đó `[4]` tự cài phần mềm còn thiếu, gồm Visual Studio C++ Build Tools x86/x64 khi source bridge mới cần biên dịch.

`[8]` ghi report vào:

`machine-reports/<COMPUTERNAME>/LATEST.txt`

trên branch `machine-sync/cry-pc`.

Report được lọc để không upload `.kvtm`, `profiles.json`, Authorization, password, cookie hoặc token.

## Trạng thái migration đã kiểm chứng

Máy chính đã export 13 profile thành công bằng `tools/KVTM_PROFILE_TRANSFER.ps1`.

Máy phụ đã import profile. Người dùng sau đó mở một profile và xác nhận **vào thẳng game, không yêu cầu đăng nhập lại**. Đây là runtime evidence thực tế cho ít nhất profile đã thử: DPAPI re-bind + launch args + ZingPlay session hoạt động trên máy phụ.

Không suy diễn rằng toàn bộ 13 profile đã được live-launch nếu chưa có test từng profile. Verifier `[7]` được người dùng báo `pass`, nhưng nếu cần số đếm chính xác thì yêu cầu output thật thay vì tự điền.

## Môi trường máy phụ đã xác minh

Fresh GitHub diagnostic đã từng xác nhận:

- Git: FOUND
- Git LFS: FOUND
- CPython 3.11 x64: FOUND
- VC++ runtime x64/x86: FOUND
- ZingPlay GameClientJS: FOUND
- ZingPlay game data: FOUND
- `RESULT=ENVIRONMENT_READY`

Diagnostic hiện có thêm:

- `runtime_source_head`
- `runtime_update_ui`
- `runtime_updater_hook`

để phân biệt repo source đã update với runtime thực tế đã được kích hoạt hay chưa.

## Runtime updater

Các file chính:

- `tools/KVTM_RUNTIME_UPDATE.ps1`
- `source-archive/multi-current/kvtm_multi_tool/runtime_update_ui.py`
- `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_host.py`
- `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`

### Cách hoạt động

Nút `Cập nhật DEV` nằm trong `BẢNG ĐIỀU KHIỂN` của Multi DEV.

Khi bấm:

1. updater kiểm tra branch `develop/multi-auto-dev` theo cách tương thích Windows PowerShell 5.1;
2. fetch/pull fast-forward source mới nếu local phía sau origin;
3. chạy Git LFS;
4. build runtime mới vào thư mục sibling staging `KVTM-ClientJS-Suite-Multi-DEV-UPDATE-<sha>`;
5. bảo toàn `data-dev`, đặc biệt `profiles.json` và `settings.json`;
6. nếu Multi đang chạy, runtime hiện tại tiếp tục chạy và bản mới ở trạng thái pending;
7. khi runtime cũ thật sự thoát, updater kích hoạt staging và giữ runtime trước đó ở `.previous` để rollback an toàn.

Không hot-swap Python/DLL đang được process hiện tại nạp.

Máy phụ không bắt buộc cài toàn bộ Visual Studio Build Tools chỉ để nhận một cập nhật
không thay đổi source bridge. Nếu compiler C++ vắng mặt (builder exit 20), builder chỉ
được tái sử dụng bốn binary bridge/loader từ runtime DEV hiện tại khi đồng thời:

- `.source-head.txt` trỏ tới một commit Git hợp lệ;
- sáu input source/build của capture bridge và Bridge V3 không đổi từ commit runtime đó
  tới HEAD mới;
- từng DLL/EXE hiện tại có chữ ký PE hợp lệ và machine `0x014c` (x86).

Nếu source bridge đã đổi, thiếu runtime cũ hoặc binary không đạt kiểm tra, build phải dừng
và yêu cầu Visual Studio C++ Build Tools; không được âm thầm đóng gói DLL cũ.

### Các lỗi đã sửa

- Windows PowerShell 5.1 làm `$LASTEXITCODE` stale sau pipeline `Select-Object`, gây false-negative branch/HEAD. Đã sửa bằng cách capture native output và exit code trước khi pipe.
- Runtime source đã update nhưng UI/runtime chính vẫn cũ vì watcher kích hoạt staging chưa chắc chắn. Commit `4806e433591b8623126e11c6e13e6ac1adec5808` làm staged activation robust hơn: theo dõi đúng process/PID, retry activation khi file còn bị khóa và xử lý self-update của updater.
- Nút updater ban đầu nổi đè góc phải và status text bị mojibake. Commit `28209c3ab6a53cf90cbb232beecc646928571fa0` đưa nút vào control panel và chuẩn hóa/sửa text tiếng Việt.

## CI hiện tại

Commit `4806e433591b8623126e11c6e13e6ac1adec5808` đã PASS đầy đủ:

- Workflow `Multi DEV checks`
  - `clear-stall-static`: PASS
  - `package-smoke`: PASS
  - package build, privacy, giữ runtime data, clean Dọn quầy preflight và legacy suite preflight đều PASS.
- Workflow `Secondary machine checks`
  - PowerShell parse: PASS
  - runtime updater Python parse: PASS
  - PS5.1 JSON/native Git regression: PASS
  - staged runtime updater safety: PASS
  - GitHub bridge safety: PASS
  - transfer crypto smoke: PASS
  - read-only machine diagnostic: PASS
  - transfer artifacts ignored: PASS.

Không thay thế live Windows evidence bằng CI. CI PASS chỉ xác nhận static/package/regression scope nói trên.

## Live status gần nhất

Trước khi bootstrap lần cuối, report máy phụ cho thấy:

- repo/source đã ở `28209c3`;
- runtime vẫn ở `01690a5`;
- `runtime_update_ui=FOUND`;
- `runtime_updater_hook=FOUND`.

Sau đó người dùng chạy `[9]` và báo `pass`, mở lại Multi và báo **`giao diện pass`**: vị trí nút và chữ tiếng Việt đã đúng.

Chưa có GitHub diagnostic mới sau lời xác nhận `giao diện pass`, nên không tự ghi một SHA runtime mới từ suy đoán.

## Điểm cần test tiếp để chốt updater FULL PASS

Cần một vòng update hoàn toàn bằng **chính nút `Cập nhật DEV`**, không dùng `[9]`:

1. Có một commit mới trên `develop/multi-auto-dev` sau runtime hiện tại.
2. Giữ Multi DEV đang chạy và bấm `Cập nhật DEV`.
3. Xác nhận UI đi qua checking/pulling/building và tới trạng thái đã tải/chờ đóng nếu runtime đang chạy.
4. Đóng Multi bình thường.
5. Mở lại `02_START_MULTI_DEV.bat`.
6. Chạy `[8]`.
7. Chỉ chốt **FULL PASS** khi report mới xác nhận:
   - `head=<commit mới>`
   - `runtime_source_head=<cùng commit mới>`
   - `runtime_update_ui=FOUND`
   - `runtime_updater_hook=FOUND`
   - `RESULT=ENVIRONMENT_READY`
   và người dùng xác nhận Multi/profile vẫn hoạt động.

Nếu source HEAD mới nhưng `runtime_source_head` vẫn cũ, coi activation là FAIL/PARTIAL và debug staging/status/watcher; không bảo người dùng lặp `[9]` như giải pháp lâu dài.

## Quy tắc dữ liệu và bảo mật

Không yêu cầu người dùng gửi hoặc commit:

- password của gói transfer;
- file `.kvtm`;
- raw `profiles.json`;
- plaintext launch args;
- token/cookie/session/password.

`.kvtm` là local-only và phải bị `.gitignore` loại bỏ.

Updater/build phải giữ `data-dev`. Trước bất kỳ thay đổi có nguy cơ ghi đè runtime, ưu tiên staging + backup; không xóa profile để sửa updater.

## Quy tắc làm việc cho AI tiếp theo

- Đọc `AI_COORDINATION.md` và file này trước khi sửa.
- Làm việc trên `develop/multi-auto-dev` cho Auto/Multi.
- Không sửa `components/workspace/**` hoặc `KVTM_WORKSPACE_CONTROL.bat` nếu task không phải Workspace.
- Không gọi PASS nếu chỉ có build/CI mà thiếu live evidence cho hành vi Windows được hỏi.
- Người dùng thích hướng dẫn ngắn, từng bước một, command copy/paste chính xác.
- Khi user nói `[8] đã gửi`, đọc `machine-sync/cry-pc:machine-reports/CRY-PC/LATEST.txt` trước khi phán đoán.
