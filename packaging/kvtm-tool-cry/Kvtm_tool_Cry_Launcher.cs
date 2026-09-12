using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;

namespace KvtmToolCry.Launcher
{
    internal static class Program
    {
        [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern int MessageBoxW(IntPtr hWnd, string text, string caption, uint type);

        private static void ShowFailure(string message)
        {
            try
            {
                string dataRoot = Path.Combine(
                    Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                    "Kvtm_tool_Cry"
                );
                string logPath = Path.Combine(dataRoot, "logs", "launcher.log");
                MessageBoxW(
                    IntPtr.Zero,
                    message + "\r\n\r\nLog: " + logPath,
                    "Kvtm_tool_Cry - Launch failed",
                    0x00000010U
                );
            }
            catch
            {
                // Never hide the original launcher exit code because diagnostics failed.
            }
        }

        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                string launcherRoot = AppDomain.CurrentDomain.BaseDirectory;
                string script = Path.Combine(launcherRoot, "Kvtm_tool_Cry_Launch.ps1");
                if (!File.Exists(script))
                {
                    ShowFailure("Missing launcher bootstrap: " + script);
                    return 2;
                }

                var psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + script + "\"",
                    WorkingDirectory = launcherRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                using (Process process = Process.Start(psi))
                {
                    process.WaitForExit();
                    int rc = process.ExitCode;
                    if (rc != 0)
                    {
                        ShowFailure("Kvtm_tool_Cry could not start. Launcher exit code=" + rc);
                    }
                    return rc;
                }
            }
            catch (Exception exc)
            {
                ShowFailure(exc.GetType().Name + ": " + exc.Message);
                return 3;
            }
        }
    }
}
