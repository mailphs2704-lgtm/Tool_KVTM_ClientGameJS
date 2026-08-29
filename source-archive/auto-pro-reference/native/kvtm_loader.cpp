#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cwchar>

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) { std::fwprintf(stderr, L"Usage: kvtm_loader.exe PID DLL_PATH\n"); return 2; }
    DWORD pid = wcstoul(argv[1], nullptr, 10);
    wchar_t full[MAX_PATH]{};
    if (!GetFullPathNameW(argv[2], MAX_PATH, full, nullptr)) return 3;
    HANDLE process = OpenProcess(PROCESS_CREATE_THREAD | PROCESS_QUERY_INFORMATION |
        PROCESS_VM_OPERATION | PROCESS_VM_WRITE | PROCESS_VM_READ, FALSE, pid);
    if (!process) { std::fwprintf(stderr, L"OpenProcess: %lu\n", GetLastError()); return 4; }
    SIZE_T bytes = (wcslen(full) + 1) * sizeof(wchar_t);
    void* remote = VirtualAllocEx(process, nullptr, bytes, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!remote || !WriteProcessMemory(process, remote, full, bytes, nullptr)) {
        std::fwprintf(stderr, L"WriteProcessMemory: %lu\n", GetLastError()); CloseHandle(process); return 5;
    }
    auto load_library = reinterpret_cast<LPTHREAD_START_ROUTINE>(
        GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW"));
    HANDLE thread = CreateRemoteThread(process, nullptr, 0, load_library, remote, 0, nullptr);
    if (!thread) { std::fwprintf(stderr, L"CreateRemoteThread: %lu\n", GetLastError()); return 6; }
    WaitForSingleObject(thread, 10000);
    DWORD module = 0; GetExitCodeThread(thread, &module);
    CloseHandle(thread); VirtualFreeEx(process, remote, 0, MEM_RELEASE); CloseHandle(process);
    if (!module) { std::fwprintf(stderr, L"LoadLibraryW returned NULL\n"); return 7; }
    std::wprintf(L"OK %lu\n", pid);
    return 0;
}
