using System;
using System.Diagnostics;
using System.IO;

namespace KvtmToolCry.Updater
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            try
            {
                string launcherRoot = AppDomain.CurrentDomain.BaseDirectory;
                string script = Path.Combine(launcherRoot, "Kvtm_tool_Cry_Update.ps1");
                if (!File.Exists(script))
                {
                    return 2;
                }

                var psi = new ProcessStartInfo
                {
                    FileName = "powershell.exe",
                    Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File \"" + script + "\" -UpdateOnly",
                    WorkingDirectory = launcherRoot,
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden
                };
                using (Process process = Process.Start(psi))
                {
                    process.WaitForExit();
                    return process.ExitCode;
                }
            }
            catch
            {
                return 3;
            }
        }
    }
}
