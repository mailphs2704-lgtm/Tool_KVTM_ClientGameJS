# KVTM ClientJS Auto – Setup, lifecycle và bàn giao AI

> Nhánh chuẩn: `develop/multi-auto-dev`  
> Giao diện vận hành duy nhất: `KVTM_DEV_CONTROL.bat`  
> Không sửa `components/workspace/**` hoặc `KVTM_WORKSPACE_CONTROL.bat` trong tác vụ AUTO/Multi.

## 1. Trạng thái đã xác minh

Run Windows `20260903-200838` đã LIVE PASS toàn bộ Dọn quầy:

- target 100 VP = 10 ô x10;
- mua được 100/100 VP;
- thu vàng 16 ô;
- treo lại đúng 100/100 VP đã xác minh mua trong chính lượt đó;
- quầy nhà đầy ở view 1 thì kéo đúng hai nhịp, scan/thu vàng rồi treo tiếp ở view 2;
- không thay đổi giá;
- `probe_ok`, `returncode=0`.

Đây là bằng chứng live cho giao dịch. Static/CI không được dùng thay thế bằng chứng Windows này.

## 2. Cài đặt và mở chương trình

Yêu cầu máy:

- Windows 10/11;
- CPython 3.11 x64;
- Git + Git LFS;
- VC++ runtime x86/x64;
- GameClientJS/ZingPlay;
- repository đã checkout đúng nhánh `develop/multi-auto-dev`.

Quy trình duy nhất:

1. Mở `KVTM_DEV_CONTROL.bat`.
2. Chọn `[1]` để pull fast-forward, Git LFS và build runtime cố định.
3. Chọn `[2]` để mở Multi DEV nền.
4. Trong Multi chọn profile, mở tab **Dọn quầy**, cấu hình rồi bật lịch.

Runtime cố định:

`dist\KVTM-ClientJS-Suite-Multi-DEV`

Dữ liệu local cần bảo toàn:

- `data-dev\profiles.json`;
- `data-dev\settings.json`;
- profile/session được mã hóa bằng Windows DPAPI.

Không gửi các file này lên GitHub hoặc cho AI.

## 3. Cấu hình Dọn quầy

- **Số nhà cần duyệt**: đi lần lượt nhà 1 đến N.
- **Kho VP**: kho dùng để chọn lại đúng VP đã mua.
- **Số lượng mua**: đơn vị VP, bắt buộc bội số 10.
- **Quét tối đa**: số lần tải lại trong một lượt ghé mỗi nhà; hết lượt mà chưa đủ thì bắt đầu vòng nhà mới, không kết thúc job.
- **Chỉ mua VP**: chọn ít nhất một trong 5 loại: Nước hoa hồng, Tinh dầu hoa hồng, Vải vàng, Táo sấy, Trà đá.
- **Chu kỳ**: phút chờ tính từ lúc vòng trước hoàn thành PASS.
- **Đóng clone sau khi xong**: nếu bật, ClientJS của đúng profile tự đóng sau PASS.

Nút chạy đầy đủ:

**Dọn quầy: Mua đủ + thu vàng + treo lại toàn bộ**

## 4. Quy trình nghiệp vụ chuẩn

### Mua tại nhà bạn

1. Hết thời gian đếm ngược.
2. Nếu có tài khoản khác đang Dọn quầy thì vào hàng chờ.
3. Khi lấy được khóa toàn máy, tự mở đúng ClientJS/profile.
4. Đăng nhập/vào game và đóng popup bằng runtime AUTO.
5. Đi nhà bạn theo thứ tự 1..N.
6. Mở quầy: scan cả hàng trên và hàng dưới, mua ngay các ô hợp lệ.
7. Kéo quầy đúng hai nhịp.
8. Lặp `scan -> mua -> kéo hai nhịp` đến cuối quầy.
9. Nếu chưa đủ target: đóng/mở lại quầy trong giới hạn mỗi lượt ghé; sau đó chuyển nhà tiếp.
10. Duyệt hết nhà 1..N vẫn chưa đủ thì chờ ngắn và bắt đầu vòng mới; chỉ dừng khi đủ target hoặc người dùng bấm Dừng.
11. Chỉ mua những ô khớp một loại VP đang được chọn trong cấu hình.
12. Ô không mua được (khóa level/đã bán) bị bỏ qua và tuyệt đối không được cộng 10 VP.
13. Chỉ kết thúc pha mua khi số lượng xác minh đạt target.

### Treo lại tại nhà mình

1. Quay về nhà và mở quầy.
2. Trên mỗi view: `scan -> thu vàng -> treo đúng VP đã mua`.
3. Khi view hết ô trống: kéo đúng hai nhịp.
4. Lặp lại scan/thu vàng/treo ở view mới.
5. Mỗi fingerprint mua thành công chỉ được tiêu thụ một lần.
6. Chỉ PASS khi `requested_quantity == purchased_quantity == sold_quantity`.
7. Giá bán không được thay đổi.

## 4A. Tương thích ClientJS của AUTO chính

Ba wrapper trong `test-candidates/auto-pro-clientjs-temp/clientjs_auto_patch.py` chỉ áp dụng cho device `PC:/PCID:`:

- **Reset ClientJS**: EngineDriver giữ immutable profile ID và chuyển sang PID mới. `openGame` ưu tiên template, nhưng cũng chấp nhận PID/bridge có ba frame 1000x1000 hợp lệ liên tiếp; không nhấn BACK khỏi một client khỏe chỉ vì template home đổi.
- **Mở rương**: sau chọn rương, chờ modal render ổn định tối thiểu 3 giây, tối đa 8 giây; thử các tâm rương ClientJS và chỉ chốt khi prompt biến mất hoặc vùng modal đổi đủ lớn.
- **Quay hề**: giữ nguyên `ADBController.VongQuay` của AUTO PRO để quay/nhận quà, sau đó đóng reward/wheel overlay và xác nhận đã trở lại màn hình game.

Các thay đổi này đang ở trạng thái SOURCE READY; phải có live log mới được nâng lên LIVE PASS.

## 5. Kết thúc chu kỳ và hàng đợi

Sự kiện duy nhất được phép chốt chu kỳ là `probe_ok` của mode
`COLLECT_GOLD_RESELL_TARGET_EXACT`, đồng thời ba bộ đếm phải bằng nhau.

Sau PASS:

1. ghi `last_result` và checkpoint;
2. đặt `next_run_at = finished_at + interval_minutes * 60` nếu lịch còn bật;
3. đóng đúng ClientJS nếu tùy chọn đóng clone đang bật;
4. giải phóng thread/khóa Dọn quầy;
5. scheduler xét các job quá hạn theo `next_run_at` tăng dần;
6. mở tài khoản đầu tiên trong hàng đợi.

Nếu FAIL/STOP:

- không được ghi kết quả PASS;
- không được reset chu kỳ như đã hoàn thành;
- không được chạy đồng thời tài khoản kế tiếp khi thread cũ chưa thoát;
- giữ bằng chứng report/activity để chẩn đoán.

## 6. Giao tiếp giữa các thành phần

| Thành phần | Vai trò | Giao tiếp |
|---|---|---|
| Multi DEV | UI, lịch, hàng đợi, lifecycle profile | settings local + event sink |
| Resident probe | Điều phối một vòng Dọn quầy | callback JSON trong cùng process |
| EngineDriver | Capture/input ClientJS | Bridge V3 theo PID/profile |
| Bridge V3 DLL | Frame BGRA và gesture | shared memory + named pipe |
| Vision/actions | Nhận diện, mua, thu vàng, treo | frame 1000x1000 + thao tác driver |
| BAT Control | update/build/open/backup | một menu duy nhất |

Các event quan trọng:

- `probe_progress`: checkpoint UI;
- `probe_purchase_ok`: chỉ phát sau khi ô quầy thay đổi;
- `probe_resale_ok`: treo thành công một lô x10;
- `probe_ok`: hoàn tất đủ kế toán;
- `probe_error`: lỗi, không chốt chu kỳ;
- `probe_exit`: nhả tài nguyên sau khi runtime kết thúc.

## 7. Backup một nút

Trong `KVTM_DEV_CONTROL.bat`, chọn:

`[B] Backup cuc bo ban hien tai`

Backup được tạo tại:

`local-backups\KVTM-<timestamp>-<HEAD>\`

Nội dung:

- `source.bundle`: snapshot Git của source;
- `runtime\`: runtime hiện tại, không gồm data-dev;
- `private-data\profiles.json` và `settings.json`: bản local-only;
- `manifest.json`: HEAD/branch/thời điểm.

`local-backups/` đã bị Git ignore. Không upload thư mục backup vì có thể chứa dữ liệu profile mã hóa gắn với Windows user hiện tại.

Nên bấm `[B]` sau khi một bản update được xác nhận live PASS và trước lần update lớn kế tiếp.

## 8. Quy tắc bắt buộc cho phiên AI khác

1. Đọc `AI_COORDINATION.md`, tài liệu này và
   `docs/SECONDARY_MACHINE_RUNTIME_UPDATE.md`.
2. Làm việc trên `develop/multi-auto-dev`.
3. Không yêu cầu người dùng kể lại lịch sử nếu evidence/repo đã có.
4. Không sửa Workspace trong task AUTO/Multi.
5. Không yêu cầu/upload `.kvtm`, profiles/settings, token, cookie, password hoặc launch args giải mã.
6. Không tuyên bố PASS nếu chưa có log/live evidence tương ứng.
7. Mọi thay đổi phải giữ một Control Center BAT duy nhất.
8. Sau sửa source: kiểm tra AST/static contract/package; sau đó chỉ yêu cầu một lượt live test cần thiết.
9. Không khôi phục các Gate 1–4 đã pass lên GUI.
10. Không thay cơ chế fingerprint bằng chọn đại VP; ngưỡng live-calibrated hiện là `0.60`.

## 9. Điểm vào source

- UI/lịch/hàng đợi:
  `source-archive/multi-current/kvtm_multi_tool/kvtm_multi.py`
- DEV resident lifecycle:
  `source-archive/multi-current/kvtm_multi_tool/kvtm_multi_dev_entry.py`
- Runtime giao dịch:
  `components/clientjs-auto/worker/clear_stall_probe_runtime.py`
- Mua/quét/treo:
  `components/clientjs-auto/kvtm_automation/actions/`
- Static contract:
  `tools/verify_clear_stall_contract.py`
- Backup:
  `tools/KVTM_CREATE_LOCAL_BACKUP.ps1`
- Build:
  `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`

## 10. Mẫu báo cáo phiên

```text
SESSION: AUTO/Multi
BRANCH: develop/multi-auto-dev
HEAD: <sha>
STATUS: IN_PROGRESS | PARTIAL | VERIFIED
FILES_CHANGED: <danh sách>
INTERFACE_CHANGED: <không hoặc mô tả>
STATIC_TEST: <kết quả thật>
LIVE_TEST: <run/log thật>
NEXT: <một hành động>
DO_NOT_TOUCH: components/workspace/**, KVTM_WORKSPACE_CONTROL.bat
```


## Cập nhật vòng mua khi đầy kho

- Mỗi lần chuyển quầy chỉ vuốt **một nhịp**, chờ render rồi scan/mua ngay.
- Khi kho clone đầy giữa lúc mua, Gate 5 chỉ treo các fingerprint VP đã xác minh mua trong chính lượt hiện tại.
- Sau khi giải phóng kho, clone quay lại đúng nhà đang dọn, mở lại quầy và tiếp tục cho đến đủ target.
- Không cộng số lượng cho click thất bại và không bán vật phẩm ngoài manifest đã mua.


## 11. Bảng xây dựng chức năng Dọn quầy

- Mở Multi, chọn tab **Thiết kế**, rồi bấm **Mở bảng tạo / chỉnh sửa chức năng**.
- Tài liệu runtime nằm tại `data-dev/clear-stall-workflow-designer.json`; source chính sách nằm trong
  `components/clientjs-auto/kvtm_automation/workflows/clear_stall/designer_policy.py`.
- Bảng cho phép sắp xếp, bật/tắt, thêm/nhân bản/xóa bước; xem template, vùng nhận diện,
  điểm click, đường swipe và vị trí hàm Python; đồng thời chỉnh policy, JSON và source Python.
- **Áp dụng runtime** chỉ thành công sau khi kiểm tra kiểu dữ liệu, giới hạn tọa độ và thứ tự
  giao dịch bắt buộc `scan → buy → swipe_1 → swipe_2 → scan_next`.
- Một nhịp quầy luôn gồm đúng hai swipe. Trình kiểm tra không cho lưu cấu hình phá vỡ quy tắc này.
- Runtime hiện đọc trực tiếp các giá trị nhận diện, retry, thời gian/điểm swipe, giới hạn thu vàng
  và thời gian chờ mở kho. Thay đổi có hiệu lực ở lượt Dọn quầy kế tiếp.
- Khi lưu source Python trong bảng, tool chạy `ast.parse` trước và tạo bản `.designer.bak`.
  Sửa source là chế độ chuyên sâu; sau khi cập nhật source từ Git, thay đổi cục bộ có thể bị ghi đè,
  vì vậy cần tạo backup trước khi pull/build.


## 12. Điều chỉnh source 2026-09-05 — chờ live verify

- AUTO chính: một lỗi có nội dung qua/thoát nhà bạn được thử lại; đủ 3 lỗi liên tiếp thì reset đúng ClientJS của profile. EngineDriver giữ immutable `profile_id`, nhận PID thay thế và `openGame` chỉ giao lại cho AUTO sau template game hoặc ba frame ClientJS 1000x1000 hợp lệ. Chỉ cho phép một lần reset trong chu kỳ lỗi; nếu vẫn lỗi thì worker FAIL rõ ràng.
- Dọn quầy: mỗi nhà chỉ mở và quét đúng một lần trong một vòng. Duyệt hết nhà `1..N` mà còn thiếu target thì chờ ngắn và bắt đầu vòng mới từ nhà 1.
- Treo bán: không còn chặn giao dịch chỉ vì template `sl10` không xuất hiện. VP vẫn phải khớp fingerprint của giao dịch mua đã xác minh, không đổi giá và phải có thay đổi màn hình sau click đặt bán.
- Scheduler: tối đa hai profile Dọn quầy độc lập cùng lúc. Cùng một profile vẫn độc quyền với AUTO chính/Dọn quầy; tài khoản thứ ba tiếp tục giữ hạn và chờ slot.
- Trạng thái: năm file Python liên quan đã `py_compile` PASS. Chưa gọi LIVE PASS cho bốn hành vi trên; cần build Windows và chạy thực tế.

## 2026-09-15 — Sửa nhịp kéo view bỏ sót mua sau 8 ô đầu

- Live report: nhà bạn đầu mua đúng 8 ô view đầu nhưng không mua các view sau; nhà thứ hai mua view sau không ổn định.
- Root cause trong Dọn quầy độc lập: `next_view()` chờ render đủ `0.55s` ngay giữa hai swipe ngắn, cho phép ClientJS snap/căn lại trước pulse thứ hai. View sau vì vậy có thể dừng lệch các tâm quét/click cố định.
- Sửa hẹp: giữ đúng 2 swipe, `0.35s/swipe`, cùng tọa độ/hướng hiện hành; gửi cả hai swipe liên tiếp và chỉ settle `0.55s` một lần sau pulse thứ hai. `previous_view()` dùng cùng contract để rewind đối xứng.
- Không đổi danh sách VP, fingerprint, xác minh listing biến mất, batch x10, AUTO MULTI DEV hoặc recovery.
- Verifier khóa một settle duy nhất sau swipe cuối cho cả tiến và lùi.
- AST và static order check: PASS. Windows build/LIVE: PENDING.

## 2026-09-15 — Tốc độ kéo Dọn quầy theo từng profile

- Thêm trường `Kéo quầy Dọn quầy (giây/swipe)` vào cấu hình AUTO MULTI DEV; mặc định `0.35`, phạm vi `0.05..3.0`.
- Đây là khóa riêng `clear_stall_drag_speed`, không thay đổi `shop_drag_speed` của AUTO Function.
- Khi bắt đầu Dọn quầy, GUI chụp snapshot cấu hình hiện hành của profile và truyền vào resident `ProbeConfig`.
- Runtime chỉ thay `swipe_duration`; vẫn bắt buộc hai swipe liên tiếp và settle `0.55s` một lần sau swipe cuối.
- Log runtime ghi rõ tốc độ thực nhận để đối chiếu cấu hình.
- Static contract: cập nhật. Windows build/LIVE: PENDING.

## 2026-09-15 — Terminal Dọn quầy phải trả profile về OFF

- Root cause: `probe_stopped`, lỗi chạy thủ công và nhánh mua/bán thiếu chỉ ghi terminal state; ClientJS của profile vẫn sống nên bảng tiếp tục báo ON và chặn AUTO khác.
- Mọi nhánh STOP/FAIL/thiếu số lượng nay yêu cầu đóng đúng process object/PID của profile, chờ xác nhận process đã thoát rồi mới xóa mapping và refresh bảng.
- Cleanup từ chối tác động nếu mapping đã được thay bằng process khác, tránh đóng nhầm ClientJS vừa được mở lại.
- PASS vẫn dùng `close_client_after_run` hiện hành. Không thay launcher, tên cửa sổ, vị trí hay kích thước 1000x1000.
- Source/static contract: PASS. Windows LIVE: PENDING.
