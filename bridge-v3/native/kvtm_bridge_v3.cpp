// KVTM Bridge V3 hard FPS cap wrapper.
//
// The historical CAPTURE3/input implementation lives byte-for-byte in
// kvtm_bridge_v3_base.cpp.  This wrapper only intercepts the bridge FPS message
// and installs a native present-path governor.  Keeping capture/input isolated
// makes the GPU experiment easy to roll back and prevents AUTO regressions.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdint>
#include <cstring>

#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif

LRESULT WINAPI KvtmBridgeBaseSendMessageW(HWND, UINT, WPARAM, LPARAM);

#define SendMessageW KvtmBridgeBaseSendMessageW
#define DllMain KvtmBridgeBaseDllMain
#include "kvtm_bridge_v3_base.cpp"
#undef DllMain
#undef SendMessageW

namespace kvtm_hardcap {

using SwapBuffersFn = BOOL (WINAPI*)(HDC);
using WglSwapLayerBuffersFn = BOOL (WINAPI*)(HDC, UINT);
using CreateWaitableTimerExWFn = HANDLE (WINAPI*)(
    LPSECURITY_ATTRIBUTES, LPCWSTR, DWORD, DWORD);

volatile LONG g_target_fps = 0;
volatile LONG g_hook_ready = 0;
LONGLONG g_qpc_frequency = 0;
SwapBuffersFn g_original_swap_buffers = nullptr;
WglSwapLayerBuffersFn g_original_wgl_swap_layer_buffers = nullptr;

thread_local HANDLE t_waitable_timer = nullptr;
thread_local LONGLONG t_next_deadline = 0;
thread_local LONG t_last_fps = 0;

HANDLE ensure_waitable_timer() {
    if (t_waitable_timer) return t_waitable_timer;

    HMODULE kernel32 = GetModuleHandleW(L"kernel32.dll");
    auto create_ex = kernel32
        ? reinterpret_cast<CreateWaitableTimerExWFn>(
              GetProcAddress(kernel32, "CreateWaitableTimerExW"))
        : nullptr;
    if (create_ex) {
        t_waitable_timer = create_ex(
            nullptr, nullptr, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION,
            TIMER_ALL_ACCESS);
    }
    if (!t_waitable_timer) {
        t_waitable_timer = CreateWaitableTimerW(nullptr, FALSE, nullptr);
    }
    return t_waitable_timer;
}

void pace_after_present() {
    const LONG fps = InterlockedCompareExchange(
        const_cast<volatile LONG*>(&g_target_fps), 0, 0);
    if (fps < 5 || fps > 120 || g_qpc_frequency <= 0) return;

    LARGE_INTEGER now{};
    if (!QueryPerformanceCounter(&now)) return;

    const LONGLONG period = g_qpc_frequency / static_cast<LONGLONG>(fps);
    if (period <= 0) return;

    if (t_last_fps != fps || t_next_deadline <= 0 ||
        now.QuadPart > t_next_deadline + period * 2) {
        t_last_fps = fps;
        t_next_deadline = now.QuadPart + period;
    } else if (t_next_deadline <= now.QuadPart) {
        const LONGLONG overdue = now.QuadPart - t_next_deadline;
        const LONGLONG missed = overdue / period + 1;
        t_next_deadline += missed * period;
    }

    const LONGLONG remaining = t_next_deadline - now.QuadPart;
    if (remaining <= 0) return;

    HANDLE timer = ensure_waitable_timer();
    if (!timer) return;

    LONGLONG due_100ns = remaining * 10000000LL / g_qpc_frequency;
    if (due_100ns < 1) due_100ns = 1;
    LARGE_INTEGER due{};
    due.QuadPart = -due_100ns;

    if (SetWaitableTimer(timer, &due, 0, nullptr, nullptr, FALSE)) {
        WaitForSingleObject(timer, INFINITE);
    }
}

BOOL WINAPI hooked_swap_buffers(HDC dc) {
    const BOOL result = g_original_swap_buffers
        ? g_original_swap_buffers(dc)
        : FALSE;
    if (result) pace_after_present();
    return result;
}

BOOL WINAPI hooked_wgl_swap_layer_buffers(HDC dc, UINT planes) {
    const BOOL result = g_original_wgl_swap_layer_buffers
        ? g_original_wgl_swap_layer_buffers(dc, planes)
        : FALSE;
    if (result) pace_after_present();
    return result;
}

bool patch_iat_target(
    HMODULE module,
    const char* import_dll,
    FARPROC target,
    FARPROC replacement) {
    if (!module || !import_dll || !target || !replacement) return false;

    auto* base = reinterpret_cast<unsigned char*>(module);
    auto* dos = reinterpret_cast<IMAGE_DOS_HEADER*>(base);
    if (dos->e_magic != IMAGE_DOS_SIGNATURE || dos->e_lfanew <= 0)
        return false;
    auto* nt = reinterpret_cast<IMAGE_NT_HEADERS*>(base + dos->e_lfanew);
    if (nt->Signature != IMAGE_NT_SIGNATURE) return false;

    const auto& directory =
        nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    if (!directory.VirtualAddress || !directory.Size) return false;

    auto* descriptor = reinterpret_cast<IMAGE_IMPORT_DESCRIPTOR*>(
        base + directory.VirtualAddress);
    bool patched = false;
    for (; descriptor->Name; ++descriptor) {
        const char* dll_name = reinterpret_cast<const char*>(
            base + descriptor->Name);
        if (_stricmp(dll_name, import_dll) != 0) continue;

        auto* thunk = reinterpret_cast<IMAGE_THUNK_DATA*>(
            base + descriptor->FirstThunk);
        for (; thunk->u1.Function; ++thunk) {
            const auto current = reinterpret_cast<FARPROC>(
                static_cast<ULONG_PTR>(thunk->u1.Function));
            if (current == replacement) {
                patched = true;
                continue;
            }
            if (current != target) continue;

            DWORD old_protect = 0;
            if (!VirtualProtect(
                    &thunk->u1.Function, sizeof(thunk->u1.Function),
                    PAGE_READWRITE, &old_protect)) {
                continue;
            }
            thunk->u1.Function = reinterpret_cast<ULONG_PTR>(replacement);
            DWORD restored = 0;
            VirtualProtect(
                &thunk->u1.Function, sizeof(thunk->u1.Function),
                old_protect, &restored);
            FlushInstructionCache(
                GetCurrentProcess(), &thunk->u1.Function,
                sizeof(thunk->u1.Function));
            patched = true;
        }
    }
    return patched;
}

bool patch_modules(
    const char* import_dll,
    FARPROC target,
    FARPROC replacement) {
    bool patched = false;
    HMODULE modules[2] = {
        GetModuleHandleW(nullptr),
        GetModuleHandleW(L"libcocos2d.dll"),
    };
    for (HMODULE module : modules) {
        if (module) {
            patched = patch_iat_target(
                module, import_dll, target, replacement) || patched;
        }
    }
    return patched;
}

bool install_present_hook() {
    if (InterlockedCompareExchange(
            const_cast<volatile LONG*>(&g_hook_ready), 0, 0) == 1) {
        return true;
    }

    LARGE_INTEGER frequency{};
    if (!QueryPerformanceFrequency(&frequency) || frequency.QuadPart <= 0)
        return false;
    g_qpc_frequency = frequency.QuadPart;

    // Prefer the normal GDI SwapBuffers path.  Only if the executable/Cocos
    // imports no such symbol do we fall back to wglSwapLayerBuffers.  Hooking
    // one present primitive avoids accidentally pacing twice per frame.
    HMODULE gdi32 = GetModuleHandleW(L"gdi32.dll");
    if (!gdi32) gdi32 = LoadLibraryW(L"gdi32.dll");
    if (gdi32) {
        auto target = reinterpret_cast<SwapBuffersFn>(
            GetProcAddress(gdi32, "SwapBuffers"));
        if (target) {
            g_original_swap_buffers = target;
            if (patch_modules(
                    "GDI32.dll",
                    reinterpret_cast<FARPROC>(target),
                    reinterpret_cast<FARPROC>(&hooked_swap_buffers))) {
                InterlockedExchange(
                    const_cast<volatile LONG*>(&g_hook_ready), 1);
                return true;
            }
        }
    }

    HMODULE opengl32 = GetModuleHandleW(L"opengl32.dll");
    if (!opengl32) opengl32 = LoadLibraryW(L"opengl32.dll");
    if (opengl32) {
        auto target = reinterpret_cast<WglSwapLayerBuffersFn>(
            GetProcAddress(opengl32, "wglSwapLayerBuffers"));
        if (target) {
            g_original_wgl_swap_layer_buffers = target;
            if (patch_modules(
                    "OPENGL32.dll",
                    reinterpret_cast<FARPROC>(target),
                    reinterpret_cast<FARPROC>(&hooked_wgl_swap_layer_buffers))) {
                InterlockedExchange(
                    const_cast<volatile LONG*>(&g_hook_ready), 1);
                return true;
            }
        }
    }
    return false;
}

LONG set_target(int fps) {
    if (fps < 5 || fps > 120) return ERROR_INVALID_PARAMETER;
    if (!install_present_hook()) return ERROR_PROC_NOT_FOUND;
    InterlockedExchange(
        const_cast<volatile LONG*>(&g_target_fps), static_cast<LONG>(fps));
    return ERROR_SUCCESS;
}

}  // namespace kvtm_hardcap

// The base bridge routes touch/capture/FPS commands through SendMessageW.
// Intercept only WM_KVTM_FPS; all other messages are forwarded unchanged.
LRESULT WINAPI KvtmBridgeBaseSendMessageW(
    HWND hwnd, UINT message, WPARAM wp, LPARAM lp) {
    if (message == WM_KVTM_FPS && lp) {
        auto* command = reinterpret_cast<FpsCommand*>(lp);
        const LONG hardcap = kvtm_hardcap::set_target(command->fps);
        if (hardcap != ERROR_SUCCESS) {
            command->result = hardcap;
            return hardcap;
        }
    }
    return ::SendMessageW(hwnd, message, wp, lp);
}

BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID reserved) {
    return KvtmBridgeBaseDllMain(instance, reason, reserved);
}
