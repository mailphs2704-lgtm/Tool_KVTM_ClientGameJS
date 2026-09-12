using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Text;

internal static class KvtmToolCrySetup
{
    private const string FooterMagic = "KVTMCRY1";
    private const int FooterSize = 16;

    [STAThread]
    private static int Main()
    {
        string tempRoot = null;
        try
        {
            string self = Assembly.GetExecutingAssembly().Location;
            long bundleLength;
            long bundleOffset;

            using (FileStream input = new FileStream(self, FileMode.Open, FileAccess.Read, FileShare.Read))
            {
                if (input.Length <= FooterSize)
                    throw new InvalidDataException("Kvtm_tool_Cry Setup bundle footer is missing.");

                input.Seek(-FooterSize, SeekOrigin.End);
                byte[] footer = new byte[FooterSize];
                ReadExact(input, footer, 0, footer.Length);

                long encodedLength = BitConverter.ToInt64(footer, 0);
                string magic = Encoding.ASCII.GetString(footer, 8, 8);
                if (!String.Equals(magic, FooterMagic, StringComparison.Ordinal))
                    throw new InvalidDataException("Kvtm_tool_Cry Setup footer identity mismatch.");
                if (encodedLength <= 0 || encodedLength > input.Length - FooterSize)
                    throw new InvalidDataException("Kvtm_tool_Cry Setup bundle length is invalid.");

                bundleLength = encodedLength;
                bundleOffset = input.Length - FooterSize - bundleLength;
            }

            tempRoot = Path.Combine(Path.GetTempPath(), "Kvtm_tool_Cry_Setup_" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(tempRoot);
            string bundlePath = Path.Combine(tempRoot, "bundle.zip");

            using (FileStream input = new FileStream(self, FileMode.Open, FileAccess.Read, FileShare.Read))
            using (FileStream output = new FileStream(bundlePath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                input.Seek(bundleOffset, SeekOrigin.Begin);
                CopyExact(input, output, bundleLength);
            }

            string extractRoot = Path.Combine(tempRoot, "bundle");
            Directory.CreateDirectory(extractRoot);
            ZipFile.ExtractToDirectory(bundlePath, extractRoot);

            string installScript = Path.Combine(extractRoot, "Install-KvtmToolCry.ps1");
            if (!File.Exists(installScript))
                throw new FileNotFoundException("Kvtm_tool_Cry Setup installer script is missing.", installScript);

            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "powershell.exe";
            psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + installScript + "\"";
            psi.WorkingDirectory = extractRoot;
            psi.UseShellExecute = false;
            psi.CreateNoWindow = true;

            using (Process process = Process.Start(psi))
            {
                if (process == null)
                    throw new InvalidOperationException("Cannot start Kvtm_tool_Cry installer bootstrap.");
                process.WaitForExit();
                if (process.ExitCode != 0)
                    return process.ExitCode;
            }

            return 0;
        }
        catch (Exception ex)
        {
            try
            {
                System.Windows.Forms.MessageBox.Show(
                    ex.Message,
                    "Kvtm_tool_Cry Setup",
                    System.Windows.Forms.MessageBoxButtons.OK,
                    System.Windows.Forms.MessageBoxIcon.Error
                );
            }
            catch { }
            return 2;
        }
        finally
        {
            if (!String.IsNullOrWhiteSpace(tempRoot))
            {
                try { Directory.Delete(tempRoot, true); } catch { }
            }
        }
    }

    private static void ReadExact(Stream stream, byte[] buffer, int offset, int count)
    {
        int readTotal = 0;
        while (readTotal < count)
        {
            int read = stream.Read(buffer, offset + readTotal, count - readTotal);
            if (read <= 0)
                throw new EndOfStreamException("Unexpected end of Kvtm_tool_Cry Setup stream.");
            readTotal += read;
        }
    }

    private static void CopyExact(Stream input, Stream output, long count)
    {
        byte[] buffer = new byte[1024 * 1024];
        long remaining = count;
        while (remaining > 0)
        {
            int wanted = (int)Math.Min(buffer.Length, remaining);
            int read = input.Read(buffer, 0, wanted);
            if (read <= 0)
                throw new EndOfStreamException("Unexpected end of Kvtm_tool_Cry Setup bundle.");
            output.Write(buffer, 0, read);
            remaining -= read;
        }
    }
}
