// KVTM Bridge V3 - capture + input only.
// Intentionally excluded: resize, DPI, window placement, layout and AUTO logic.
// This file is isolated from the production bridge until V3 live gates pass.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <sstream>

namespace {
constexpr UINT WM_KVTM_TOUCH = WM_APP + 0x417;
constexpr UINT WM_KVTM_CAPTURE = WM_APP + 0x418;
constexpr wchar_t kWindowProperty[] = L"KVTM_BRIDGE_V3_CAPTURE_INPUT_ONLY";
constexpr DWORD kCaptureVersion = 3;
constexpr DWORD kPixelFormatBgra8TopDown = 2;
constexpr DWORD kMaxCaptureBytes = 64u * 1024u * 1024u;
constexpr DWORD kCaptureModeLegacy = 0;
constexpr DWORD kCaptureModeWriterMap = 1;
constexpr unsigned int GL_FRONT_VALUE = 0x0404;
constexpr unsigned int GL_BACK_VALUE = 0x0405;
constexpr unsigned int GL_PACK_ALIGNMENT_VALUE = 0x0D05;
constexpr unsigned int GL_BGRA_VALUE = 0x80E1;
constexpr unsigned int GL_UNSIGNED_BYTE_VALUE = 0x1401;

enum class Phase : int { Down = 1, Move = 2, Up = 3 };
struct TouchCommand { Phase phase; float x; float y; LONG result; };
struct GesturePoint { float x; float y; };
struct GestureCommand {
    int segment_steps;
    int point_count;
    GesturePoint points[32];
};
struct CaptureCommand {
    LONG result;
    DWORD frame_id;
    DWORD width;
    DWORD height;
    DWORD stride;
    DWORD mapping_mode;
    ULONGLONG writer_id;
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
constexpr DWORD kCaptureMappingBytes =
    static_cast<DWORD>(sizeof(CaptureHeader)) + kMaxCaptureBytes;

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
volatile LONG g_capture_frame = 0;
HANDLE g_writer_capture_mapping = nullptr;
CaptureHeader* g_writer_capture_header = nullptr;
volatile LONG g_writer_capture_frame = 0;
HANDLE g_bridge_owner = nullptr;
ULONGLONG g_writer_id = 0;
UINT g_writer_capture_message = 0;

void initialize_writer_id() {
    LARGE_INTEGER counter{};
    QueryPerformanceCounter(&counter);
    const ULONGLONG pid = static_cast<ULONGLONG>(GetCurrentProcessId());
    const ULONGLONG tid = static_cast<ULONGLONG>(GetCurrentThreadId());
    const ULONGLONG module = static_cast<ULONGLONG>(
        reinterpret_cast<ULONG_PTR>(g_self));
    g_writer_id =
        static_cast<ULONGLONG>(counter.QuadPart) ^
        (GetTickCount64() << 7) ^
        (pid << 32) ^
        (tid << 17) ^
        (module << 3);
    if (!g_writer_id) g_writer_id = (pid << 32) | 1u;
}

bool initialize_writer_capture_message() {
    if (!g_writer_id) {
        SetLastError(ERROR_INVALID_DATA);
        return false;
    }
    wchar_t name[160]{};
    swprintf_s(
        name, L"KVTM_CAPTURE3_WRITERMSG1_%lu_%016llX",
        GetCurrentProcessId(),
        static_cast<unsigned long long>(g_writer_id));
    g_writer_capture_message = RegisterWindowMessageW(name);
    return g_writer_capture_message != 0;
}

bool claim_bridge_owner() {
    wchar_t name[96]{};
    swprintf_s(
        name, L"Local\\KVTM-BridgeV3-Owner-%lu", GetCurrentProcessId());
    SetLastError(ERROR_SUCCESS);
    HANDLE handle = CreateMutexW(nullptr, FALSE, name);
    const DWORD error = GetLastError();
    if (!handle) return false;
    if (error == ERROR_ALREADY_EXISTS) {
        CloseHandle(handle);
        SetLastError(ERROR_ALREADY_EXISTS);
        return false;
    }
    g_bridge_owner = handle;
    return true;
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

bool ensure_capture_mapping(
    DWORD pixel_bytes,
    DWORD mapping_mode,
    CaptureHeader** header_out,
    volatile LONG** frame_out) {
    if (!header_out || !frame_out || pixel_bytes > kMaxCaptureBytes) {
        SetLastError(pixel_bytes > kMaxCaptureBytes
            ? ERROR_NOT_ENOUGH_MEMORY : ERROR_INVALID_PARAMETER);
        return false;
    }
    if (mapping_mode != kCaptureModeLegacy &&
        mapping_mode != kCaptureModeWriterMap) {
        SetLastError(ERROR_INVALID_PARAMETER);
        return false;
    }

    HANDLE* mapping_slot = mapping_mode == kCaptureModeWriterMap
        ? &g_writer_capture_mapping : &g_capture_mapping;
    CaptureHeader** header_slot = mapping_mode == kCaptureModeWriterMap
        ? &g_writer_capture_header : &g_capture_header;
    volatile LONG* frame_slot = mapping_mode == kCaptureModeWriterMap
        ? &g_writer_capture_frame : &g_capture_frame;

    if (*header_slot && *mapping_slot) {
        *header_out = *header_slot;
        *frame_out = frame_slot;
        return true;
    }
    if (*header_slot || *mapping_slot) {
        SetLastError(ERROR_INVALID_HANDLE);
        return false;
    }

    wchar_t name[128]{};
    if (mapping_mode == kCaptureModeWriterMap) {
        swprintf_s(
            name, L"Local\\KVTM-CaptureV3-%lu-%016llX",
            GetCurrentProcessId(),
            static_cast<unsigned long long>(g_writer_id));
    } else {
        swprintf_s(
            name, L"Local\\KVTM-CaptureV3-%lu", GetCurrentProcessId());
    }

    SetLastError(ERROR_SUCCESS);
    *mapping_slot = CreateFileMappingW(
        INVALID_HANDLE_VALUE, nullptr, PAGE_READWRITE, 0,
        kCaptureMappingBytes, name);
    if (!*mapping_slot) return false;
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        CloseHandle(*mapping_slot);
        *mapping_slot = nullptr;
        SetLastError(ERROR_ALREADY_EXISTS);
        return false;
    }
    *header_slot = static_cast<CaptureHeader*>(
        MapViewOfFile(
            *mapping_slot, FILE_MAP_ALL_ACCESS, 0, 0,
            kCaptureMappingBytes));
    if (!*header_slot) {
        CloseHandle(*mapping_slot);
        *mapping_slot = nullptr;
        return false;
    }
    ZeroMemory(*header_slot, sizeof(CaptureHeader));
    *header_out = *header_slot;
    *frame_out = frame_slot;
    return true;
}

LONG dispatch_capture(CaptureCommand* command) {
    if (!command || !g_window || !resolve_opengl()) return ERROR_PROC_NOT_FOUND;
    if (command->mapping_mode != kCaptureModeLegacy &&
        command->mapping_mode != kCaptureModeWriterMap)
        return ERROR_INVALID_PARAMETER;

    RECT client{};
    if (!GetClientRect(g_window, &client)) return GetLastError();
    const DWORD width = static_cast<DWORD>(client.right - client.left);
    const DWORD height = static_cast<DWORD>(client.bottom - client.top);
    if (!width || !height || width > 8192 || height > 8192) return ERROR_INVALID_DATA;
    const ULONGLONG bytes64 = static_cast<ULONGLONG>(width) * height * 4u;
    if (bytes64 > kMaxCaptureBytes) return ERROR_NOT_ENOUGH_MEMORY;
    const DWORD stride = width * 4u;
    const DWORD pixel_bytes = static_cast<DWORD>(bytes64);

    CaptureHeader* header = nullptr;
    volatile LONG* frame_counter = nullptr;
    if (!ensure_capture_mapping(
            pixel_bytes, command->mapping_mode, &header, &frame_counter))
        return GetLastError();

    header->status = 1;
    MemoryBarrier();
    std::memcpy(header->magic, "KCAP", 4);
    header->version = kCaptureVersion;
    header->header_size = sizeof(CaptureHeader);
    header->width = width;
    header->height = height;
    header->stride = stride;
    header->pixel_format = kPixelFormatBgra8TopDown;
    header->buffer_size = pixel_bytes;
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
        MemoryBarrier();
        return ERROR_READ_FAULT;
    }

    auto* words = reinterpret_cast<std::uint32_t*>(pixels);
    const size_t row_words = static_cast<size_t>(width);
    for (size_t top = 0, bottom = static_cast<size_t>(height) - 1;
         top < bottom; ++top, --bottom) {
        auto* top_row = words + top * row_words;
        auto* bottom_row = words + bottom * row_words;
        for (size_t x = 0; x < row_words; ++x) {
            const std::uint32_t value = top_row[x];
            top_row[x] = bottom_row[x];
            bottom_row[x] = value;
        }
    }

    const DWORD frame = static_cast<DWORD>(InterlockedIncrement(frame_counter));
    header->frame_id = frame;
    header->timestamp_ms = GetTickCount64();
    MemoryBarrier();
    header->status = 2;
    MemoryBarrier();

    command->frame_id = frame;
    command->width = width;
    command->height = height;
    command->stride = stride;
    command->writer_id = command->mapping_mode == kCaptureModeWriterMap
        ? g_writer_id : 0;
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
    if (message == WM_KVTM_CAPTURE ||
        (g_writer_capture_message != 0 && message == g_writer_capture_message)) {
        auto* command = reinterpret_cast<CaptureCommand*>(lp);
        command->result = dispatch_capture(command);
        return command->result;
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
    if (!SetPropW(g_window, kWindowProperty, g_self)) {
        SetWindowLongPtrW(
            g_window, GWLP_WNDPROC, reinterpret_cast<LONG_PTR>(g_previous_proc));
        g_previous_proc = nullptr;
        return false;
    }
    if (GetPropW(g_window, kWindowProperty) != g_self) return false;
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

bool parse_gesture(const char* line, GestureCommand& gesture) {
    std::istringstream stream(line);
    std::string name;
    if (!(stream >> name >> gesture.segment_steps >> gesture.point_count))
        return false;
    if (name != "SWIPE" || gesture.segment_steps < 1 ||
        gesture.segment_steps > 400 || gesture.point_count < 2 ||
        gesture.point_count > 32)
        return false;
    for (int index = 0; index < gesture.point_count; ++index) {
        auto& point = gesture.points[index];
        if (!(stream >> point.x >> point.y) ||
            point.x < 0 || point.x > 1000 ||
            point.y < 0 || point.y > 1000)
            return false;
    }
    stream >> std::ws;
    return stream.eof();
}

LONG send_touch(Phase phase, float x, float y) {
    TouchCommand command{phase, x, y, ERROR_SUCCESS};
    SendMessageW(g_window, WM_KVTM_TOUCH, 0, reinterpret_cast<LPARAM>(&command));
    return command.result;
}

void wait_until(LONGLONG deadline, LONGLONG frequency) {
    LARGE_INTEGER now{};
    for (;;) {
        QueryPerformanceCounter(&now);
        const LONGLONG remaining = deadline - now.QuadPart;
        if (remaining <= 0) return;
        const DWORD remaining_ms = static_cast<DWORD>(remaining * 1000 / frequency);
        if (remaining_ms > 1) Sleep(remaining_ms - 1);
        else SwitchToThread();
    }
}

LONG dispatch_gesture(const GestureCommand& gesture, DWORD& actual_ms, DWORD& move_count) {
    LARGE_INTEGER frequency{}, started{}, finished{};
    if (!QueryPerformanceFrequency(&frequency) || !QueryPerformanceCounter(&started))
        return ERROR_NOT_SUPPORTED;
    LONG result = send_touch(
        Phase::Down, gesture.points[0].x, gesture.points[0].y);
    if (result != ERROR_SUCCESS) return result;

    move_count = 0;
    const LONGLONG step_ticks = frequency.QuadPart * 5 / 1000;
    for (int segment = 1; segment < gesture.point_count; ++segment) {
        const auto& start = gesture.points[segment - 1];
        const auto& end = gesture.points[segment];
        for (int step = 1; step <= gesture.segment_steps; ++step) {
            ++move_count;
            wait_until(
                started.QuadPart + static_cast<LONGLONG>(move_count) * step_ticks,
                frequency.QuadPart);
            const float ratio =
                static_cast<float>(step) / static_cast<float>(gesture.segment_steps);
            result = send_touch(
                Phase::Move,
                start.x + (end.x - start.x) * ratio,
                start.y + (end.y - start.y) * ratio);
            if (result != ERROR_SUCCESS) {
                send_touch(Phase::Up, end.x, end.y);
                return result;
            }
        }
    }
    const auto& last = gesture.points[gesture.point_count - 1];
    result = send_touch(Phase::Up, last.x, last.y);
    QueryPerformanceCounter(&finished);
    actual_ms = static_cast<DWORD>(
        (finished.QuadPart - started.QuadPart) * 1000 / frequency.QuadPart);
    return result;
}

DWORD WINAPI pipe_thread(void*) {
    if (!claim_bridge_owner()) return 1;
    if (!initialize_writer_capture_message()) return 2;
    if (!attach_window() || !resolve_cocos()) return 3;

    wchar_t pipe_name[128]{};
    swprintf_s(pipe_name, L"\\\\.\\pipe\\KVTM-CocosV3-%lu", GetCurrentProcessId());
    HANDLE pipe = CreateNamedPipeW(
        pipe_name,
        PIPE_ACCESS_DUPLEX | FILE_FLAG_FIRST_PIPE_INSTANCE,
        PIPE_TYPE_MESSAGE | PIPE_READMODE_MESSAGE | PIPE_WAIT,
        1, 4096, 4096, 0, nullptr);
    if (pipe == INVALID_HANDLE_VALUE) return 4;

    for (;;) {
        BOOL connected = ConnectNamedPipe(pipe, nullptr) ||
            GetLastError() == ERROR_PIPE_CONNECTED;
        if (connected) {
            for (;;) {
                char input[4096]{};
                DWORD read = 0;
                if (!ReadFile(pipe, input, sizeof(input) - 1, &read, nullptr) || !read)
                    break;
                input[read] = 0;
                const char* response = "ERR PARSE\n";
                char output[192]{};

                if (std::strncmp(input, "PING", 4) == 0) {
                    sprintf_s(
                        output,
                        "OK PONG KVTM_BRIDGE_V3 CAPTURE3 INPUT4 BATCH_SWIPE "
                        "NO_LAYOUT CAPTURE3_SYNC2 CAPTURE3_FIXEDMAP "
                        "CAPTURE3_WRITERMAP2 CAPTURE3_WRITERMSG1 %016llX\n",
                        static_cast<unsigned long long>(g_writer_id));
                    response = output;
                } else if (std::strncmp(input, "CAPTUREW", 8) == 0) {
                    CaptureCommand command{};
                    command.mapping_mode = kCaptureModeWriterMap;
                    if (!g_writer_capture_message) {
                        command.result = ERROR_NOT_READY;
                    } else {
                        SendMessageW(
                            g_window, g_writer_capture_message, 0,
                            reinterpret_cast<LPARAM>(&command));
                    }
                    if (command.result == ERROR_SUCCESS &&
                        command.writer_id == g_writer_id) {
                        sprintf_s(
                            output, "OK FRAMEW %lu %lu %lu %lu %016llX\n",
                            command.frame_id, command.width,
                            command.height, command.stride,
                            static_cast<unsigned long long>(command.writer_id));
                    } else if (command.result == ERROR_SUCCESS) {
                        sprintf_s(
                            output, "ERR WRITER %016llX %016llX\n",
                            static_cast<unsigned long long>(g_writer_id),
                            static_cast<unsigned long long>(command.writer_id));
                    } else {
                        sprintf_s(output, "ERR %ld\n", command.result);
                    }
                    response = output;
                } else if (std::strncmp(input, "CAPTURE", 7) == 0) {
                    CaptureCommand command{};
                    command.mapping_mode = kCaptureModeLegacy;
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
                } else if (std::strncmp(input, "SWIPE ", 6) == 0) {
                    GestureCommand gesture{};
                    if (parse_gesture(input, gesture)) {
                        DWORD actual_ms = 0, move_count = 0;
                        const LONG result =
                            dispatch_gesture(gesture, actual_ms, move_count);
                        if (result == ERROR_SUCCESS) {
                            sprintf_s(
                                output, "OK SWIPE %lu %lu\n",
                                actual_ms, move_count);
                        } else {
                            sprintf_s(output, "ERR %ld\n", result);
                        }
                        response = output;
                    }
                } else {
                    TouchCommand command{};
                    if (parse_command(input, command)) {
                        SendMessageW(
                            g_window, WM_KVTM_TOUCH, 0,
                            reinterpret_cast<LPARAM>(&command));
                        sprintf_s(
                            output,
                            command.result == ERROR_SUCCESS ? "OK\n" : "ERR %ld\n",
                            command.result);
                        response = output;
                    }
                }

                DWORD written = 0;
                if (!WriteFile(
                        pipe, response, static_cast<DWORD>(std::strlen(response)),
                        &written, nullptr))
                    break;
            }
        }
        FlushFileBuffers(pipe);
        DisconnectNamedPipe(pipe);
    }
}
}

extern "C" __declspec(dllexport) DWORD WINAPI KvtmBridgeProtocol() {
    return 3;
}

extern "C" __declspec(dllexport) BOOL WINAPI KvtmBridgeInstall(HWND hwnd) {
    if (!hwnd || !same_process_window(hwnd)) return FALSE;
    g_window = hwnd;
    return TRUE;
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) {
        g_self = instance;
        initialize_writer_id();
        DisableThreadLibraryCalls(instance);
        HANDLE thread = CreateThread(nullptr, 0, pipe_thread, nullptr, 0, nullptr);
        if (thread) CloseHandle(thread);
    }
    return TRUE;
}
