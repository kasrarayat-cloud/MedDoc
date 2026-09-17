using System.Runtime.InteropServices;

namespace QuillMD.WordAdapter;

/// <summary>Mandatory second filter synchronized across every existing CLR thread.</summary>
public sealed class SdkSeccompGate : IDocumentSandbox
{
    private static readonly object Sync = new();
    private static bool locked;
    private static string? boundWorkspace;

    public void LockBeforeDocumentRead(string workspace)
    {
        lock (Sync)
        {
            if (!OperatingSystem.IsLinux() || RuntimeInformation.ProcessArchitecture != Architecture.X64)
                throw new InvalidOperationException("Unqualified document sandbox platform.");
            var root = Path.GetFullPath(workspace);
            if (root != Directory.GetCurrentDirectory() || !Directory.Exists(root))
                throw new InvalidOperationException("Document workspace must equal the launcher workspace.");
            if (locked)
            {
                if (boundWorkspace != root) throw new InvalidOperationException("Sandbox workspace cannot change.");
                return;
            }
            // These are direct kernel controls, not a caller-set environment flag.
            var status = File.ReadAllLines("/proc/self/status").Select(line => line.Split(':', 2))
                .Where(parts => parts.Length == 2).ToDictionary(parts => parts[0], parts => parts[1].Trim());
            if (status.GetValueOrDefault("NoNewPrivs") != "1" || status.GetValueOrDefault("Seccomp") != "2")
                throw new InvalidOperationException("Native pre-exec boundary is required.");
            bool outsideDenied = false;
            try { using var stream = File.OpenRead("/etc/passwd"); }
            catch (UnauthorizedAccessException) { outsideDenied = true; }
            if (!outsideDenied) throw new InvalidOperationException("Native filesystem boundary did not deny outside access.");
            var socket = NativeSocket(2, 1, 0);
            var socketError = Marshal.GetLastPInvokeError();
            if (socket >= 0) { Close(socket); throw new InvalidOperationException("Native network boundary absent."); }
            if (socketError != 1) throw new InvalidOperationException("Native network denial is inconclusive.");

            var context = SeccompInit(0x7fff0000);
            if (context == IntPtr.Zero) throw new InvalidOperationException("Second document filter unavailable.");
            try
            {
                // SCMP_FLTATR_CTL_TSYNC=4: never accept a filter protecting only
                // the calling thread while pre-existing CLR threads stay open.
                if (SeccompAttribute(context, 4, 1) != 0)
                    throw new InvalidOperationException("Thread-synchronized filtering unavailable.");
                foreach (var name in new[] { "execve", "execveat" })
                {
                    var number = Resolve(name);
                    if (number < 0 || AddRule(context, 0x00050001, number, 0) != 0)
                        throw new InvalidOperationException("Document exec-denial rule unavailable.");
                }
                if (Load(context) != 0) throw new InvalidOperationException("Thread-synchronized filter failed.");
                boundWorkspace = root;
                locked = true;
            }
            finally { Release(context); }
        }
    }

    [DllImport("libc", EntryPoint = "socket", SetLastError = true)]
    private static extern int NativeSocket(int domain, int type, int protocol);
    [DllImport("libc", EntryPoint = "close")]
    private static extern int Close(int descriptor);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_init")]
    private static extern IntPtr SeccompInit(uint action);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_attr_set")]
    private static extern int SeccompAttribute(IntPtr context, uint attribute, uint value);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_syscall_resolve_name")]
    private static extern int Resolve([MarshalAs(UnmanagedType.LPUTF8Str)] string name);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_rule_add")]
    private static extern int AddRule(IntPtr context, uint action, int syscall, uint argumentCount);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_load")]
    private static extern int Load(IntPtr context);
    [DllImport("libseccomp.so.2", EntryPoint = "seccomp_release")]
    private static extern void Release(IntPtr context);
}
