using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("灵感屿")]
[assembly: AssemblyProduct("Sparkspace")]
[assembly: AssemblyDescription("灵感屿桌面启动器")]
[assembly: AssemblyVersion("1.1.0.0")]

internal static class Launcher
{
    private static bool IsPythonFile(string path)
    {
        return !String.IsNullOrWhiteSpace(path) && File.Exists(path) &&
            path.IndexOf(@"\Microsoft\WindowsApps\", StringComparison.OrdinalIgnoreCase) < 0;
    }

    private static string FindPython(string bundledPath)
    {
        if (IsPythonFile(bundledPath)) return bundledPath;
        foreach (string entry in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(';'))
        {
            if (String.IsNullOrWhiteSpace(entry)) continue;
            try
            {
                string path = Path.Combine(entry.Trim().Trim('"'), "pythonw.exe");
                if (IsPythonFile(path)) return Path.GetFullPath(path);
            }
            catch (ArgumentException) { }
        }
        foreach (RegistryHive hive in new[] { RegistryHive.CurrentUser, RegistryHive.LocalMachine })
        foreach (RegistryView view in new[] { RegistryView.Registry64, RegistryView.Registry32 })
        {
            try
            {
                using (var registry = RegistryKey.OpenBaseKey(hive, view))
                using (var core = registry.OpenSubKey(@"SOFTWARE\Python\PythonCore"))
                {
                    if (core == null) continue;
                    foreach (string tag in core.GetSubKeyNames())
                    {
                        Version version;
                        if (!Version.TryParse(tag.Split('-')[0], out version) || version < new Version(3, 10)) continue;
                        using (var install = core.OpenSubKey(tag + @"\InstallPath"))
                        {
                            if (install == null) continue;
                            string path = install.GetValue("WindowedExecutablePath") as string;
                            if (IsPythonFile(path)) return path;
                            string directory = install.GetValue(null) as string;
                            if (!String.IsNullOrWhiteSpace(directory))
                            {
                                path = Path.Combine(directory, "pythonw.exe");
                                if (IsPythonFile(path)) return path;
                            }
                        }
                    }
                }
            }
            catch (System.Security.SecurityException) { }
            catch (UnauthorizedAccessException) { }
        }
        throw new FileNotFoundException("没有找到包含 Tkinter 的 Python 3.10 或更新版本。\r\n\r\n" +
            "请安装 Python 后重试。也可在项目目录运行 build-exe.ps1 -Pythonw \"实际 pythonw.exe 路径\" 指定路径重新构建。");
    }

    // Windows command-line quoting: quotes and trailing backslashes must survive intact.
    private static string Quote(string value)
    {
        var text = new StringBuilder("\"");
        int slashes = 0;
        foreach (char character in value)
        {
            if (character == '\\') { slashes++; continue; }
            text.Append('\\', character == '"' ? slashes * 2 + 1 : slashes);
            text.Append(character);
            slashes = 0;
        }
        return text.Append('\\', slashes * 2).Append('"').ToString();
    }

    private static int RunPython(string python, string root, string[] arguments)
    {
        var start = new ProcessStartInfo(python, String.Join(" ", arguments.Select(Quote)))
        {
            WorkingDirectory = root,
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardError = true,
            StandardErrorEncoding = Encoding.UTF8
        };
        start.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        using (var process = Process.Start(start))
        {
            string error = process.StandardError.ReadToEnd();
            process.WaitForExit();
            if (process.ExitCode != 0 && !String.IsNullOrWhiteSpace(error))
                throw new InvalidOperationException("启动脚本返回错误：\r\n" + error.Trim());
            // launch.pyw already displays its handled startup failures; avoid a second dialog.
            return process.ExitCode;
        }
    }

    [STAThread]
    private static int Main(string[] arguments)
    {
        bool selfTest = arguments.Length == 1 && arguments[0] == "--self-test";
        if (selfTest)
        {
            Console.SetOut(new StreamWriter(Console.OpenStandardOutput(), new UTF8Encoding(false)) { AutoFlush = true });
            Console.SetError(new StreamWriter(Console.OpenStandardError(), new UTF8Encoding(false)) { AutoFlush = true });
        }
        try
        {
            string root = AppDomain.CurrentDomain.BaseDirectory;
            string python;
            using (var resource = Assembly.GetExecutingAssembly().GetManifestResourceStream("Sparkspace.PythonwPath"))
            using (var reader = new StreamReader(resource, Encoding.UTF8))
                python = reader.ReadToEnd().Trim();
            python = FindPython(python);
            foreach (string file in new[] { "launch.pyw", "server.py", "quick_capture.pyw", "public/index.html" })
                if (!File.Exists(Path.Combine(root, file)))
                    throw new FileNotFoundException("缺少项目文件：" + file +
                        "\r\n\r\n请将 灵感屿.exe 保留在完整项目目录内。桌面入口请使用快捷方式，不要单独移动这个 exe。");
            string launch = Path.Combine(root, "launch.pyw");
            if (selfTest)
            {
                string[] samples = { "", "中文 路径", "\"quoted\"", "C:\\目录 空格\\", "slash\\\"quote" };
                string expected = String.Join(",", samples.Select(value =>
                    "bytes.fromhex('" + BitConverter.ToString(Encoding.UTF8.GetBytes(value)).Replace("-", "") + "').decode('utf-8')"));
                string probe = "import sys, tkinter, sqlite3, runpy; assert sys.version_info >= (3, 10); " +
                    "runpy.run_path(sys.argv[1], run_name='sparkspace_self_test'); assert sys.argv[2:] == [" + expected + "]";
                if (RunPython(python, root, new[] { "-c", probe, launch }.Concat(samples).ToArray()) != 0)
                    throw new InvalidOperationException("Python 环境自检失败。");
                Console.WriteLine("PASS: Python 3.10+, Tkinter, SQLite, launch.pyw import");
                Console.WriteLine("PASS: Windows argument roundtrip (empty, Chinese, spaces, quotes, backslashes)");
                Console.WriteLine("Python: " + python);
                Console.WriteLine("Project: " + root);
                return 0;
            }
            return RunPython(python, root, new[] { launch }.Concat(arguments).ToArray());
        }
        catch (Exception error)
        {
            if (selfTest) Console.Error.WriteLine(error.Message);
            else MessageBox.Show(error.Message, "灵感屿 · 启动失败", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }
}
