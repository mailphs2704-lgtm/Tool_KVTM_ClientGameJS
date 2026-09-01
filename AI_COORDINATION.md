# KVTM AI Session Coordination

> Tài liệu điều phối bắt buộc cho mọi phiên AI làm việc trên repository này.
> Đọc toàn bộ file trước khi sửa code. Cập nhật phần trạng thái của mình trước khi kết thúc một mốc công việc.

## Mục tiêu chung

Xây `KVTM-ClientJS-Suite` gồm Multi, ClientJS Workspace và Auto chạy nền ổn định. Workspace có thể thu nhỏ xuống taskbar mà ClientJS và Auto vẫn tiếp tục chạy. Mọi thao tác thử nghiệm phải chỉ tác động tới client thuộc bộ DEV hiện tại.

## Phân nhánh và quyền sở hữu

| Phiên | Nhánh làm việc | Phạm vi sở hữu chính | Không tự ý sửa |
|---|---|---|---|
| AUTO/Multi | `develop/multi-auto-dev` | Logic Auto, workflow Dọn quầy, Multi hiện tại, profile/session, worker và probe | `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat` |
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
7. Không coi build thành công là runtime PASS. Chỉ ghi PASS khi có output kiểm thử trên Windows của người dùng.

## Trạng thái phiên AUTO/Multi

- Nhánh chính: `develop/multi-auto-dev`.
- HEAD nhánh chính quan sát khi bắt đầu mốc chuyển máy: `e58d03a`.
- Nhánh triển khai cô lập hiện tại: `feature/secondary-machine-migration`.
- Chủ sở hữu cập nhật: phiên AI đang làm Auto/Multi.
- Trạng thái: `IN_PROGRESS` — bổ sung luồng chuyển profile sang máy phụ, chẩn đoán môi trường và cài dependency; chưa ghi runtime PASS.
- Mốc vừa hoàn thành: thêm module mới, không sửa `kvtm_multi.py`, driver/capture/bootstrap Dọn quầy hay Workspace. Export giải DPAPI trên máy nguồn trong bộ nhớ rồi mã hóa portable; Import xác thực HMAC, mã hóa lại DPAPI cho Windows user máy đích và backup profile trước khi ghi. Machine diagnostic kiểm tra Git/Git LFS/Python 3.11 x64/VC++ x86+x64/ZingPlay/GameClientJS/game data/DEV runtime; các dependency có package ổn định được cài qua WinGet.
- File mốc này: `tools/KVTM_PROFILE_TRANSFER.ps1`, `tools/KVTM_PROFILE_VERIFY.ps1`, `tools/KVTM_MACHINE_SETUP.ps1`, `KVTM_MACHINE_TRANSFER_CONTROL.bat`, `KVTM_SECONDARY_BOOTSTRAP.ps1`, `.gitignore`.
- Interface Workspace thay đổi: không.
- Test: static review/compare Git; chưa có PowerShell/Windows runtime verification. Không gọi PASS trước khi người dùng chạy export/diagnostic/import trên Windows.
- Next: đưa feature về `develop/multi-auto-dev` bằng fast-forward nếu nhánh chính chưa thay đổi; người dùng pull máy chính, chạy `KVTM_MACHINE_TRANSFER_CONTROL.bat` -> Export và diagnostic. Sau đó chạy bootstrap/diagnostic trên máy phụ rồi Import, gửi output verify nếu có lỗi.
- DO_NOT_TOUCH: `components/workspace/**`, `KVTM_WORKSPACE_CONTROL.bat`; không thay đổi logic Dọn quầy/capture/driver trong mốc chuyển máy này.
- Yêu cầu với phiên Workspace: không cần merge; feature chuyển máy không đổi interface Workspace/capture.

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
|---|---|---|---|---|
| 2026-09-01 | AUTO/Multi | Workspace | `feature/secondary-machine-migration` | Thêm riêng luồng chuyển máy/profile + machine setup. Không sửa `kvtm_multi.py`, capture, driver hoặc Workspace; Workspace không cần merge. Chưa runtime PASS trên Windows. |
| 2026-09-01 | AUTO/Multi | Workspace | `cf32eb0`, `70a5cc3` | SAFE Step 1 chỉ thay `ai-don-quay/step1_probe.py` và `KVTM_DON_QUAY_SAFE.bat`. Bổ sung identity fallback qua `running_clients.json` còn mới <=30 giây do Multi DEV publish; không đổi interface capture/driver/bootstrap và Workspace không cần merge. |
| 2026-09-01 | Workspace | AUTO/Multi | `addc02f` | Đã tách nhánh Workspace. Không yêu cầu merge. Xin giữ ổn định interface capture theo PID/HWND và báo SHA khi thay đổi. |
| 2026-09-01 | AUTO/Multi | Workspace | `a5b4310` | HEAD AUTO/Multi được quan sát khi tạo tài liệu; Workspace chưa lấy các thay đổi sau nền `f10d773`. Cần review diff trước khi đồng bộ. |

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

## Điều kiện tích hợp

Chỉ đưa thay đổi Workspace về nhánh tích hợp sau khi đạt đủ:

- Multi mở được từ Control Center.
- Workspace nhận đúng client DEV, không nhận client bộ cũ.
- Live View hoạt động ở chế độ một Device và All.
- Thu nhỏ Workspace tối thiểu 5 phút không làm dừng Auto/ClientJS.
- Mở lại Workspace không đen hình, không sai tỷ lệ.
- Không chiếm chuột thật khi Auto chạy.
- Logs không chứa secret, cookie, session hoặc launch arguments đã giải mã.
