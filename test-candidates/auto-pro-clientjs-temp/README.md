# AUTO PRO tạm thời chạy GameClientJS

Bản này chỉ thay `engine_driver.py`. Logic và giao diện AUTO PRO cũ được giữ nguyên.

## Thay đổi

- Click đi qua Cocos Engine Bridge, không chiếm chuột.
- Swipe hai điểm và nhiều điểm đều đi qua Cocos Engine Bridge.
- Bỏ toàn bộ hệ số, thời gian tối thiểu từ `engine_bridge.json`.
- Thời gian swipe nhiều điểm = giá trị AUTO PRO x số đoạn logic.
- Các delay còn lại vẫn do `adb_controller.pyc` đọc trực tiếp từ giao diện AUTO PRO.
- Tạo bản sao `engine_driver.py.before-auto-settings.bak` trước khi cài.

## Cài

Chạy:

```powershell
.\INSTALL_TO_AUTO_PRO.bat "C:\Users\15130\Desktop\AUTO_KVTM_PRO_recovered_local_FIXED2\AUTO_KVTM_PRO_recovered_local"
```

Sau đó chạy `RUN_PC_AUTO_ENGINE.bat` trong thư mục AUTO PRO.
