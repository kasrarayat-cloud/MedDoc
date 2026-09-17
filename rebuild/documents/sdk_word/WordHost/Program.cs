using System.Text.Json;
using QuillMD.WordAdapter;
try {
    if (args.Length != 1) throw new WordAdapterException("invalid_request", "Document workspace required.");
    Console.WriteLine(WmAdapter.Execute(args[0], new SdkSeccompGate()));
    return 0;
} catch (WordAdapterException error) {
    Console.WriteLine(JsonSerializer.Serialize(new { error = error.Message, code = error.Code }));
    return 2;
} catch (Exception) {
    // File paths, SDK internals, source content and secrets never reach callers.
    Console.WriteLine(JsonSerializer.Serialize(new { error = "Word processing or its mandatory isolation boundary failed.", code = "word_processing_failed" }));
    return 2;
}
