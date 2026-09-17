namespace QuillMD.WordAdapter;

/// <summary>Mandatory security boundary supplied by the trusted worker host.</summary>
/// <remarks>
/// Production implementation must synchronize the second seccomp phase across
/// all CLR threads before opening request/document files. Native launcher
/// Landlock and resource/network/process policy must already be inherited.
/// There is no environment-variable, missing-policy, or developer-mode bypass.
/// </remarks>
public interface IDocumentSandbox
{
    void LockBeforeDocumentRead(string workspace);
}
