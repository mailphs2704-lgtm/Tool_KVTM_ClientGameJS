# PROJECT CLEANUP / PACKAGING NORMALIZATION PLAN

Cập nhật: 2026-09-09

Tài liệu này mô tả **kế hoạch tương lai**, chưa phải lệnh cho phép xóa file. Mục tiêu là dọn repo, gom source authoritative về vị trí dễ hiểu và làm cho packaging chỉ phụ thuộc các đường dẫn canonical.

## Nguyên tắc an toàn

- **Không làm cleanup phá hủy trên `develop/multi-auto-dev`.**
- Dùng branch riêng `maintenance/repo-cleanup-packaging`.
- Branch cleanup hiện là snapshot cũ và phải được rebase/recreate từ HEAD `develop/multi-auto-dev` mới nhất trước khi bắt đầu cleanup thực tế.
- Không xóa thư mục chỉ vì tên là `test-candidates`, `source-archive`, `ai-don-quay` hoặc `legacy`; phải chứng minh zero runtime/build references trước.
- Mỗi stage cleanup phải build package + static contracts + smoke runtime trước khi chuyển stage kế tiếp.
- Không trộn cleanup với sửa hành vi Function, Sale, QC, Dọn quầy, Bridge hoặc Recovery trong cùng commit.

## Packaging input hiện tại — phải bảo vệ

`packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1` hiện lấy production package từ **5 nguồn**:

```text
source-archive/auto-pro-reference
source-archive/multi-current/kvtm_multi_tool
test-candidates/auto-pro-clientjs-temp
bridge-v3
components/clientjs-auto
```

Do đó:

- `source-archive/` **chưa thể xóa**;
- `test-candidates/` **chưa thể xóa toàn bộ**;
- `source-archive/multi-current/kvtm_multi_tool` hiện vẫn là source GUI Multi DEV authoritative cho packaging;
- `test-candidates/auto-pro-clientjs-temp` hiện vẫn là packaging input thực tế dù tên thư mục nghe như thử nghiệm;
- Bridge V3 và `components/clientjs-auto` là production inputs trực tiếp.

Việc chuẩn hóa packaging phải đổi builder/caller trước, verify xong rồi mới xóa đường dẫn cũ.

## Cấu trúc đích đề xuất

Không bắt buộc giữ đúng tên này nếu dependency audit cho thấy phương án tốt hơn, nhưng mục tiêu là tách rõ source, native, vendor, tooling và test:

```text
src/
  multi/
  clientjs-auto/

native/
  bridge-v3/

vendor/
  auto-pro-reference/
  auto-pro-clientjs-runtime/

packaging/
  suite-v0.15/

tools/
  verify/
  diagnostics/
  ops/

docs/
tests/

KVTM_DEV_CONTROL.bat
```

Điểm quan trọng không phải tên folder mà là: **mỗi production component chỉ có một authoritative location** và builder không còn lấy source production từ folder mang nghĩa `test-candidates`.

## Stage 0 — snapshot + dependency inventory

Trước khi move/xóa:

1. cập nhật branch cleanup từ HEAD develop mới nhất;
2. ghi HEAD base vào tài liệu/commit;
3. liệt kê toàn bộ tracked root files/directories;
4. quét references từ:
   - `KVTM_DEV_CONTROL.bat`;
   - `packaging/**/*.ps1`;
   - `tools/**/*.py|ps1|bat`;
   - `.github/`;
   - source imports/path joins;
5. lập bảng `path → callers → runtime/build/test/obsolete`;
6. không xóa gì ở stage này.

## Stage 1 — low-risk cleanup / ignore hygiene

Chỉ xử lý các artifact chắc chắn không phải source:

- logs, reports, cache, generated diagnostics;
- build output `dist/`;
- temporary recordings hoặc image dumps không cần commit;
- machine/profile diagnostic output;
- `.pyc`, `__pycache__`, temporary package staging;
- root artifacts local-only nếu dependency audit xác nhận không tracked/không required.

Mục tiêu stage 1 là `.gitignore` sạch hơn và repo checkout mới không sinh noise.

### Không được xóa mù ở stage 1

Các path sau phải dependency-search trước:

- `KVTM_DON_QUAY_SAFE.bat`;
- `ai-don-quay/step1_probe.py`;
- root diagnostic/build scripts;
- `source-archive/*`;
- `test-candidates/*`.

`KVTM_DEV_CONTROL.bat` hiện là entry operator quan trọng và có thể gọi các script root; mọi relocation phải cập nhật caller cùng commit.

## Stage 2 — canonical source relocation

Di chuyển từng component một, không move toàn repo cùng lúc.

Thứ tự đề xuất:

1. Multi source authoritative;
2. ClientJS AUTO source;
3. Bridge V3 native source;
4. AUTO PRO/vendor reference/runtime input;
5. test/prototype source còn giá trị.

Với mỗi component:

```text
copy/move authoritative source
→ update all path references
→ update static verifier path constants
→ build package
→ verify package contains expected files
→ smoke runtime
→ only then remove old path
```

Trong thời gian transition có thể giữ compatibility path/adapter ngắn hạn, nhưng phải có issue/doc ghi rõ ngày xóa; không để hai authoritative copies tồn tại lâu dài.

## Stage 3 — packaging normalization

Mục tiêu cuối:

`BUILD_FULL_PACKAGE.ps1` chỉ đọc các production canonical inputs, ví dụ:

```text
src/multi
src/clientjs-auto
native/bridge-v3
vendor/auto-pro-reference
vendor/auto-pro-clientjs-runtime
```

Builder phải fail-close nếu source canonical thiếu. Không fallback ngầm sang `source-archive` hoặc `test-candidates` sau khi migration đã hoàn tất.

PS5.1 wrapper, old-runtime release, output cleanup retry, persistent settings preservation và HEAD stamp vẫn phải được giữ nguyên hành vi.

## Stage 4 — prototype/obsolete removal

Chỉ sau khi canonical packaging PASS và search toàn repo trả về zero caller mới xét xóa:

- prototype thật sự như `test-candidates/function-builder-core` nếu vẫn còn và không còn caller;
- probe cũ trong `ai-don-quay` nếu đã được production workflow thay thế;
- BAT legacy không còn được Control Center hoặc operator workflow gọi;
- duplicate source archives sau khi production đã chuyển sang canonical path.

Mỗi delete batch nhỏ, có commit riêng và dependency evidence.

## Stage 5 — acceptance gate trước merge cleanup

Tối thiểu phải PASS:

1. toàn bộ static contracts do `[1]` chạy;
2. Bridge V3 build x86;
3. full package build;
4. `.source-head.txt`/HEAD stamp đúng cleanup HEAD;
5. Multi DEV mở được;
6. Function 1 smoke PASS;
7. Recipe/Recovery architecture contracts PASS;
8. Sale VP + QC không regression;
9. friend-refresh toggle không regression;
10. periodic ClientJS restart 2h contract còn nguyên;
11. persistent `%APPDATA%\KVTM Multi DEV` settings không bị overwrite;
12. Dọn quầy vẫn dùng settings/profile/operator data cũ bình thường.

Cleanup chỉ được merge sau các gate này.

## Các vùng không được sửa cùng cleanup nếu không có regression evidence

- Function 1 business flow;
- `RecoveryManager` policy;
- Recipe dependency;
- exact-main detector;
- down-floor visual detector;
- VP advertising/QC;
- Clear Stall transaction logic;
- Bridge V3 protocol/capture ownership;
- ClientJS periodic restart safe-boundary semantics.

## Handoff cho AI tiếp theo

AI tiếp theo trước khi dọn repo phải đọc theo thứ tự:

1. `docs/AUTO_MULTI_DEV_LATEST_HANDOFF.md`;
2. `docs/PROJECT_CLEANUP_PACKAGING_PLAN.md`;
3. `packaging/suite-v0.15/BUILD_FULL_PACKAGE.ps1`;
4. `packaging/suite-v0.15/BUILD_FULL_PACKAGE_PS51.ps1`;
5. `KVTM_DEV_CONTROL.bat`;
6. toàn bộ verifier được builder gọi.

Sau đó mới audit dependencies. **Không bắt đầu bằng `git rm`, move folder hàng loạt hoặc xóa `source-archive/test-candidates`.**

## Trạng thái branch cleanup hiện tại

Branch `maintenance/repo-cleanup-packaging` đã tồn tại nhưng đang đứng ở snapshot cũ hơn nhiều so với develop hiện tại. Trước cleanup thực tế nên tạo điểm bắt đầu mới từ HEAD develop hiện hành thay vì tiếp tục trực tiếp trên snapshot cũ và phải resolve một khối lớn runtime changes cùng lúc.
