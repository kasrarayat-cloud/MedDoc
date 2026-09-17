// PRIVATE SYNTHETIC QUALIFICATION ONLY. This is not an application export adapter.
// Uses the established Aspose.Words FOSS document model; no ZIP/XML mutation.
using System.Security.Cryptography;
using System.Text.Json;
using Aspose.Words;
using Aspose.Words.Markup;
using Aspose.Words.Tables;

const string OriginalSha = "c1852a492221cfa0d144c9c0a60b700a7363a2cca7630aa988ee8b6329e1868b";
if (args.Length != 2) throw new ArgumentException("Expected accepted blank template and private output directory.");
var source = Path.GetFullPath(args[0]);
var output = Path.GetFullPath(args[1]);
if (Convert.ToHexString(SHA256.HashData(File.ReadAllBytes(source))).ToLowerInvariant() != OriginalSha)
    throw new ArgumentException("Only the accepted blank WM IOV qualification fixture is permitted.");
if (!output.Contains("/.runtime/", StringComparison.Ordinal) || !Directory.Exists(output))
    throw new ArgumentException("Output must be an existing private runtime directory.");

var doc = new Document(source);
var controls = doc.GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().ToArray();
if (controls.Length != 28) throw new InvalidDataException("Unexpected control count.");
var selected = controls.Select((s, i) => {
    if (s.SdtType != SdtType.DropDownList) throw new InvalidDataException("Unexpected control type.");
    var option = s.ListItems.Cast<SdtListItem>().Where(x => x.Value != "Choose an item.")
        .OrderByDescending(x => x.DisplayText.Length).First();
    s.ListItems.SelectedValue = option;
    s.IsShowingPlaceholderText = false;
    return new { id = s.Id.ToString(), index = i, value = option.Value, display = option.DisplayText };
}).ToArray();
SaveNew(doc, "dropdowns.docx");
var reopened = new Document(Path.Combine(output, "dropdowns.docx"));
var again = reopened.GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().ToArray();
if (again.Length != 28 || !again.Zip(selected).All(pair => pair.First.Id.ToString() == pair.Second.id
        && pair.First.ListItems.SelectedValue?.Value == pair.Second.value))
    throw new InvalidDataException("SDK dropdown round trip failed.");

// Additional existing blanks are exercised with explicit synthetic values.
// These are demonstrations of SDK operations, never AI-inferred clinical data.
var complete = new Document(Path.Combine(output, "dropdowns.docx"));
var demographics = new Dictionary<string, string> {
    ["DATE OF SERVICE:"] = "2026-09-17 (SYNTHETIC)",
    ["PATIENT ID:"] = "SYNTHETIC-WM-001",
    ["PATIENT NAME:"] = "SYNTHETIC QUALIFICATION PATIENT",
    ["DATE OF BIRTH:"] = "1980-01-01 (SYNTHETIC)"
};
foreach (var item in demographics) {
    var p = complete.GetChildNodes(NodeType.Paragraph, true).Cast<Paragraph>()
        .Single(p => p.GetText().TrimEnd('\r', '\a') == item.Key);
    AppendInStyle(p, " " + item.Value);
}
var table = (Table)complete.GetChild(NodeType.Table, 0, true);
if (table.Rows.Count != 28) throw new InvalidDataException("Unexpected measurement table.");
var measurements = new List<object>();
var locations = new List<object>();
for (var row = 0; row < table.Rows.Count; row++) {
    if (row == 0 || row == 14) continue;
    for (var col = 1; col <= 2; col++) {
        var cell = table.Rows[row].Cells[col];
        if (cell.GetText().Trim('\r', '\a').Length != 0) throw new InvalidDataException("Expected empty cell.");
        var value = col == 1 ? (row + 1).ToString() + ".25" : (500 + row).ToString();
        AppendInStyle(cell.FirstParagraph, value, table.Rows[row].Cells[0].FirstParagraph);
        measurements.Add(new { row, column = col, value });
    }
    var location = table.Rows[row].Cells[0];
    if (location.GetText().Contains("<<insert location>>")) {
        var value = "SYNTHETIC location " + row;
        location.Range.Replace("<<insert location>>", value);
        locations.Add(new { row, column = 0, value });
    }
}
complete.Range.Replace("<<insert date and time>>", "2026-09-17T12:00:00Z (SYNTHETIC)");
// Filled locations can lengthen the measurement table. Keep the existing
// signature label with its following signer line instead of orphaning it.
var signature = complete.GetChildNodes(NodeType.Paragraph, true).Cast<Paragraph>()
    .Single(p => p.GetText().StartsWith("Electronically Signed On ", StringComparison.Ordinal));
signature.ParagraphFormat.KeepWithNext = true;
SaveNew(complete, "all-blanks.docx");

var longDoc = new Document(Path.Combine(output, "all-blanks.docx"));
var longText = "SYNTHETIC REVIEW NOTE: " + string.Concat(Enumerable.Repeat(
    "Measured observation documented in synthetic notes; retain every word. ", 280))
    + "END OF SYNTHETIC LONG ANSWER";
var review = longDoc.GetChildNodes(NodeType.Paragraph, true).Cast<Paragraph>()
    .Single(p => p.GetText().Contains("Clinical correlation with the above findings is required."));
var answer = new Paragraph(longDoc);
var run = new Run(longDoc, longText);
run.Font.Name = "Times New Roman";
run.Font.Size = 10;
answer.AppendChild(run);
review.ParentNode.InsertBefore(answer, review);
SaveNew(longDoc, "long-answer.docx");
if (!new Document(Path.Combine(output, "long-answer.docx")).GetText().Contains(longText))
    throw new InvalidDataException("Long answer did not survive SDK round trip.");

var report = new { sdk = "Aspose.Words.FOSS", version = "26.3.0", source_sha256 = OriginalSha,
    qualification_only = true, clinically_validated = false, selected, demographics, measurements, locations,
    signature_marker_filled = true, original_signer_not_reassigned = true,
    long_answer = longText, long_answer_characters = longText.Length,
    warning = "Longest choices intentionally conflict with prewritten template assertions. Never export as a clinical record." };
File.WriteAllText(Path.Combine(output, "sdk-evidence.json"), JsonSerializer.Serialize(report, new JsonSerializerOptions { WriteIndented = true }));
Console.WriteLine(JsonSerializer.Serialize(new { controls = 28, measurements = measurements.Count,
    locations = locations.Count, demographic_fields = demographics.Count, long_answer_chars = longText.Length }));

void SaveNew(Document value, string name) {
    var path = Path.Combine(output, name);
    using var stream = new FileStream(path, FileMode.CreateNew, FileAccess.Write);
    value.Save(stream, SaveFormat.Docx);
}

void AppendInStyle(Paragraph paragraph, string value, Paragraph? fallback = null) {
    // Inherit the existing answer run's formatting instead of the SDK's default font.
    var prototype = paragraph.Runs.Cast<Run>().LastOrDefault()
        ?? fallback?.Runs.Cast<Run>().LastOrDefault();
    var added = prototype is null ? new Run(paragraph.Document) : (Run)prototype.Clone(true);
    added.Text = value;
    paragraph.AppendChild(added);
}
