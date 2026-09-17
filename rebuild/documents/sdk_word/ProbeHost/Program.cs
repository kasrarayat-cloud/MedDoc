// Synthetic boundary probe. This executable is never a production document route.
using System.ComponentModel;
using System.Diagnostics;
using System.Net.Sockets;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Text.Json;
using Aspose.Words;
using Aspose.Words.Markup;
using QuillMD.WordAdapter;

if (args.Length != 2) throw new ArgumentException("workspace and outside-canary required");
var workspace = Path.GetFullPath(args[0]);
var canary = Path.GetFullPath(args[1]);
var checks = new Dictionary<string, object>();
// This thread exists before the managed filter. Native Landlock must already
// cover it, and the managed exec filter must synchronize to it with TSYNC.
using var ready = new ManualResetEventSlim(false);
using var go = new ManualResetEventSlim(false);
var before = new Thread(() => {
    ready.Set(); go.Wait();
    lock (checks) {
        checks["existing_thread_canary_denied"] = ReadDenied(canary);
        checks["existing_thread_exec_denied"] = ExecDenied();
    }
});
before.Start(); ready.Wait();
new SdkSeccompGate().LockBeforeDocumentRead(workspace);
checks["main_canary_denied"] = ReadDenied(canary);
checks["main_exec_denied"] = ExecDenied();
try { using var socket = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp); checks["socket_denied"] = false; }
catch (SocketException) { checks["socket_denied"] = true; }
try { using var process = Process.Start("/usr/bin/true"); process?.WaitForExit(); checks["process_denied"] = false; }
catch (Win32Exception) { checks["process_denied"] = true; }
go.Set(); before.Join();
var after = new Thread(() => {
    lock (checks) {
        checks["new_thread_canary_denied"] = ReadDenied(canary);
        checks["new_thread_exec_denied"] = ExecDenied();
    }
});
after.Start(); after.Join();
var input = Path.Combine(workspace, "input.docx");
if (Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(input))).ToLowerInvariant()
    != "c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b")
    throw new ArgumentException("Only accepted blank allowed for this probe.");
var document = new Document(input);
var controls = document.GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().ToArray();
foreach (var control in controls) { control.ListItems.SelectedValue = control.ListItems[1]; control.IsShowingPlaceholderText = false; }
var result = Path.Combine(workspace, "output.docx");
using (var output = new FileStream(result, FileMode.CreateNew, FileAccess.Write)) document.Save(output, SaveFormat.Docx);
checks["sdk_28_control_roundtrip"] = new Document(result).GetChildNodes(NodeType.StructuredDocumentTag, true).Count == 28;
checks["all_checks_pass"] = checks.Values.All(x => x is true);
checks["process_metrics"] = File.ReadAllLines("/proc/self/status").Where(line => line.StartsWith("VmPeak:") || line.StartsWith("VmRSS:") || line.StartsWith("VmSize:") || line.StartsWith("Threads:")).ToArray();
Console.WriteLine(JsonSerializer.Serialize(checks));
return checks["all_checks_pass"] is true ? 0 : 1;

static bool ReadDenied(string path) {
    try { using var file = File.OpenRead(path); return false; }
    catch (UnauthorizedAccessException) { return true; }
    // ENOENT is not proof of isolation; a canary must exist and be readable to
    // the launcher before its profile is applied.
}
static bool ExecDenied() {
    Native.Execve("/quillmd-nonexistent-exec-probe", IntPtr.Zero, IntPtr.Zero);
    return Marshal.GetLastPInvokeError() == 1; // EPERM, not ENOENT/EACCES.
}
static class Native {
    [DllImport("libc", EntryPoint = "execve", SetLastError = true)]
    internal static extern int Execve(string filename, IntPtr argv, IntPtr envp);
}
