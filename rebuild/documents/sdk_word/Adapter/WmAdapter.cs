using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
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
// `Kind`: null for a labelled line (the original contract), "unit" for one sentence of the notes and "answers" for a
// statement wording that rests on its own answers (the narrative contract, docs/rebuild/wm-narrative-design.md).
public sealed record Evidence(string Quote, int Start, int End, string? Kind = null, string[]? AnswerKeys = null);
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
                if (decision.Evidence is not null && decision.Evidence.Any(e => e?.Kind is not null))
                    VerifyNarrativeStatement(requirement, variant, decision.Evidence, answers, trusted.Notes);
                else if (decision.Evidence is null || decision.Evidence.Length == 0
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
        if (answer.Evidence is not null && answer.Evidence.Any(e => e?.Kind is not null)) { VerifyNarrativeAnswer(field, answer, notes); return; }
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
    private static IEnumerable<string> ExplicitLabelValues(string notes, string label) => SplitLines(notes).Select(line => LabelValue(line, label)).Where(value => !string.IsNullOrEmpty(value)).Select(value => value!);
    // The line breaks Python's `str.splitlines` reads, so the parent and the engine see the same labelled lines.
    private static string[] SplitLines(string text) => Regex.Split(text, "\r\n|[\n\r\u000b\u000c\u001c\u001d\u001e\u0085\u2028\u2029]");
    // Text compared after compatibility decomposition, without combining marks, in invariant lower case with the
    // dotless i folded: never stricter than the parent's case-insensitive reading (a ligature, İ/ı, a decomposed é).
    private static string Fold(string text)
    {
        var decomposed = text.Normalize(NormalizationForm.FormKD);
        var kept = new StringBuilder(decomposed.Length);
        foreach (var c in decomposed) {
            var category = CharUnicodeInfo.GetUnicodeCategory(c);
            if (category is UnicodeCategory.NonSpacingMark or UnicodeCategory.SpacingCombiningMark or UnicodeCategory.EnclosingMark) continue;
            kept.Append(c);
        }
        return kept.ToString().ToLowerInvariant().Replace('\u0131', 'i');
    }
    private static bool LabelValuesConsistent(string notes, string label, string expected) => ExplicitLabelValues(notes, label).All(value => Normalize(value) == Normalize(expected));
    // ── the narrative contract's second boundary ──────────────────────────────────────────────────────────────
    // These four patterns are core/wm_narrative.py's, verbatim (a parent test asserts it). Every check below is
    // IMPLIED by the parent's rule, never stricter: the parent reads only unsuperseded places in the sentences it
    // may use and the side of each place; this reads any place in any cited sentence and any side word from the
    // paragraph's start to the sentence's end. So an answer review accepted is never refused here, and an answer
    // with no support at all, or none for its side, never reaches the document.
    private const string QuantityPattern = @"(?<![0-9.,])(?<![0-9][\u2009\u202f])([0-9]+(?:\.[0-9]+)?)[ \t\u00a0]*-?[ \t\u00a0]*(?i:(mm|millimet(?:er|re)s?|ms|msecs?|millisec(?:ond)?s?|s|secs?|seconds?))(?![^\W\d_])";
    private const string BoundedBeforePattern = @"(?i:(?:[<>~\u2248\u2264\u2265\u00b1]=?|\b(?:less|greater|more|fewer|longer|shorter|higher|lower|larger|smaller)\s+than(?:\s+or\s+equal\s+to)?|\b(?:equal\s+to|in\s+excess\s+of|close\s+to|not\s+exceeding|exceeding|under|over|below|above|beyond|about|around|approximately|approx\.?|roughly|nearly|almost|circa|ca\.|estimated|est\.|up\s+to|at\s+(?:least|most)|at\s+or\s+(?:above|below))|\bbetween\s+[0-9][0-9.,]*\s*(?:[^\W\d_]+\s*)?and|[0-9]\s*(?:[^\W\d_]{1,12}\.?\s*)?(?:-|\u2013|\u2014|\bto|\bor)|\bor)\s*)$";
    private const string BoundedAfterPattern = @"(?i:^(?:\s*\+|\s*\?|\s*\(?\s*(?:approx(?:imately)?\.?|estimated|est\.)(?![^\W\d_])|\s*(?:or|and)\s+(?:more|less|greater|higher|lower|longer|shorter|larger|smaller|so|above|below|over|under)(?![^\W\d_])(?=\s*(?:[,.;:)\]]|$|\s(?:in|at|on|for|with|and|but)\b))|\s*(?:-|\u2013|\u2014|to\b|or\b)\s*[0-9]))";
    private const string SidePattern = @"(?<![^\W\d_])((?i:right(?!\s+(?:below|above|at|after|before|behind|under|over|next|near|beside|along|across|around|into|through|up|down|now|away|there|here|about)(?![^\W\d_]))|rt|rle|left|lt|lle|both|bilateral(?:ly)?|bilat|either|ble|b/l|contralateral|ipsilateral|(?:other|opposite)\s+(?:leg|side|limb|extremity))|R\s*(?:and|&|/|\+)\s*L|(?:R|L)(?=\s+(?i:gsv|ssv|aagsv|pagsv|great|small|leg|lower|le|sfj|spj|cfv|fv|pop|thigh|calf|knee|ankle|side|deep|superficial|accessory|anterior|posterior|saphenous|popliteal|femoral|tributary|perforator)(?![^\W\d_])))(?![^\W\d_])";
    // The four shared patterns scope their own case (as the parent compiles them); only the value words ignore it.
    private static readonly RegexOptions Reading = RegexOptions.IgnoreCase | RegexOptions.CultureInvariant;
    private static readonly Regex Quantity = new(QuantityPattern, RegexOptions.CultureInvariant);
    private static readonly Regex BoundedBefore = new(BoundedBeforePattern, RegexOptions.CultureInvariant);
    private static readonly Regex BoundedAfter = new(BoundedAfterPattern, RegexOptions.CultureInvariant);
    private static readonly Regex SideWord = new(SidePattern, RegexOptions.CultureInvariant);
    private static readonly Regex MeasurementForm = new(@"^(?:0|[1-9][0-9]*)(?:\.[0-9]+)? (mm|ms)$");

    private static void VerifyNarrativeAnswer(Field field, Answer answer, string notes)
    {
        var quotes = new List<(string Quote, int Start, int End)>();
        foreach (var evidence in answer.Evidence) {
            if (evidence is null || evidence.Kind is not (null or "unit")) Fail("unsupported_answer", "An answer rests on source sentences only.");
            var slice = Slice(evidence, notes);
            if (slice is null) Fail("unsupported_answer", "Answer evidence no longer matches the source.");
            quotes.Add(slice.Value);
        }
        var written = field.Kind switch {
            "choice" => field.Options.Contains(answer.Text, StringComparer.Ordinal),
            "measurement" => quotes.Any(q => MeasurementWritten(answer.Text, q.Quote)),
            _ => quotes.Any(q => WordsPattern(Fold(answer.Text)).IsMatch(Fold(q.Quote))),
        };
        if (!written || !ExplicitLabelValues(notes, field.Label).All(value => Agrees(field, value, answer.Text)))
            Fail("unsupported_answer", "Answer is not written in its cited source sentences.");
        var side = FieldSide(field.Label);
        if (side is not null && !quotes.Any(q => SideWritten(notes, q.Start, q.End, side)))
            Fail("unsupported_answer", "The cited source sentences do not place this answer on its side.");
    }

    private static void VerifyNarrativeStatement(ReviewRequirement requirement, ClaimVariant variant, Evidence[] evidence,
        Dictionary<string, Answer> answers, string notes)
    {
        var sentences = new List<(string Quote, int Start, int End)>(); var basis = 0;
        // A wording rests on the answers it is built from, or a `not_documented` wording on the answers whose absence
        // it states (the parent also bounds the first kind's connecting text; this is the coarser, implied rule).
        var absence = variant.RequiredControlKeys.Length == 0 && variant.Id == "not_documented";
        var rests = variant.RequiredControlKeys.Length > 0 ? variant.RequiredControlKeys : absence ? variant.EmptyControlKeys : [];
        foreach (var entry in evidence) {
            if (entry is null) Fail("unsupported_assertion", "Invalid statement evidence.");
            if (entry.Kind == "answers") {
                basis++;
                if (basis > 1 || rests.Length == 0 || entry.AnswerKeys is null
                    || !entry.AnswerKeys.SequenceEqual(rests, StringComparer.Ordinal)
                    || (absence && entry.AnswerKeys.Any(key => answers[key].Status != "missing")))
                    Fail("unsupported_assertion", "A statement rests only on the answers its own wording is built from, or whose absence it states.");
            } else if (entry.Kind == "unit") {
                var slice = Slice(entry, notes);
                if (slice is null) Fail("unsupported_assertion", "Statement evidence no longer matches the source.");
                sentences.Add(slice.Value);
            } else if (entry.Kind is not null || !LabelledSupport(entry, notes, requirement.Label, requirement.Text)) {
                Fail("unsupported_assertion", "A statement requires complete, consistent source evidence.");
            }
        }
        if (variant.RequiredControlKeys.Length == 0) {
            if (sentences.Count == 0 && basis == 0 && !evidence.Any(e => e.Kind is null)) Fail("unsupported_assertion", "A fixed statement wording needs a source sentence.");
            var side = FieldSide(requirement.Label.Replace("Prewritten statement: ", "", StringComparison.Ordinal));
            if (side is not null && sentences.Count > 0 && !sentences.Any(q => SideWritten(notes, q.Start, q.End, side)))
                Fail("unsupported_assertion", "The cited source sentences do not name this statement's side.");
        }
    }

    // The cited slice in UTF-16 indices, or null when it is not exactly the notes' text at its code-point offsets.
    private static (string Quote, int Start, int End)? Slice(Evidence evidence, string notes)
    {
        if (evidence.Quote is null || evidence.Start < 0 || evidence.End <= evidence.Start) return null;
        var start = CodePointOffset(notes, evidence.Start); var end = CodePointOffset(notes, evidence.End);
        if (start < 0 || end < 0 || notes[start..end] != evidence.Quote) return null;
        return (evidence.Quote, start, end);
    }

    private static bool MeasurementWritten(string value, string quote)
    {
        var form = MeasurementForm.Match(value);
        if (!form.Success || !decimal.TryParse(value.Split(' ')[0], NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var number)) return false;
        var unit = form.Groups[1].Value;
        foreach (Match found in Quantity.Matches(quote)) {
            if (BoundedBefore.IsMatch(quote[Math.Max(0, found.Index - 40)..found.Index]) || BoundedAfter.IsMatch(quote[(found.Index + found.Length)..])) continue;
            if (!decimal.TryParse(found.Groups[1].Value, NumberStyles.AllowDecimalPoint, CultureInfo.InvariantCulture, out var stated)) continue;
            var word = found.Groups[2].Value.ToLowerInvariant();
            if ((unit == "mm" && (word.StartsWith("mm", StringComparison.Ordinal) || word.StartsWith("millimet", StringComparison.Ordinal)) && stated == number)
                || (unit == "ms" && (word.StartsWith("ms", StringComparison.Ordinal) || word.StartsWith("msec", StringComparison.Ordinal) || word.StartsWith("millisec", StringComparison.Ordinal)) && stated == number)
                || (unit == "ms" && word.StartsWith('s') && stated <= decimal.MaxValue / 1000m && stated * 1000 == number))
                return true;
        }
        return false;
    }

    // A value's words with any whitespace between them, a side word allowed inside the phrase (core/wm_narrative._words).
    private static Regex WordsPattern(string value)
    {
        var words = value.Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries);
        return new Regex(@"(?<![^\W\d_])" + string.Join(@"\s+(?:(?:right|left|rt|lt)\s+)?", words.Select(Regex.Escape)) + @"(?![^\W\d_])", Reading);
    }

    private static bool Agrees(Field field, string labelled, string value) => field.Kind switch {
        "choice" => !field.Options.Contains(labelled, StringComparer.Ordinal) || labelled == value,
        "measurement" => Normalize(labelled) == Normalize(value) || MeasurementWritten(value, labelled),
        _ => Fold(Normalize(labelled)).Contains(Fold(Normalize(value)), StringComparison.Ordinal),
    };

    private static string? FieldSide(string label) => label.StartsWith("Right ", StringComparison.Ordinal) ? "right" : label.StartsWith("Left ", StringComparison.Ordinal) ? "left" : null;

    // Any side word of this side (or both legs) from the start of the notes to the end of the cited sentence: the
    // parent reads the clause, the sentence, the paragraph and the nearest heading, all inside that range.
    private static bool SideWritten(string notes, int start, int end, string side)
    {
        foreach (Match word in SideWord.Matches(notes[..end])) {
            var name = string.Join(" ", word.Groups[1].Value.ToLowerInvariant().Split((char[]?)null, StringSplitOptions.RemoveEmptyEntries));
            var named = name is "right" or "rt" or "rle" or "r" ? "right" : name is "left" or "lt" or "lle" or "l" ? "left"
                : name is "contralateral" or "ipsilateral" || name.StartsWith("other", StringComparison.Ordinal) || name.StartsWith("opposite", StringComparison.Ordinal) ? "unclear" : "both";
            if (named == side || named == "both") return true;
        }
        return false;
    }

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
