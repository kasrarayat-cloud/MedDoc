using System.Text.RegularExpressions;
using Aspose.Words;
using Aspose.Words.Markup;

namespace QuillMD.WordAdapter;

public static partial class WmAdapter
{
    private static string DefaultVariant(int paragraph) => paragraph switch {
        9 => "exam_choice", 11 or 45 or 46 => "trusted", 19 => "technique_only",
        30 or 31 or 34 or 35 => "selected", 32 or 36 => "negative", _ => "original"
    };

    private static ClaimVariant[] VariantDefinitions(int paragraph, string original, string[] controls)
    {
        var template = original;
        foreach (var key in controls) {
            var index = template.IndexOf("Choose an item.", StringComparison.Ordinal);
            if (index < 0) Fail("unsupported_structure", "Expected original control placeholder.");
            template = template[..index] + "{" + key + "}" + template[(index + "Choose an item.".Length)..];
        }
        ClaimVariant Variant(string id, string label, string text, string[]? required = null, string[]? empty = null)
            => new(id, label, text, required ?? controls, empty ?? []);
        var side = paragraph is 23 or 30 or 31 or 32 ? "right" : "left";
        var title = char.ToUpperInvariant(side[0]) + side[1..];
        if (paragraph is 23 or 27) template = template.Replace("treatment {" + controls[3] + "}", "treatment{" + side + "_treatment_connector}{" + controls[3] + "}", StringComparison.Ordinal);
        return paragraph switch {
            9 => [Variant("original", "Documented full study", original, []),
                  Variant("exam_choice", "Use the documented exam selection", "TYPE OF EXAM: {sdt_1475334564}", ["sdt_1475334564"])],
            11 => [Variant("trusted", "Actual authenticated interpreting clinician", "INTERPRETING PHYSICIAN: {signer_name}", [])],
            19 => [Variant("original", "Original technique including reflux over 500 ms", template),
                   Variant("technique_only", "Documented technique without assuming a positive reflux finding", template[..template.IndexOf(" This study documents reflux", StringComparison.Ordinal)].TrimEnd()),
                   Variant("not_documented", "Technique details explicitly not documented", "Technique details were not documented.", [], controls)],
            23 or 27 => [Variant("original", $"Documented {side} prior treatment", template),
                         Variant("none", $"Documented no {side} prior treatment", $"       No previous treatment in the {side} lower extremity.", [], controls),
                         Variant("not_documented", $"{title} prior-treatment history explicitly not documented", $"       Previous treatment history was not documented for the {side} lower extremity.", [], controls)],
            30 or 34 => [Variant("selected", $"Documented {side} vein and finding", $"{title} {{{controls[0]}}}{{{side}_reflux_connector}}{{{controls[1]}}}"),
                         Variant("not_documented", $"{title} saphenous-vein findings explicitly not documented", $"{title} saphenous-vein findings were not documented.", [], controls),
                         Variant("not_assessed", $"{title} saphenous veins explicitly not assessed", $"{title} saphenous veins were not assessed.", [], controls)],
            31 or 35 => [Variant("selected", $"Documented {side} deep-system finding", template),
                         Variant("not_documented", $"{title} deep-system findings explicitly not documented", $"{title} deep venous system findings were not documented.", [], controls),
                         Variant("not_assessed", $"{title} deep venous system explicitly not assessed", $"{title} deep venous system was not assessed.", [], controls)],
            32 or 36 => [Variant("negative", $"Documented no {side} saphenous reflux", original, []),
                         Variant("positive", $"Documented positive {side} saphenous reflux", $"Saphenous reflux is present in the {side} lower extremity.", []),
                         Variant("not_documented", $"{title} saphenous reflux explicitly not documented", $"Saphenous reflux status was not documented in the {side} lower extremity.", []),
                         Variant("not_assessed", $"{title} saphenous reflux explicitly not assessed", $"Saphenous reflux was not assessed in the {side} lower extremity.", [])],
            45 => [Variant("trusted", "Actual finalization time", original, [])],
            46 => [Variant("trusted", "Actual authenticated signer", "{signer_name}", [])],
            _ => [Variant("original", "Documented original statement", template)]
        };
    }

    private static (ReviewRequirement[], string[]) ApplyVariants(Document document, Mapping mapping,
        Dictionary<string, Answer> answers, Dictionary<string, string> selected, TrustedClinicalContext trusted)
    {
        var paragraphs = BodyParagraphs(document);
        var result = new List<ReviewRequirement>(); var conflicts = new List<string>();
        var controls = Controls(document).ToDictionary(s => "sdt_" + s.Id);
        foreach (var original in mapping.ReviewRequirements) {
            var id = selected.GetValueOrDefault(original.Key, original.DefaultVariant);
            // Recommendations may reflect an explicit selected finding. They
            // remain visible, source-bound choices, and fill requires all IDs.
            if (!selected.ContainsKey(original.Key) && original.BodyParagraph is 32 or 36) {
                var finding = answers[original.BodyParagraph == 32 ? "sdt_-213273323" : "sdt_605543147"].Text;
                if (finding == "reflux positive.") id = "positive";
            }
            var variant = original.Variants.SingleOrDefault(v => v.Id == id);
            if (variant is null) Fail("invalid_variant", "Statement variant is not in this immutable mapping.");
            if (variant.RequiredControlKeys.Any(key => answers[key].Status == "missing"))
                conflicts.Add(original.Key + ": selected statement needs a documented answer for every required control.");
            if (variant.EmptyControlKeys.Any(key => answers[key].Status != "missing"))
                conflicts.Add(original.Key + ": selected statement cannot omit an answered control.");
            var template = variant.TextTemplate.Replace("{signer_name}", trusted.SignerName, StringComparison.Ordinal);
            foreach (var side in new[] { "right", "left" }) {
                var findingKey = side == "right" ? "sdt_-213273323" : "sdt_605543147";
                var connector = answers[findingKey].Text == "is absent." ? " " : " is ";
                template = template.Replace("{" + side + "_reflux_connector}", connector, StringComparison.Ordinal);
                var outcome = answers[side == "right" ? "sdt_1706206184" : "sdt_-1268837810"].Text;
                template = template.Replace("{" + side + "_treatment_connector}", outcome.StartsWith(",", StringComparison.Ordinal) ? "" : " ", StringComparison.Ordinal);
            }
            // Controls physically inside this paragraph stay in place. External
            // controls (exam selection) are referenced only as literal values.
            foreach (var answer in answers.Where(x => !original.ControlKeys.Contains(x.Key)))
                template = template.Replace("{" + answer.Key + "}", answer.Value.Text, StringComparison.Ordinal);
            RewriteLiteralSegments(paragraphs[original.BodyParagraph], original.ControlKeys, template, controls);
            var text = paragraphs[original.BodyParagraph].GetText().TrimEnd('\r', '\a', '\f');
            if (text.Contains('{') || text.Contains('}')) Fail("invalid_variant", "Unresolved statement template token.");
            result.Add(original with { Text = text, TextSha256 = TextDigest(text), SelectedVariant = id,
                Changed = text != original.Text, OriginalText = original.Text, OriginalTextSha256 = original.TextSha256 });
        }
        // A positive selected vein cannot coexist with a negative/unknown global
        // statement. Absent ONE selected vein does not prove all veins normal:
        // any global negative still requires its own exact source evidence.
        foreach (var (paragraph, findingKey) in new[] { (32, "sdt_-213273323"), (36, "sdt_605543147") }) {
            var chosen = result.Single(r => r.BodyParagraph == paragraph).SelectedVariant;
            if (answers[findingKey].Text == "reflux positive." && chosen != "positive")
                conflicts.Add("claim_" + paragraph + ": positive selected reflux requires the reviewed positive statement.");
        }
        var rightTreatment = result.Single(r => r.BodyParagraph == 23).SelectedVariant;
        var leftTreatment = result.Single(r => r.BodyParagraph == 27).SelectedVariant;
        if (rightTreatment == "none" && leftTreatment == "none" && answers["sdt_-770853925"].Text == "Previous vein treatment")
            conflicts.Add("Clinical indication reports previous treatment while both reviewed leg statements deny it.");
        foreach (var (claim, vein, outcome, impression, finding) in new[] {
            ("claim_23", "sdt_-1287346867", "sdt_1706206184", "sdt_-892962961", "sdt_-213273323"),
            ("claim_27", "sdt_1093284141", "sdt_-1268837810", "sdt_2001841928", "sdt_605543147") }) {
            if (result.Single(r => r.Key == claim).SelectedVariant == "original"
                && answers[vein].Text == answers[impression].Text && answers[outcome].Text == "and is absent."
                && answers[finding].Text == "reflux positive.")
                conflicts.Add(claim + ": the same documented vein cannot be absent and reflux-positive.");
        }
        foreach (var (impression, reflux, firstRow, lastRow) in new[] { (30, 32, 1, 13), (34, 36, 15, 27) }) {
            var impressionVariant = result.Single(r => r.BodyParagraph == impression).SelectedVariant;
            var refluxVariant = result.Single(r => r.BodyParagraph == reflux).SelectedVariant;
            var sideFields = mapping.Fields.Where(f => f.Locator.TryGetValue("row", out var row)
                && (int)row >= firstRow && (int)row <= lastRow).ToArray();
            if (impressionVariant == "not_assessed" && sideFields.Any(f => answers[f.Key].Status != "missing"))
                conflicts.Add("claim_" + impression + ": a non-assessed side cannot contain documented measurements or locations.");
            var refluxMeasurements = sideFields.Where(f => f.Kind == "measurement" && (string)f.Locator["unit"] == "ms"
                && answers[f.Key].Status != "missing").ToArray();
            if (refluxVariant == "not_assessed" && refluxMeasurements.Length > 0)
                conflicts.Add("claim_" + reflux + ": reflux measurements contradict a non-assessed reflux statement.");
            if (refluxVariant == "negative" && refluxMeasurements.Any(f => decimal.Parse(MeasurementValue(f, answers[f.Key].Text), System.Globalization.CultureInfo.InvariantCulture) > 500))
                conflicts.Add("claim_" + reflux + ": a recorded reflux duration exceeds this template's explicit 500 ms positive criterion.");
        }
        RewriteSymptomSeparators(paragraphs[15], controls);
        return (result.ToArray(), conflicts.ToArray());
    }

    private static void ClearControlDisplay(StructuredDocumentTag control)
    {
        // Keep the actual content-control container, ID, option list, run
        // formatting and paragraph. Only its displayed placeholder is cleared.
        foreach (var run in control.GetChildNodes(NodeType.Run, true).Cast<Run>()) run.Text = "";
        control.IsShowingPlaceholderText = false;
    }

    private static void RewriteLiteralSegments(Paragraph paragraph, string[] keys, string template,
        Dictionary<string, StructuredDocumentTag> controls)
    {
        var kept = keys.Where(key => template.Contains("{" + key + "}", StringComparison.Ordinal)).ToArray();
        if (kept.Length != 0 && !kept.SequenceEqual(keys)) Fail("invalid_variant", "A statement cannot reorder or partially remove its controls.");
        var segments = new List<string>();
        if (kept.Length == 0) {
            segments.Add(template);
            segments.AddRange(keys.Select(_ => ""));
            foreach (var key in keys) ClearControlDisplay(controls[key]);
        } else {
            var remainder = template;
            foreach (var key in keys) {
                var token = "{" + key + "}"; var index = remainder.IndexOf(token, StringComparison.Ordinal);
                if (index < 0) Fail("invalid_variant", "Missing statement control token.");
                segments.Add(remainder[..index]); remainder = remainder[(index + token.Length)..];
            }
            segments.Add(remainder);
        }
        var buckets = new List<List<Run>> { new() };
        foreach (Node child in paragraph.GetChildNodes(NodeType.Any, false)) {
            if (child is StructuredDocumentTag) buckets.Add(new List<Run>());
            else if (child is Run run) buckets[^1].Add(run);
        }
        if (buckets.Count != segments.Count) Fail("unsupported_structure", "Unexpected literal/control sequence.");
        for (var index = 0; index < buckets.Count; index++) {
            var runs = buckets[index];
            if (runs.Count == 0) {
                if (segments[index].Length == 0) continue;
                // Existing variants only target literals already present in the
                // accepted blank. Refuse rather than invent new run placement.
                Fail("unsupported_structure", "Required original literal run is absent.");
            }
            var original = string.Concat(runs.Select(run => run.Text.Replace("\f", "", StringComparison.Ordinal)));
            if (original == segments[index]) continue; // Preserve every unchanged styled run.
            var remaining = segments[index]; var changed = false;
            for (var r = 0; r < runs.Count; r++) {
                var visible = runs[r].Text.Replace("\f", "", StringComparison.Ordinal);
                var pageBreaks = new string(runs[r].Text.Where(c => c == '\f').ToArray());
                // Preserve a stable styled prefix (question label or indent),
                // then inherit the original value run's formatting for changes.
                if (!changed && remaining.StartsWith(visible, StringComparison.Ordinal) && r < runs.Count - 1) {
                    remaining = remaining[visible.Length..];
                    continue;
                }
                runs[r].Text = (changed ? "" : remaining) + pageBreaks;
                changed = true;
            }
        }
    }

    private static void RewriteSymptomSeparators(Paragraph paragraph, Dictionary<string, StructuredDocumentTag> controls)
    {
        var tags = paragraph.GetChildNodes(NodeType.StructuredDocumentTag, true).Cast<StructuredDocumentTag>().ToArray();
        if (tags.Length != 6) Fail("unsupported_structure", "Unexpected clinical indication controls.");
        var keys = tags.Select(tag => "sdt_" + tag.Id).ToArray();
        var text = "CLINICAL INDICATIONS: "; var previous = false;
        foreach (var key in keys) {
            var populated = !string.IsNullOrWhiteSpace(controls[key].GetText().TrimEnd('\r', '\a'));
            if (populated && previous) text += ", ";
            text += "{" + key + "}";
            previous |= populated;
        }
        RewriteLiteralSegments(paragraph, keys, text, controls);
    }
}
