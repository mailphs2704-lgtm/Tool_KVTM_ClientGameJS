# PROJECT CLEANUP INVENTORY

Cập nhật: 2026-09-11
Branch làm việc: `maintenance/repo-cleanup-packaging`
Base đồng bộ: `58930f2e2d86e8799013b16dfe2f95648b6ba4fc`

Mục tiêu: chuẩn hóa repository theo từng bước nhỏ, đối chiếu từng thư mục trước khi xóa. Không xóa theo tên folder; chỉ xóa sau khi chứng minh không còn runtime/build/test/operator caller cần thiết.

## Trạng thái sử dụng

- `KEEP_ACTIVE`: đang được runtime/build/operator/CI sử dụng trực tiếp.
- `ACTIVE_RELOCATE`: đang dùng nhưng tên/vị trí chưa chuẩn; phải move + sửa caller + verify trước khi xóa path cũ.
- `REVIEW`: chưa đủ bằng chứng để giữ hoặc xóa.
- `REMOVE_CANDIDATE`: bằng chứng hiện tại cho thấy không còn vai trò production; vẫn chờ đối chiếu cuối trước khi delete.
- `LOCAL_GENERATED`: output/cache/log local; không phải source authoritative.

## Root inventory

| Path | Trạng thái hiện tại | Ghi chú |
|---|---|---|
| `.github/` | KEEP_ACTIVE | CI/static checks |
| `KVTM-Clean-Auto/` | REMOVE_CANDIDATE | Skeleton tài liệu cũ; audit chi tiết ở dưới |
| `ai-don-quay/` | REVIEW | Probe cũ; cần dependency audit |
| `bridge-v3/` | ACTIVE_RELOCATE | Production Bridge V3; đích dự kiến `native/bridge-v3` |
| `components/` | KEEP_ACTIVE | Chứa source runtime chính, đặc biệt `components/clientjs-auto` |
| `docs/` | KEEP_ACTIVE | Handoff, architecture, cleanup docs |
| `packaging/` | KEEP_ACTIVE | Builder/package source |
| `source-archive/` | ACTIVE_RELOCATE | Vẫn chứa production inputs thật; không được xóa nguyên folder |
| `test-candidates/` | ACTIVE_RELOCATE | Một phần vẫn là production input; audit từng subfolder |
| `tools/` | KEEP_ACTIVE | Verifier/updater/diagnostic/ops; cần chuẩn hóa subfolder sau |
| `KVTM_DEV_CONTROL.bat` | KEEP_ACTIVE | Operator entry chính |
| `KVTM_MACHINE_TRANSFER_CONTROL.bat` | KEEP_ACTIVE | Machine/runtime update operations |
| `KVTM_SECONDARY_BOOTSTRAP.ps1` | KEEP_ACTIVE | Secondary machine bootstrap |
| `START_SECONDARY_SETUP.bat` | KEEP_ACTIVE | Secondary setup entry |
| `KVTM_DON_QUAY_SAFE.bat` | REVIEW | Cần đối chiếu caller trước khi quyết định |
| `KVTM_PROFILE_DIAGNOSTIC.ps1` | REVIEW | Diagnostic root script; cần đối chiếu caller |
| `KVTM_RECIPE_668_PROBE.bat` | REVIEW | Probe root script; cần đối chiếu caller |

## Audit 001 — `KVTM-Clean-Auto/`

### Nội dung thực tế

Thư mục hiện chỉ còn:

```text
KVTM-Clean-Auto/
  README.md
  docs/
    PASS_LOG.md
    WORKFLOW.md
```

Không có các thư mục source mà README mô tả như `app/`, `automation/`, `vision/`, `engine/`, `bridge/`, `assets/`, `config/`, `tests/` hoặc `scripts/`.

### Bằng chứng obsolete

- README tự nhận `KVTM-Clean-Auto/` là source chính, nhưng cấu trúc source được mô tả không còn tồn tại.
- README yêu cầu `scripts/IMPORT_REQUIRED_FILES.ps1`, nhưng file/script đó không tồn tại trong chính folder này.
- `docs/PASS_LOG.md` chỉ có header, chưa có một bản ghi PASS nào.
- `docs/WORKFLOW.md` mô tả đường dẫn local/project cũ và quy trình promote cũ, không khớp architecture hiện hành.
- Packaging hiện tại không lấy input từ `KVTM-Clean-Auto/`; 5 production inputs hiện nằm ở `source-archive/auto-pro-reference`, `source-archive/multi-current/kvtm_multi_tool`, `test-candidates/auto-pro-clientjs-temp`, `bridge-v3`, `components/clientjs-auto`.

### Kết luận

`KVTM-Clean-Auto/` = `REMOVE_CANDIDATE`.

Chưa xóa ở Stage 0. Chỉ delete sau khi operator xác nhận và không phát hiện caller mới trong lượt đối chiếu cuối.

## Thứ tự audit tiếp theo

1. `ai-don-quay/`
2. `test-candidates/`
3. `source-archive/`
4. root BAT/PS1 probe/diagnostic files
5. `tools/` — tách `verify/`, `diagnostics/`, `ops/`
6. `bridge-v3/` — chuẩn hóa sang `native/bridge-v3`
7. `components/` — xác nhận authoritative source layout

Không thực hiện destructive cleanup trên `develop/multi-auto-dev`.
