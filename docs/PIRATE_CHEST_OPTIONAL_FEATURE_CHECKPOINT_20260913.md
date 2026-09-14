# PIRATE CHEST OPTIONAL FEATURE — CHECKPOINT 2026-09-13

Repo: `mailphs2704-lgtm/Tool_KVTM_ClientGameJS`  
Branch: `develop/multi-auto-dev`  
Trạng thái: **SOURCE READY FOR LOCAL BUILD/LIVE TEST — NOT RUNTIME PASS**

## 1. Yêu cầu operator đã chốt

- Các chức năng tùy chọn từ đây thay vào vị trí AUTO chức năng chính cũ trên UI Multi DEV.
- Tùy chọn đầu tiên: **Mở rương hải tặc**.
- Điểm vào Kho Báu Hải Tặc là hitbox thân thuyền tại logical `(363, 620)`; tuyệt đối không click hai bong bóng rương/đèn thần phía trên và không nhận diện template/background vì skin/background có thể khác nhau.
- Chỉ được phép thao tác **rương đầu tiên / slot 0**. Các rương còn lại có thể tốn kim cương nên không được tồn tại tọa độ click cho chúng trong workflow.
- Check đầu tiên chỉ chạy **sau sale đầu tiên hoàn tất**.
- Từ đó bắt đầu chu kỳ **20 phút**. Khi đến hạn chỉ đánh dấu due; thao tác UI phải chờ safe Function boundary, không cắt ngang Function.
- Nếu slot 0 đang cooldown thì đóng panel và kết thúc lượt check.
- Nếu gặp modal **KHO QUÁ TẢI**, không nhận diện tên Kho 2/Kho 3: đóng modal, thoát flow mở rương, kết thúc riêng optional function và tiếp tục các Function khác.
- Lỗi/timeout của optional function phải fail-close và non-blocking đối với AUTO Main.

## 2. Kiến trúc triển khai

### Runtime workflow

`components/clientjs-auto/kvtm_automation/workflows/pirate_chest/workflow.py`

- logical coordinate/hitbox entry tại thân thuyền, có log logical/native/content;
- slot 0 only;
- READY / COOLDOWN bằng ROI màu/hình học;
- modal KHO QUÁ TẢI là trạng thái chung, không phụ thuộc tên kho;
- timeout theo state, không spam click;
- `SAFE_ABORT` thay cho speculative click;
- không có coordinate cho paid chest slot 1..4.

### Scheduler

`components/clientjs-auto/kvtm_automation/workflows/auto_main/pirate_chest_schedule.py`

- `PIRATE_CHEST_INTERVAL_SECONDS = 1200.0`;
- đọc `pirate_chest_enabled` từ `auto-main-config.json`;
- check đầu sau completed sale đầu;
- các lần sau chỉ chạy ở post-Function boundary;
- scheduled 3h restart vẫn defer tới safe boundary và có thể consume chest due trước restart;
- exception của optional maintenance -> `SAFE_ABORT`, schedule chu kỳ mới, không làm fail Function đã PASS.

### AUTO Main entry

`components/clientjs-auto/kvtm_automation/workflows/auto_main/__init__.py`

AUTO Main hiện đi qua wrapper `pirate_chest_schedule.AutoMainWorkflow`.

## 3. UI / per-profile config mới

`source-archive/multi-current/kvtm_multi_tool/optional_features_integration.py`

- thay visible Function-selector slot cũ bằng vùng **TÙY CHỌN**;
- tùy chọn đầu tiên: `Mở rương hải tặc`;
- mặc định OFF;
- lưu riêng theo profile dưới key `auto_multi_dev_optional_features`;
- snapshot theo profile trước khi run bắt đầu;
- inject `pirate_chest_enabled` vào `_auto_main_pending_config`;
- đồng thời inject vào `_auto_main_active_config` để scheduled ClientJS restart giữ nguyên trạng thái tùy chọn;
- không thay Bridge/capture, Function engine, sale cadence hoặc recovery ownership.

Underlying Function scheduler vẫn được giữ làm execution backbone để không phá behavior đã ổn định; chỉ vị trí UI selector cũ được chuyển sang Optional Features tại checkpoint này.

## 4. Host/runtime packaging

`source-archive/multi-current/kvtm_multi_tool/kvtm_multi_owned_host.py`

- import/install `optional_features_integration` sau scheduler/profile settings layer;
- launcher DEV `START_MULTI_DEV_SILENT.ps1` chạy chính `kvtm_multi_owned_host.py`;
- `BUILD_FULL_PACKAGE.ps1` copy recursive toàn bộ `kvtm_multi_tool`, nên module mới được ship theo normal Control Center `[1]` build.

## 5. Static contract

`tools/verify_multi_dev_persistent_settings_contract.py` đã được mở rộng để khóa:

- owned host phải install Optional Features;
- Pirate Chest default OFF và per-profile;
- UI slot cũ phải thành `TÙY CHỌN` + `Mở rương hải tặc`;
- run snapshot phải inject `pirate_chest_enabled` vào pending/active config;
- AUTO Main phải import pirate chest scheduler;
- interval phải giữ 1200s;
- first check phải gắn completed-sale boundary;
- recurring check phải gắn post-Function boundary;
- workflow phải có slot 0 và không được có slot 1..4/paid chest coordinate;
- workflow không được dùng các template-call bị cấm;
- STORAGE_FULL / COOLDOWN / READY fail-close guards phải còn nguyên.

Verifier này nằm trong luồng build DEV hiện hành thông qua persistent settings contract của `BUILD_FULL_PACKAGE_PS51.ps1`.

## 6. Commits của mốc này

- `06ab43ee253a582a17fb2c59f691a7976b76d09c` — add Optional Features per-profile layer.
- `5ce312751c5ca649d6bf24921b26ee4c09de3b19` — install Optional Features in owned Multi DEV host.
- `2189df8e858f4bd020f672593f61fa1120af27f9` — lock Pirate Chest optional-feature static contract.

Các commit Pirate Chest core/scheduler trước đó nằm cùng branch; `5f7fc33f3135652ab233261996a389020b8130e5` xác nhận AUTO Main entry đã được wire qua pirate chest scheduler.

## 7. Live regression 23:22 — reward-timeout handoff

Live log xác nhận rương đã mở nhưng `_reward_ready` timeout. Flow cũ vẫn ghi
`exact-main=PASS` từ HUD phía sau overlay rồi chạy Function kế tiếp, làm Planting
nhận diện sai màn hình và fail-close.

Source fix:

- chỉ khi kết quả rương là `SAFE_ABORT` mới bắt buộc reset scene;
- thoát reward/chest overlay đúng một lần, không retry `MỞ NGAY` hoặc nhận quà;
- chạy route dùng chung `nhà bạn #1 → nhà mình`;
- chỉ cho phép Function kế tiếp chạy khi vòng qua nhà bạn và exact-main đều PASS;
- `OPENED`, `COOLDOWN`, `STORAGE_FULL` không chạy vòng qua nhà bạn;
- nếu vòng reset lỗi, fail-close trước Function kế tiếp thay vì tiếp tục trên màn hình ảo.

Đây là SOURCE/AST READY, chưa phải runtime PASS.

## 8. Persisted modal `Chạm để mở rương`

Operator xác nhận game có thể lưu rương đã chọn nhưng chưa mở. Lần check sau,
click thân thuyền đi thẳng vào modal `Chạm để mở rương`, không qua panel slot.
Ảnh evidence native 1000x1000 được đối chiếu với detector hiện tại:

- `header_mean=15.12`;
- `orange_ratio=0.397`;
- `_open_prompt=True`.

Entry nay chấp nhận `panel normal OR open prompt`. Khi vào thẳng open prompt,
workflow tiếp tục đúng rương hiện tại và tuyệt đối bỏ qua chọn slot 0 cùng
`MỞ NGAY`. Nhánh SAFE_ABORT/qua nhà bạn chỉ chạy nếu thao tác tiếp theo thật sự
timeout hoặc gặp lỗi.

## 9. NEXT GATE

Theo `AGENTS.md`, operator chạy đúng Control Center:

```text
D:\Tool_KVTM_Multi_DEV\KVTM_DEV_CONTROL.bat
→ [1] Cap nhat source + build runtime DEV
```

Sau build sạch, mở Multi DEV và kiểm tra theo thứ tự:

1. Vị trí Function selector cũ hiển thị `TÙY CHỌN` + `Mở rương hải tặc`.
2. Chuyển acc qua lại xác nhận trạng thái toggle lưu riêng theo profile.
3. Bật Mở rương cho một acc test.
4. Bắt đầu AUTO; sale đầu hoàn tất rồi mới check rương.
5. Nếu READY: chỉ slot 0 được chọn/mở/nhận quà, sau đó xác nhận cooldown.
6. Nếu COOLDOWN: đóng panel và tiếp tục AUTO.
7. Nếu KHO QUÁ TẢI: đóng modal/thoát rương và tiếp tục Function kế tiếp.
8. Đến 20 phút giữa Function: không được chen ngang; chỉ chạy sau Function PASS.

Không gọi RUNTIME PASS trước bằng chứng live từ operator.


## 10. Live evidence: nhận quà bằng vùng trống và trạng thái rương giữa

Hai ảnh operator cung cấp xác nhận reward presentation là modal phủ lên panel
Kho Báu Hải Tặc. Quà là ngẫu nhiên nên không được phụ thuộc màu/ảnh đồng xu.

Hợp đồng mới:

- trước `MỞ NGAY`, lưu fresh frame của panel và vùng rương giữa;
- chỉ công nhận modal mở khi vùng rương giữa biến mất/thay đổi đủ lớn;
- sau khi quà xuất hiện, chạm đúng một lần tại logical `(500, 715)`, vùng trống
  ngay dưới dòng `Chạm để nhận quà`; không chạm rương hoặc vật phẩm;
- không dùng nút quay lại để thoát reward modal;
- chỉ công nhận nhận quà xong khi panel thường quay lại và vùng rương giữa xuất
  hiện lại; lúc đó mới bấm X đóng panel về MAIN;
- nhánh vào thẳng persisted modal không có reference panel ban đầu, nên dùng
  panel header làm return proof an toàn;
- nếu modal không hoàn tất thì `SAFE_ABORT`, không báo MAIN giả và không retry
  thao tác nhận quà.

Commits: `613e24b`, `49e4bbd`, `b4230d92`, `1c17ca3`.
Source AST PASS; Windows build/live vẫn PENDING.


## 11. Live 11:08 — nhận quà PASS nhưng hậu kiểm SAFE_ABORT giả

Live xác nhận cú chạm `(500,715)` đã nhận quà và reward modal đã đóng.
Sai số nằm ở hậu kiểm: source cũ so panel sau claim với panel trước `MỞ NGAY`;
animation/cooldown làm vùng rương khác ngưỡng nên trả `SAFE_ABORT` giả, kéo theo
friend-house recovery và lỗi dừng AUTO.

Fix `d4acf2dc` lưu frame reward thật ngay trước claim. Sau claim, return proof
bắt buộc đồng thời có panel thường và vùng rương giữa thay đổi đủ lớn so với
reward frame. Khi đạt, status là `OPENED`, đóng X về MAIN và tuyệt đối không
chạy friend-house recovery. Verifier khóa tại `0ed715ff`; AST PASS. Windows
rebuild/live retest vẫn PENDING.


## 12. Animation race: claim prompt và panel return

Live tiếp theo cho thấy claim có thể được game nhận trễ/ngẫu nhiên nếu click trong lúc
animation vẫn khóa input; hậu kiểm 6 giây cũng có thể hết trước khi rương giữa ổn định.

Fix `b91175ce` không tăng sleep mù:

- nhận diện vùng chữ trắng `Chạm để nhận quà`, độc lập hình phần thưởng;
- yêu cầu vùng chữ ổn định liên tục 0.60s trước một claim tap duy nhất;
- reward animation timeout 10s;
- sau claim chờ panel+rương giữa trở lại ổn định liên tục 0.60s, timeout 12s;
- không retry claim và không dùng Back.

Verifier `13126736`; workflow/verifier AST PASS. Windows live PENDING.


## 13. Operator-approved exact sequence

Quy trình cuối được operator chốt:

1. vào thuyền và phân loại panel thường hoặc persisted open modal;
2. nếu panel thường, chỉ chọn slot 0 rồi MỞ NGAY;
3. khi open modal đã được chứng minh, giữ đúng trạng thái 4.0s rồi mới tap rương;
4. sau tap rương, chờ tối thiểu 4.0s và claim text ổn định mới claim đúng một lần
   tại `(500,715)`;
5. chờ reward modal tự đóng; panel/rương giữa phải trở lại ổn định;
6. đóng X và bắt buộc chứng minh exact-main trước khi trả `OPENED`.

Commit `866a0219`; contract `c9722329`; AST PASS. Live PENDING.


## 14. INPUT4/CAPTURE3 post-claim separation

Live phản ánh claim và capture hậu kiểm bắt đầu gần như đồng thời. Fix
`96ca33f4` thêm quiet window 4.0s ngay sau claim-once: trong khoảng này không
gọi frame/CAPTURE/check. Hết quiet window mới bắt đầu chờ panel+rương giữa trở
lại. Không thêm claim retry. Contract `1effe387`; AST PASS; live PENDING.

Log startup cho thấy friend refresh định kỳ đang BẬT; đây là cấu hình riêng sau
mỗi ba vòng, không phải bằng chứng chest SAFE_ABORT nếu thiếu đoạn log chest.
