using System.Reflection;
using System.Security.Cryptography;
using System.Text.Json;
using DocumentFormat.OpenXml;
using DocumentFormat.OpenXml.Packaging;
using DocumentFormat.OpenXml.Validation;

if (args.Length < 2)
{
    Console.Error.WriteLine("Usage: OpenXmlValidator <output-json> <docx> [docx...]");
    return 2;
}

var outputPath = Path.GetFullPath(args[0]);
var targetName = Environment.GetEnvironmentVariable("OPENXML_TARGET") ?? "Office2013";
var sourceCommit = Environment.GetEnvironmentVariable("QA_SOURCE_COMMIT") ?? "";
var generatedAt = Environment.GetEnvironmentVariable("QA_GENERATED_AT") ?? "";
if (!Enum.TryParse<FileFormatVersions>(targetName, false, out var targetVersion) ||
    !System.Text.RegularExpressions.Regex.IsMatch(sourceCommit, "^[a-f0-9]{40}$") ||
    !DateTimeOffset.TryParse(generatedAt, out _))
{
    Console.Error.WriteLine("OPENXML_TARGET, QA_SOURCE_COMMIT, or QA_GENERATED_AT is invalid.");
    return 2;
}

var validator = new OpenXmlValidator(targetVersion);
var executablePath = Environment.ProcessPath;
if (string.IsNullOrWhiteSpace(executablePath) || !File.Exists(executablePath))
{
    Console.Error.WriteLine("The validator executable identity is unavailable.");
    return 2;
}
var validatorExecutableSha256 = Convert.ToHexString(
    SHA256.HashData(await File.ReadAllBytesAsync(executablePath))
).ToLowerInvariant();
var results = new List<object>();
foreach (var input in args.Skip(1))
{
    var fullPath = Path.GetFullPath(input);
    try
    {
        // Read once, hash those exact bytes, and validate the same immutable
        // in-memory snapshot. This prevents a report from being replayed for a
        // stale or substituted DOCX with the same filename.
        var documentBytes = await File.ReadAllBytesAsync(fullPath);
        var documentSha256 = Convert.ToHexString(
            SHA256.HashData(documentBytes)
        ).ToLowerInvariant();
        using var stream = new MemoryStream(documentBytes, writable: false);
        using var document = WordprocessingDocument.Open(stream, false);
        var errors = validator.Validate(document).Select(error => new
        {
            id = error.Id,
            type = error.ErrorType.ToString(),
            description = error.Description,
            part = error.Part?.Uri.ToString(),
            path = error.Path?.XPath,
        }).ToArray();
        results.Add(new { file = Path.GetFileName(fullPath), sha256 = documentSha256, sizeBytes = documentBytes.LongLength, opened = true, valid = errors.Length == 0, errorCount = errors.Length, errors });
    }
    catch (Exception exception)
    {
        results.Add(new
        {
            file = Path.GetFileName(fullPath),
            sha256 = (string?)null,
            sizeBytes = (long?)null,
            opened = false,
            valid = false,
            errorCount = 1,
            errors = new[] { new { id = "OPEN_EXCEPTION", type = exception.GetType().Name, description = exception.Message, part = (string?)null, path = (string?)null } },
        });
    }
}

var payload = new
{
    tool = "DocumentFormat.OpenXml.OpenXmlValidator",
    sdkVersion = typeof(OpenXmlValidator).Assembly.GetName().Version?.ToString(),
    packageVersion = typeof(WordprocessingDocument).Assembly.GetCustomAttribute<AssemblyInformationalVersionAttribute>()?.InformationalVersion,
    validatorExecutableSha256,
    targetFileFormat = targetVersion.ToString(),
    sourceCommit,
    generatedAt,
    results,
};
Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
await File.WriteAllTextAsync(outputPath, JsonSerializer.Serialize(payload, new JsonSerializerOptions { WriteIndented = true }) + Environment.NewLine);
Console.WriteLine(outputPath);
return results.All(result => (bool)(result.GetType().GetProperty("valid")?.GetValue(result) ?? false)) ? 0 : 1;
