#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <cstdint>

namespace {
constexpr UINT WM_KVTM_TOUCH = WM_APP + 0x417;
constexpr UINT WM_KVTM_CAPTURE = WM_APP + 0x418;
constexpr wchar_t kWindowProperty[] = L"KVTM_ENGINE_BRIDGE_20260828";
constexpr DWORD kCaptureVersion = 1;
constexpr DWORD kPixelFormatBgra8BottomUp = 1;
constexpr DWORD kPixelFormatBgra8TopDown = 2;
constexpr DWORD kMaxCaptureBytes = 64u * 1024u * 1024u;
constexpr unsigned int GL_FRONT_VALUE = 0x0404;
constexpr unsigned int GL_BACK_VALUE = 0x0405;
constexpr unsigned int GL_PACK_ALIGNMENT_VALUE = 0x0D05;
constexpr unsigned int GL_BGRA_VALUE = 0x80E1;
constexpr unsigned int GL_UNSIGNED_BYTE_VALUE = 0x1401;
constexpr int kMinimumWindowSide = 200;

enum class Phase : int { Down = 1, Move = 2, Up = 3 };
struct TouchCommand { Phase phase; float x; float y; LONG result; };
struct CaptureCommand {
    LONG result;
    DWORD frame_id;
    DWORD width;
    DWORD height;
    DWORD stride;
};
struct CaptureHeader {
    char magic[4];
    DWORD version;
    DWORD header_size;
    DWORD width;
    DWORD height;
    DWORD stride;
    DWORD pixel_format;
    DWORD buffer_size;
    DWORD frame_id;
    DWORD status;
    ULONGLONG timestamp_ms;
};

using DirectorGetInstance = void* (__cdecl*)();
using DirectorGetOpenGLView = void* (__thiscall*)(void*);
using HandleTouches = void (__thiscall*)(void*, int, int*, float*, float*);
using GlReadPixels = void (WINAPI*)(int, int, int, int, unsigned int, unsigned int, void*);
using GlGetError = unsigned int (WINAPI*)();
using GlReadBuffer = void (WINAPI*)(unsigned int);
using GlPixelStorei = void (WINAPI*)(unsigned int, int);

WNDPROC g_previous_proc = nullptr;
HWND g_window = nullptr;
HMODULE g_self = nullptr;
DirectorGetInstance g_get_director = nullptr;
DirectorGetOpenGLView g_get_view = nullptr;
HandleTouches g_touch_begin = nullptr;
HandleTouches g_touch_move = nullptr;
HandleTouches g_touch_end = nullptr;
GlReadPixels g_gl_read_pixels = nullptr;
GlGetError g_gl_get_error = nullptr;
GlReadBuffer g_gl_read_buffer = nullptr;
GlPixelStorei g_gl_pixel_store_i = nullptr;
HANDLE g_capture_mapping = nullptr;
CaptureHeader* g_capture_header = nullptr;
DWORD g_capture_capacity = 0;
volatile LONG g_capture_frame = 0;

bool non_client_size(HWND hwnd, int& width, int& height) {
    RECT outer{}, client{};
    if (!GetWindowRect(hwnd, &outer) || !GetClientRect(hwnd, &client)) return false;
    width = (outer.right - outer.left) - (client.right - client.left);
    height = (outer.bottom - outer.top) - (client.bottom - client.top);
    return true;
}

void make_sizing_rect_square(HWND hwnd, WPARAM edge, RECT* proposed) {
    if (!proposed) return;
    int border_w = 0, border_h = 0;
    if (!non_client_size(hwnd, border_w, border_h)) return;
    int client_w = max(kMinimumWindowSide, proposed->right - proposed->left - border_w);
    int client_h = max(kMinimumWindowSide, proposed->bottom - proposed->top - border_h);

    const bool vertical_only = edge == WMSZ_TOP || edge == WMSZ_BOTTOM;
    int side = vertical_only ? client_h : client_w;
    int outer_w = side + border_w;
    int outer_h = side + border_h;

    if (edge == WMSZ_LEFT || edge == WMSZ_TOPLEFT || edge == WMSZ_BOTTOMLEFT)
        proposed->left = proposed->right - outer_w;
    else
        proposed->right = proposed->left + outer_w;

    if (edge == WMSZ_TOP || edge == WMSZ_TOPLEFT || edge == WMSZ_TOPRIGHT)
        proposed->top = proposed->bottom - outer_h;
    else
        proposed->bottom = proposed->top + outer_h;
}

void force_square_client(HWND hwnd) {
    RECT outer{}, client{};
    if (!GetWindowRect(hwnd, &outer) || !GetClientRect(hwnd, &client)) return;
    int border_w = (outer.right - outer.left) - (client.right - client.left);
    int border_h = (outer.bottom - outer.top) - (client.bottom - client.top);
    int side = min(client.right - client.left, client.bottom - client.top);
    if (side < kMinimumWindowSide) side = kMinimumWindowSide;
    SetWindowPos(hwnd, nullptr, 0, 0, side + border_w, side + border_h,
        SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE);
}

void maximize_square(HWND hwnd) {
    HMONITOR monitor = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST);
    MONITORINFO info{sizeof(info)};
    int border_w = 0, border_h = 0;
    if (!GetMonitorInfoW(monitor, &info) || !non_client_size(hwnd, border_w, border_h)) return;
    int work_w = info.rcWork.right - info.rcWork.left;
    int work_h = info.rcWork.bottom - info.rcWork.top;
    int side = min(work_w - border_w, work_h - border_h);
    int outer_w = side + border_w, outer_h = side + border_h;
    int x = info.rcWork.left + (work_w - outer_w) / 2;
    int y = info.rcWork.top + (work_h - outer_h) / 2;
    ShowWindow(hwnd, SW_RESTORE);
    SetWindowPos(hwnd, nullptr, x, y, outer_w, outer_h,
        SWP_NOZORDER | SWP_NOACTIVATE);
}

bool same_process_window(HWND hwnd) {
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(hwnd)) return false;
    RECT rc{};
    return GetClientRect(hwnd, &rc) && rc.right > 100 && rc.bottom > 100;
}

BOOL CALLBACK find_window_callback(HWND hwnd, LPARAM) {
    if (same_process_window(hwnd)) {
        g_window = hwnd;
        return FALSE;
    }
    return TRUE;
}

bool resolve_cocos() {
    HMODULE cocos = GetModuleHandleW(L"libcocos2d.dll");
    if (!cocos) return false;
    g_get_director = reinterpret_cast<DirectorGetInstance>(GetProcAddress(
        cocos, "?getInstance@Director@cocos2d@@SAPAV12@XZ"));
    g_get_view = reinterpret_cast<DirectorGetOpenGLView>(GetProcAddress(
        cocos, "?getOpenGLView@Director@cocos2d@@QAEPAVGLView@2@XZ"));
    g_touch_begin = reinterpret_cast<HandleTouches>(GetProcAddress(
        cocos, "?handleTouchesBegin@GLView@cocos2d@@UAEXHQAHQAM1@Z"));
    g_touch_move = reinterpret_cast<HandleTouches>(GetProcAddress(
        cocos, "?handleTouchesMove@GLView@cocos2d@@UAEXHQAHQAM1@Z"));
    g_touch_end = reinterpret_cast<HandleTouches>(GetProcAddress(
        cocos, "?handleTouchesEnd@GLView@cocos2d@@UAEXHQAHQAM1@Z"));
    return g_get_director && g_get_view && g_touch_begin && g_touch_move && g_touch_end;
}

bool resolve_opengl() {
    if (g_gl_read_pixels && g_gl_get_error && g_gl_read_buffer && g_gl_pixel_store_i)
        return true;
    HMODULE gl = GetModuleHandleW(L"opengl32.dll");
    if (!gl) gl = LoadLibraryW(L"opengl32.dll");
    if (!gl) return false;
    g_gl_read_pixels = reinterpret_cast<GlReadPixels>(GetProcAddress(gl, "glReadPixels"));
    g_gl_get_error = reinterpret_cast<GlGetError>(GetProcAddress(gl, "glGetError"));
    g_gl_read_buffer = reinterpret_cast<GlReadBuffer>(GetProcAddress(gl, "glReadBuffer"));
    g_gl_pixel_store_i = reinterpret_cast<GlPixelStorei>(GetProcAddress(gl, "glPixelStorei"));
    return g_gl_read_pixels && g_gl_get_error && g_gl_read_buffer && g_gl_pixel_store_i;
}

bool ensure_capture_mapping(DWORD pixel_bytes) {
    const DWORD required = static_cast<DWORD>(sizeof(CaptureHeader)) + pixel_bytes;
    if (g_capture_header && g_capture_capacity >= required) return true;
    if (g_capture_header) {
        UnmapViewOfFile(g_capture_header);
        g_capture_header = nullptr;
    }
    if (g_capture_mapping) {
        CloseHandle(g_capture_mapping);
        g_capture_mapping = nullptr;
    }
    wchar_t name[96]{};
    swprintf_s(name, L"Local\\KVTM-Capture-%lu", GetCurrentProcessId());
    g_capture_mapping = CreateFileMappingW(
        INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0, required, name);
    if (!g_capture_mapping) return false;
    g_capture_header = static_cast<CaptureHeader*>(
        MapViewOfFile(g_capture_mapping, FILE_MAP_ALL_ACCESS, 0, 0, required));
    if (!g_capture_header) {
        CloseHandle(g_capture_mapping);
        g_capture_mapping = nullptr;
        return false;
    }
    g_capture_capacity = required;
    return true;
}

LONG dispatch_capture(CaptureCommand* command) {
    if (!command || !g_window || !resolve_opengl()) return ERROR_PROC_NOT_FOUND;
    RECT client{};
    if (!GetClientRect(g_window, &client)) return GetLastError();
    const DWORD width = static_cast<DWORD>(client.right - client.left);
    const DWORD height = static_cast<DWORD>(client.bottom - client.top);
    if (!width || !height || width > 8192 || height > 8192) return ERROR_INVALID_DATA;
    const ULONGLONG bytes64 = static_cast<ULONGLONG>(width) * height * 4u;
    if (bytes64 > kMaxCaptureBytes) return ERROR_NOT_ENOUGH_MEMORY;
    const DWORD stride = width * 4u;
    const DWORD pixel_bytes = static_cast<DWORD>(bytes64);
    if (!ensure_capture_mapping(pixel_bytes)) return GetLastError();

    CaptureHeader* header = g_capture_header;
    std::memcpy(header->magic, "KCAP", 4);
    header->version = kCaptureVersion;
    header->header_size = sizeof(CaptureHeader);
    header->width = width;
    header->height = height;
    header->stride = stride;
    header->pixel_format = kPixelFormatBgra8TopDown;
    header->buffer_size = pixel_bytes;
    header->status = 1;
    MemoryBarrier();

    auto* pixels = reinterpret_cast<unsigned char*>(header) + sizeof(CaptureHeader);
    while (g_gl_get_error() != 0) {}
    g_gl_pixel_store_i(GL_PACK_ALIGNMENT_VALUE, 1);
    g_gl_read_buffer(GL_FRONT_VALUE);
    g_gl_read_pixels(
        0, 0, static_cast<int>(width), static_cast<int>(height),
        GL_BGRA_VALUE, GL_UNSIGNED_BYTE_VALUE, pixels);
    unsigned int gl_error = g_gl_get_error();
    if (gl_error != 0) {
        while (g_gl_get_error() != 0) {}
        g_gl_read_buffer(GL_BACK_VALUE);
        g_gl_read_pixels(
            0, 0, static_cast<int>(width), static_cast<int>(height),
            GL_BGRA_VALUE, GL_UNSIGNED_BYTE_VALUE, pixels);
        gl_error = g_gl_get_error();
    }
    if (gl_error != 0) {
        header->status = 3;
        return ERROR_READ_FAULT;
    }

    // GameClientJS presents this OpenGL surface rotated 180 degrees relative
    // to the logical game coordinates. Normalize the shared frame once in
    // native code so Live View and AUTO consume the same top-down image.
    auto* words = reinterpret_cast<std::uint32_t*>(pixels);
    const size_t pixel_count = static_cast<size_t>(width) * height;
    for (size_t left = 0, right = pixel_count - 1; left < right; ++left, --right) {
        const std::uint32_t value = words[left];
        words[left] = words[right];
        words[right] = value;
    }

    const DWORD frame = static_cast<DWORD>(InterlockedIncrement(&g_capture_frame));
    header->frame_id = frame;
    header->timestamp_ms = GetTickCount64();
    MemoryBarrier();
    header->status = 2;
    command->frame_id = frame;
    command->width = width;
    command->height = height;
    command->stride = stride;
    return ERROR_SUCCESS;
}

LONG dispatch_touch(TouchCommand* command) {
    if (!command || !resolve_cocos()) return ERROR_PROC_NOT_FOUND;
    void* director = g_get_director();
    void* view = director ? g_get_view(director) : nullptr;
    if (!view) return ERROR_NOT_READY;

    RECT client{};
    if (!GetClientRect(g_window, &client)) return GetLastError();
    float xs[1] = {command->x * static_cast<float>(client.right) / 1000.0f};
    float ys[1] = {command->y * static_cast<float>(client.bottom) / 1000.0f};
    int ids[1] = {0};
    switch (command->phase) {
        case Phase::Down: g_touch_begin(view, 1, ids, xs, ys); break;
        case Phase::Move: g_touch_move(view, 1, ids, xs, ys); break;
        case Phase::Up: g_touch_end(view, 1, ids, xs, ys); break;
        default: return ERROR_INVALID_PARAMETER;
    }
    return ERROR_SUCCESS;
}

LRESULT CALLBACK bridge_window_proc(HWND hwnd, UINT message, WPARAM wp, LPARAM lp) {
    if (message == WM_KVTM_TOUCH) {
        auto* command = reinterpret_cast<TouchCommand*>(lp);
        command->result = dispatch_touch(command);
        return command->result;
    }
    if (message == WM_KVTM_CAPTURE) {
        auto* command = reinterpret_cast<CaptureCommand*>(lp);
        command->result = dispatch_capture(command);
        return command->result;
    }
    if (message == WM_SIZING) {
        make_sizing_rect_square(hwnd, wp, reinterpret_cast<RECT*>(lp));
        return TRUE;
    }
    if (message == WM_SYSCOMMAND && (wp & 0xFFF0) == SC_MAXIMIZE) {
        maximize_square(hwnd);
        return 0;
    }
    if (message == WM_EXITSIZEMOVE) {
        force_square_client(hwnd);
    }
    return CallWindowProcW(g_previous_proc, hwnd, message, wp, lp);
}

bool attach_window() {
    for (int attempt = 0; attempt < 100 && !g_window; ++attempt) {
        EnumWindows(find_window_callback, 0);
        if (!g_window) Sleep(100);
    }
    if (!g_window || GetPropW(g_window, kWindowProperty)) return false;
    SetLastError(ERROR_SUCCESS);
    g_previous_proc = reinterpret_cast<WNDPROC>(SetWindowLongPtrW(
        g_window, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(bridge_window_proc)));
    if (!g_previous_proc && GetLastError() != ERROR_SUCCESS) return false;
    SetPropW(g_window, kWindowProperty, g_self);
    force_square_client(g_window);
    return true;
}

bool parse_command(const char* line, TouchCommand& command) {
    char name[16]{};
    float x = 0, y = 0;
    if (std::sscanf(line, "%15s %f %f", name, &x, &y) != 3) return false;
    if (std::strcmp(name, "DOWN") == 0) command.phase = Phase::Down;
    else if (std::strcmp(name, "MOVE") == 0) command.phase = Phase::Move;
    else if (std::strcmp(name, "UP") == 0) command.phase = Phase::Up;
    else return false;
    if (x < 0 || x > 1000 || y < 0 || y > 1000) return false;
    command.x = x; command.y = y; command.result = ERROR_SUCCESS;
    return true;
}

DWORD WINAPI pipe_thread(void*) {
    if (!attach_window() || !resolve_cocos()) return 1;
    wchar_t pipe_name[128]{};
    swprintf_s(pipe_name, L"\\\\.\\pipe\\KVTM-Cocos-%lu", GetCurrentProcessId());
    HANDLE pipe = INVALID_HANDLE_VALUE;
    for (;;) {
        if (pipe == INVALID_HANDLE_VALUE) {
            pipe = CreateNamedPipeW(pipe_name, PIPE_ACCESS_DUPLEX,
                PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
                1, 256, 256, 0, nullptr);
            if (pipe == INVALID_HANDLE_VALUE) { Sleep(100); continue; }
        }
        BOOL connected = ConnectNamedPipe(pipe, nullptr) || GetLastError() == ERROR_PIPE_CONNECTED;
        if (connected) {
            char input[128]{}; DWORD read = 0;
            if (ReadFile(pipe, input, sizeof(input) - 1, &read, nullptr)) {
                input[read] = 0;
                const char* response = "ERR PARSE\n";
                char output[64]{};
                if (std::strncmp(input, "PING", 4) == 0) {
                    response = "OK PONG CAPTURE1\n";
                } else if (std::strncmp(input, "CAPTURE", 7) == 0) {
                    CaptureCommand command{};
                    SendMessageW(
                        g_window, WM_KVTM_CAPTURE, 0,
                        reinterpret_cast<LPARAM>(&command));
                    if (command.result == ERROR_SUCCESS) {
                        sprintf_s(
                            output, "OK FRAME %lu %lu %lu %lu\n",
                            command.frame_id, command.width,
                            command.height, command.stride);
                    } else {
                        sprintf_s(output, "ERR %ld\n", command.result);
                    }
                    response = output;
                } else {
                    TouchCommand command{};
                    if (parse_command(input, command)) {
                        SendMessageW(g_window, WM_KVTM_TOUCH, 0, reinterpret_cast<LPARAM>(&command));
                        sprintf_s(output, command.result == ERROR_SUCCESS ? "OK\n" : "ERR %ld\n", command.result);
                        response = output;
                    }
                }
                DWORD written = 0;
                WriteFile(pipe, response, static_cast<DWORD>(std::strlen(response)), &written, nullptr);
            }
        }
        FlushFileBuffers(pipe);
        DisconnectNamedPipe(pipe);
    }
}
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = instance;
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, pipe_thread, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
