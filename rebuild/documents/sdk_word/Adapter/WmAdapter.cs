using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Aspose.Words;
using Aspose.Words.Markup;
using Aspose.Words.Tables;

namespace QuillMD.WordAdapter;

public sealed class WordAdapterException(string code, string message) : Exception(message)
{
    public string Code { get; } = code;
}

// Constructed by the authenticated parent, never by model output or form JSON.
public sealed record TrustedClinicalContext(string ReviewerId, int Revision,
    string Notes, string SignerName, DateTimeOffset FinalizedAt);
public sealed record Evidence(string Quote, int Start, int End);
public sealed record Answer(string Text, string Status, string ReviewedBy, int Revision, Evidence[] Evidence);
public sealed record ReviewDecision(string TextSha256, string ReviewedBy, int Revision, Evidence[] Evidence);
public sealed record Field(string Key, string Label, string Kind, Dictionary<string, object> Locator, string[] Options);
public sealed record ClaimVariant(string Id, string Label, string TextTemplate, string[] RequiredControlKeys, string[] EmptyControlKeys);
public sealed record ReviewRequirement(string Key, string Label, string Kind, int BodyParagraph, string Text, string TextSha256, string[] ControlKeys,
    ClaimVariant[] Variants, string DefaultVariant, string OriginalText, string OriginalTextSha256, string SelectedVariant, bool Changed);
public sealed record Mapping(string Backend, string SourceSha256, Field[] Fields, ReviewRequirement[] ReviewRequirements);

/// <summary>
/// Bounded, fail-closed WM adapter. The mandatory document boundary precedes
/// processing; the authenticated parent supplies current clinical review context.
/// </summary>
public static partial class WmAdapter
{
    public const string OriginalSha256 = "c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b";
    public const string Backend = "wm-iov-foss-v2";
    private static readonly JsonSerializerOptions Json = new() { PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower, MaxDepth = 32 };
    private static readonly string[] ControlLabels = ["Practice address", "Exam side", "Referring physician", "Ultrasound technologist", "Ultrasound machine", "Exam location", "Clinical indication: leg pain", "Clinical indication: swelling", "Clinical indication: heaviness", "Clinical indication: history or skin changes", "Clinical indication: sensory symptoms", "Clinical indication: asymptomatic or itching", "Diagnosis", "Technique: venous systems", "Right previous treatment: vein", "Right previous treatment: start", "Right previous treatment: end", "Right previous treatment: outcome", "Left previous treatment: vein", "Left previous treatment: start", "Left previous treatment: end", "Left previous treatment: outcome", "Right impression: vein", "Right impression: reflux or absence", "Right deep venous system", "Left impression: vein", "Left impression: reflux or absence", "Left deep venous system"];
    private static readonly int[] ClaimParagraphs = [9, 11, 19, 23, 27, 30, 31, 32, 34, 35, 36, 39, 45, 46];
    private static readonly (int Index, string Key, string Label)[] Demographics = [(4, "date_of_service", "Date of service"), (5, "patient_id", "Patient ID"), (6, "patient_name", "Patient name"), (7, "date_of_birth", "Date of birth")];

    // The security gate is invoked before request/document reads and before any
    // untrusted bytes reach Aspose. Production gate failures are never ignored.
    public static string Execute(string workspace, IDocumentSandbox sandbox, TrustedClinicalContext? trusted = null)
    {
        ArgumentNullException.ThrowIfNull(sandbox);
        workspace = Path.GetFullPath(workspace);
        sandbox.LockBeforeDocumentRead(workspace);
        var requestBytes = ReadBounded(Path.Combine(workspace, "request.json"), 2 * 1024 * 1024);
        using var parsed = JsonDocument.Parse(requestBytes, new JsonDocumentOptions { MaxDepth = 32 });
        RejectDuplicateProperties(parsed.RootElement);
        var request = parsed.RootElement;
        if (trusted is null && request.TryGetProperty("trusted_context", out var context)) trusted = context.Deserialize<TrustedClinicalContext>(Json);
        var operation = RequiredString(request, "operation");
        if (operation is not ("inspect" or "resolve" or "fill")) Fail("invalid_operation", "Unsupported Word operation.");
        var bytes = ReadBounded(Path.Combine(workspace, "input.docx"), 10 * 1024 * 1024);
        if (Digest(bytes) != OriginalSha256) Fail("unsupported_original", "This adapter accepts only the qualified WM IOV original.");
        // Reading exactly the hashed bytes avoids a hash/open filename race.
        using var input = new MemoryStream(bytes, writable: false);
        var document = new Document(input);
        var mapping = Inspect(document);
        var mappingDigest = Digest(Encoding.UTF8.GetBytes(JsonSerializer.Serialize(mapping, Json)));
        if (operation == "inspect") return Serialize(new { format = "docx", backend = Backend, source_sha256 = OriginalSha256, mapping_digest = mappingDigest, fields = mapping.Fields, review_requirements = mapping.ReviewRequirements, warnings = Warnings() });
        if (RequiredString(request, "mapping_digest") != mappingDigest) Fail("stale_mapping", "Mapping does not match the qualified original and adapter version.");
        var answersNode = request.GetProperty("answers");
        var answers = answersNode.Deserialize<Dictionary<string, Answer>>(Json) ?? throw new WordAdapterException("invalid_answers", "Answers are required.");
        if (!answers.Keys.ToHashSet(StringComparer.Ordinal).SetEquals(mapping.Fields.Select(f => f.Key))) Fail("invalid_answers", "Provide exactly the90 canonical answer fields.");
        ValidateValues(mapping, answers);
        ApplyAnswers(document, mapping, answers);
        if (trusted is null || string.IsNullOrWhiteSpace(trusted.ReviewerId) || string.IsNullOrWhiteSpace(trusted.SignerName)
            || trusted.SignerName.Length > 500 || trusted.SignerName.Any(char.IsControl))
            Fail("review_required", "Authenticated clinical review context and actual signer name are required.");
        var requestedVariants = request.TryGetProperty("claim_variants", out var variantsNode)
            ? variantsNode.Deserialize<Dictionary<string, string>>(Json) ?? [] : new Dictionary<string, string>();
        if (requestedVariants.Keys.Any(key => !mapping.ReviewRequirements.Any(r => r.Key == key))) Fail("invalid_variant", "Unknown statement variant key.");
        if (operation == "fill" && !requestedVariants.Keys.ToHashSet().SetEquals(mapping.ReviewRequirements.Select(r => r.Key)))
            Fail("review_required", "Every statement variant must be explicitly reviewed before export.");
        var (resolved, variantConflicts) = ApplyVariants(document, mapping, answers, requestedVariants, trusted);
        var conflicts = TemplateConflicts(document).Concat(variantConflicts).ToArray();
        if (operation == "resolve") return Serialize(new { backend = Backend, source_sha256 = OriginalSha256, mapping_digest = mappingDigest, review_requirements = resolved, conflicts, export_ready = false });
        if (trusted is null || string.IsNullOrWhiteSpace(trusted.ReviewerId)) Fail("review_required", "Authenticated clinical finalization context is required.");
        if (conflicts.Length > 0) Fail("template_conflict", "Selected answers and reviewed statement variants conflict.");
        foreach (var field in mapping.Fields) {
            var answer = answers[field.Key];
            if (answer.ReviewedBy != trusted!.ReviewerId || answer.Revision != trusted.Revision) Fail("stale_review", "Every answer must be reviewed for the current source revision.");
            VerifyAnswerEvidence(field, answer, trusted.Notes);
        }
        var decisions = request.GetProperty("reviewed_requirements").Deserialize<Dictionary<string, ReviewDecision>>(Json)
            ?? throw new WordAdapterException("review_required", "Template assertions require clinical review.");
        if (!decisions.Keys.ToHashSet(StringComparer.Ordinal).SetEquals(resolved.Select(r => r.Key))) Fail("review_required", "Review all14 template assertions and identity requirements.");
        var paragraphs = BodyParagraphs(document);
        foreach (var requirement in resolved) {
            var decision = decisions[requirement.Key];
            if (decision.TextSha256 != requirement.TextSha256 || decision.ReviewedBy != trusted.ReviewerId || decision.Revision != trusted.Revision)
                Fail("stale_review", "A template assertion changed or was not reviewed for this source revision.");
            if (requirement.Kind == "assertion") {
                var variant = requirement.Variants.Single(v => v.Id == requirement.SelectedVariant);
                if (variant.RequiredControlKeys.Any(key => answers[key].Status == "missing"))
                    Fail("missing_assertion_answer", "A reviewed statement still depends on an unanswered content control.");
                if (decision.Evidence is null || decision.Evidence.Length == 0
                    || decision.Evidence.Any(e => !LabelledSupport(e, trusted.Notes, requirement.Label, requirement.Text))
                    || !LabelValuesConsistent(trusted.Notes, requirement.Label, requirement.Text))
                    Fail("unsupported_assertion", "A statement requires complete, consistent source evidence under its own exact label and side.");
            } else if (decision.Evidence is null || decision.Evidence.Length != 0) {
                Fail("identity_evidence_forbidden", "Clinician identity and signature metadata must come only from the authenticated parent.");
            }
        }
        document.Range.Replace("<<insert date and time>>", trusted.FinalizedAt.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss'Z'", CultureInfo.InvariantCulture));
        paragraphs[45].ParagraphFormat.KeepWithNext = true;
        var output = Path.Combine(workspace, "output.docx");
        using (var destination = new FileStream(output, FileMode.CreateNew, FileAccess.Write, FileShare.None)) document.Save(destination, SaveFormat.Docx);
        if (new FileInfo(output).Length > 30 * 1024 * 1024) { File.Delete(output); Fail("output_limit", "Word export exceeds the processing limit."); }
        // Original bytes are never rewritten; all output fields/options are
        // independently inspected by the parent qualification/security suite.
        return Serialize(new { format = "docx", backend = Backend, source_sha256 = OriginalSha256, output_sha256 = Digest(File.ReadAllBytes(output)), field_count = mapping.Fields.Length, review_requirement_count = resolved.Length });
    }

    private static Mapping Inspect(Document document)
    {
        var controls = Controls(document);
        if (controls.Length != 28 || controls.Any(s => s.SdtType != SdtType.DropDownList)) Fail("unsupported_structure", "Unexpected WM content controls.");
        var fields = controls.Select((s, i) => new Field("sdt_" + s.Id, ControlLabels[i], "choice",
            new() { ["part"] = "word/document.xml", ["sdt_id"] = s.Id.ToString() },
            s.ListItems.Cast<SdtListItem>().Where(v => v.Value != "Choose an item.").Select(v => v.Value).ToArray())).ToList();
        var paragraphs = BodyParagraphs(document);
        foreach (var (index, key, label) in Demographics)
            fields.Add(new Field(key, label, "text", new() { ["body_paragraph"] = index, ["expected_text_sha256"] = TextDigest(paragraphs[index].GetText().TrimEnd('\r', '\a', '\f')) }, []));
        var table = FirstTable(document);
        if (table.Rows.Count != 28 || table.Rows.Cast<Row>().Any(r => r.Cells.Count != 3)) Fail("unsupported_structure", "Unexpected measurement table.");
        for (var row = 0; row < 28; row++) {
            if (row is 0 or 14) continue;
            var question = table.Rows[row].Cells[0].GetText().TrimEnd('\r', '\a', '\f');
            var side = row < 14 ? "Right" : "Left";
            var measurementLabel = question.Contains("<<insert location>>") ? $"{side} tributary row {row}" : $"{side} {question}";
            for (var col = 1; col <= 2; col++) {
                if (table.Rows[row].Cells[col].GetText().Trim('\r', '\a').Length != 0) Fail("unsupported_structure", "Expected a blank measurement cell.");
                fields.Add(new Field($"measurement_{row}_{col}", $"{measurementLabel}: {(col == 1 ? "diameter (mm)" : "reflux time (ms)")}", "measurement", new() { ["table"] = 0, ["row"] = row, ["column"] = col, ["unit"] = col == 1 ? "mm" : "ms" }, []));
            }
            if (question.Contains("<<insert location>>"))
                fields.Add(new Field($"location_{row}", $"{side} tributary row {row}: anatomical location", "text", new() { ["table"] = 0, ["row"] = row, ["column"] = 0, ["marker"] = "<<insert location>>" }, []));
        }
        if (fields.Count != 90) Fail("unsupported_structure", "Unexpected canonical field count.");
        return new Mapping(Backend, OriginalSha256, fields.ToArray(), Requirements(document));
    }

    private static ReviewRequirement[] Requirements(Document document)
    {
        var paragraphs = BodyParagraphs(document);
        if (paragraphs.Length != 48) Fail("unsupported_structure", "Unexpected body paragraph structure.");
        return ClaimParagraphs.Select(i => {
            var value = paragraphs[i].GetText().TrimEnd('\r', '\a', '\f');
            var keys = paragraphs[i].GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().Select(s => "sdt_" + s.Id).ToArray();
            var labels = new Dictionary<int,string> { [9] = "Exam type", [11] = "Interpreting physician", [19] = "Technique", [23] = "Right previous treatment", [27] = "Left previous treatment", [30] = "Right impression", [31] = "Right deep venous system", [32] = "Right saphenous reflux finding", [34] = "Left impression", [35] = "Left deep venous system", [36] = "Left saphenous reflux finding", [39] = "Clinical correlation", [45] = "Signature timestamp", [46] = "Signer identity" };
            var variants = VariantDefinitions(i, value, keys);
            return new ReviewRequirement("claim_" + i, "Prewritten statement: " + labels[i], i is 11 or 46 ? "identity" : i == 45 ? "signature" : "assertion", i, value, TextDigest(value), keys, variants, DefaultVariant(i), value, TextDigest(value), "", false);
        }).ToArray();
    }

    private static void ValidateValues(Mapping mapping, Dictionary<string, Answer> answers)
    {
        foreach (var field in mapping.Fields) {
            var answer = answers[field.Key];
            if (answer is null || answer.Text is null || answer.Text.Length > 20000
                || answer.Text.Any(c => char.IsControl(c) && c != '\n' && c != '\t'))
                Fail("invalid_answer", "WM answers must be bounded text without invalid control characters.");
            if (answer.Status == "missing" && answer.Text == "") continue;
            if (answer.Status != "supported" || string.IsNullOrWhiteSpace(answer.Text)) Fail("invalid_answer_status", "Empty answers require an explicit missing decision; nonempty answers require supported status.");
            if (field.Kind == "choice" && !field.Options.Contains(answer.Text, StringComparer.Ordinal)) Fail("invalid_choice", "Dropdown value is not an original allowed option.");
            if (field.Kind == "measurement") _ = MeasurementValue(field, answer.Text);
            if (field.Locator.ContainsKey("marker") && answer.Text.Contains("<<", StringComparison.Ordinal)) Fail("invalid_location", "Replace the anatomical location marker explicitly.");
        }
    }

    private static void ApplyAnswers(Document document, Mapping mapping, Dictionary<string, Answer> answers)
    {
        var controls = Controls(document).ToDictionary(s => "sdt_" + s.Id);
        var paragraphs = BodyParagraphs(document);
        var table = FirstTable(document);
        foreach (var field in mapping.Fields) {
            var value = answers[field.Key].Text;
            if (answers[field.Key].Status == "missing") { if (field.Kind == "choice") ClearControlDisplay(controls[field.Key]); continue; }
            if (field.Kind == "choice") {
                var control = controls[field.Key];
                control.ListItems.SelectedValue = control.ListItems.Cast<SdtListItem>().Single(v => v.Value == value);
                control.IsShowingPlaceholderText = false;
            } else if (field.Locator.TryGetValue("body_paragraph", out var paragraph)) {
                var p = paragraphs[(int)paragraph];
                if (TextDigest(p.GetText().TrimEnd('\r', '\a', '\f')) != (string)field.Locator["expected_text_sha256"]) Fail("stale_mapping", "Demographic anchor changed.");
                AppendInStyle(p, " " + value);
            } else {
                var row = (int)field.Locator["row"]; var col = (int)field.Locator["column"];
                var cell = table.Rows[row].Cells[col];
                if (field.Locator.ContainsKey("marker")) cell.Range.Replace("<<insert location>>", value);
                else AppendInStyle(cell.FirstParagraph, MeasurementValue(field, value), table.Rows[row].Cells[0].FirstParagraph);
            }
        }
    }

    private static string[] TemplateConflicts(Document document)
    {
        var controls = Controls(document); var result = new List<string>();
        if (controls[11].GetText().TrimEnd('\r', '\a') == "Asymptomatic" && new[] { 6, 7, 8, 10 }.Any(i => !string.IsNullOrWhiteSpace(controls[i].GetText().TrimEnd('\r', '\a')))) result.Add("Asymptomatic selection conflicts with required symptom selections in other unchanged slots.");
        return result.ToArray();
    }

    private static string MeasurementValue(Field field, string text) {
        var suffix = " " + (string)field.Locator["unit"];
        if (!text.EndsWith(suffix, StringComparison.Ordinal)) Fail("invalid_measurement", "Measurement evidence must include the mapped unit.");
        var value = text[..^suffix.Length];
        if (value.Length > 12 || !decimal.TryParse(value, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var number) || number < 0)
            Fail("invalid_measurement", "Measurement must be an explicit nonnegative decimal in its mapped unit.");
        return value;
    }
    private static void VerifyAnswerEvidence(Field field, Answer answer, string notes)
    {
        if (answer.Status == "missing") {
            if (ExplicitLabelValues(notes, field.Label).Any()) Fail("missing_documented_answer", "A documented field cannot be marked missing.");
            return;
        }
        if (answer.Evidence is null || answer.Evidence.Length == 0
            || answer.Evidence.Any(e => !LabelledSupport(e, notes, field.Label, answer.Text))
            || !LabelValuesConsistent(notes, field.Label, answer.Text))
            Fail("unsupported_answer", "Answer lacks complete consistent source evidence under its own full label.");
    }
    // Full-label matching tolerates case and surrounding whitespace, preserves
    // internal colons/side, and never accepts an arbitrary unlabelled suffix.
    private static bool LabelledSupport(Evidence evidence, string notes, string label, string expected)
    {
        if (evidence is null || evidence.Quote is null || evidence.Start < 0 || evidence.End <= evidence.Start) return false;
        var start = CodePointOffset(notes, evidence.Start); var end = CodePointOffset(notes, evidence.End);
        if (start < 0 || end < 0 || notes[start..end] != evidence.Quote) return false;
        var lineStart = start == 0 ? 0 : notes.LastIndexOf('\n', start - 1) + 1;
        var next = notes.IndexOf('\n', end); var lineEnd = next < 0 ? notes.Length : next;
        var line = notes[lineStart..lineEnd].Trim();
        var value = LabelValue(line, label);
        return value is not null && Normalize(value) == Normalize(expected)
            && (evidence.Quote == line || evidence.Quote == value);
    }
    private static string? LabelValue(string line, string label) {
        line = line.Trim();
        for (var index = 0; index < line.Length; index++) {
            if (line[index] == ':' && line[..index].Trim().TrimEnd(':', '?').Trim().Equals(label.Trim().TrimEnd(':', '?').Trim(), StringComparison.OrdinalIgnoreCase))
                return line[(index + 1)..].Trim();
        }
        return null;
    }
    private static IEnumerable<string> ExplicitLabelValues(string notes, string label) => notes.Split('\n').Select(line => LabelValue(line, label)).Where(value => !string.IsNullOrEmpty(value)).Select(value => value!);
    private static bool LabelValuesConsistent(string notes, string label, string expected) => ExplicitLabelValues(notes, label).All(value => Normalize(value) == Normalize(expected));
    private static int CodePointOffset(string text, int offset) {
        var codePoints = 0; var utf16 = 0;
        foreach (var rune in text.EnumerateRunes()) { if (codePoints++ == offset) return utf16; utf16 += rune.Utf16SequenceLength; }
        return codePoints == offset ? utf16 : -1;
    }
    private static string[] Warnings() => ["This mapping applies to this unchanged original form.", "Review all prewritten findings, changed statements and the actual clinician signer before export.", "Missing information is left blank; it is never replaced with a normal finding.", "Unmapped blank paragraphs are preserved. Export is available in Word format."];
    private static StructuredDocumentTag[] Controls(Document doc) => doc.GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().ToArray();
    private static Paragraph[] BodyParagraphs(Document doc) => doc.GetChildNodes(NodeType.Paragraph, true).Cast<Paragraph>().Where(p => p.ParentNode is Body).ToArray();
    private static Table FirstTable(Document doc) => (Table)doc.GetChild(NodeType.Table, 0, true);
    private static void AppendInStyle(Paragraph p, string value, Paragraph? fallback = null) { var prototype = p.Runs.Cast<Run>().LastOrDefault() ?? fallback?.Runs.Cast<Run>().LastOrDefault(); var run = prototype is null ? new Run(p.Document) : (Run)prototype.Clone(true); run.Text = value; p.AppendChild(run); }
    private static string RequiredString(JsonElement root, string key) { if (!root.TryGetProperty(key, out var value) || value.ValueKind != JsonValueKind.String || string.IsNullOrEmpty(value.GetString())) Fail("invalid_request", "Required request value is missing."); return value.GetString()!; }
    private static byte[] ReadBounded(string path, int limit) { var info = new FileInfo(path); if (info.LinkTarget is not null || info.Length <= 0 || info.Length > limit) Fail("input_limit", "Input must be a bounded regular file."); using var file = File.OpenRead(path); var bytes = new byte[limit + 1]; var count = 0; while (count < bytes.Length) { var read = file.Read(bytes, count, bytes.Length - count); if (read == 0) break; count += read; } if (count > limit) Fail("input_limit", "Input exceeds its limit."); return bytes[..count]; }
    private static void RejectDuplicateProperties(JsonElement element) { if (element.ValueKind == JsonValueKind.Object) { var keys = new HashSet<string>(StringComparer.Ordinal); foreach (var item in element.EnumerateObject()) { if (!keys.Add(item.Name)) Fail("duplicate_property", "Duplicate JSON properties are refused."); RejectDuplicateProperties(item.Value); } } else if (element.ValueKind == JsonValueKind.Array) foreach (var item in element.EnumerateArray()) RejectDuplicateProperties(item); }
    private static string Digest(byte[] value) => Convert.ToHexString(SHA256.HashData(value)).ToLowerInvariant();
    private static string TextDigest(string value) => Digest(Encoding.UTF8.GetBytes(value));
    private static string Normalize(string value) => string.Join(" ", value.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
    private static string Serialize(object value) => JsonSerializer.Serialize(value, Json);
    [System.Diagnostics.CodeAnalysis.DoesNotReturn]
    private static void Fail(string code, string message) => throw new WordAdapterException(code, message);
}
