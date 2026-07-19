[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ExpectedCommit = "__SOURCE_COMMIT__"
$ExpectedManifestSha256 = "__MANIFEST_SHA256__"
$ExpectedOpenXmlValidatorSha256 = "__OPENXML_VALIDATOR_SHA256__"
$ShortSha = "__SHORT_SHA__"
$BundleRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $BundleRoot "manifests\WORD-QA-DOCUMENTS.json"
$RunTimestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$ResultsRoot = Join-Path $BundleRoot ("word-evidence-" + $ShortSha + "-" + $RunTimestamp)
$WorkRoot = Join-Path $ResultsRoot "work-copies"
$ReopenedRoot = Join-Path $ResultsRoot "word-reopened-docx"
$PdfRoot = Join-Path $ResultsRoot "word-exported-pdf"
$PdfBindingRoot = Join-Path $ResultsRoot "pdf-export-binding"
$OpenXmlRoot = Join-Path $ResultsRoot "openxml"
$OpenXmlValidatorPath = Join-Path $BundleRoot "tools\openxml-validator\OpenXmlValidator.exe"
$ReturnZip = Join-Path $BundleRoot ("template-twin-word-evidence-" + $ShortSha + ".zip")
$ReturnSidecar = $ReturnZip + ".sha256"

function Ensure-Directory([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) {
    New-Item -ItemType Directory -Path $Path | Out-Null
  }
}

function Get-Sha256([string]$Path) {
  return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-PortableRelativePath([string]$Path, [string]$Root) {
  return $Path.Substring($Root.Length + 1).Replace("\", "/")
}

function Get-FileEvidence([string]$Path, [string]$Root, [string]$Kind) {
  $item = Get-Item -LiteralPath $Path
  return [ordered]@{
    relativePath = Get-PortableRelativePath $item.FullName $Root
    sizeBytes = [long]$item.Length
    sha256 = Get-Sha256 $item.FullName
    kind = $Kind
  }
}

function Release-ComObject($Object) {
  if ($null -ne $Object) {
    try { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Object) } catch {}
  }
}

function Invoke-OpenXmlValidation([string]$DocumentPath, [string]$OutputPath, [string]$Target) {
  $env:OPENXML_TARGET = $Target
  $env:QA_SOURCE_COMMIT = $ExpectedCommit
  $env:QA_GENERATED_AT = (Get-Date).ToUniversalTime().ToString("o")
  & $OpenXmlValidatorPath $OutputPath $DocumentPath | Out-Host
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $OutputPath -PathType Leaf)) {
    throw "OPENXML_SCHEMA"
  }
  $Report = Get-Content -LiteralPath $OutputPath -Raw | ConvertFrom-Json
  $ReportResults = @($Report.results)
  if ($Report.tool -ne "DocumentFormat.OpenXml.OpenXmlValidator" -or
      $Report.sdkVersion -ne "3.5.1.0" -or
      $Report.validatorExecutableSha256 -ne $ExpectedOpenXmlValidatorSha256 -or
      $Report.targetFileFormat -ne $Target -or
      $Report.sourceCommit -ne $ExpectedCommit -or
      $ReportResults.Count -ne 1 -or
      $ReportResults[0].file -ne (Split-Path -Leaf $DocumentPath) -or
      $ReportResults[0].sha256 -ne (Get-Sha256 $DocumentPath) -or
      [long]$ReportResults[0].sizeBytes -ne (Get-Item -LiteralPath $DocumentPath).Length -or
      $ReportResults[0].opened -ne $true -or $ReportResults[0].valid -ne $true -or
      [int]$ReportResults[0].errorCount -ne 0 -or @($ReportResults[0].errors).Count -ne 0) {
    throw "OPENXML_SCHEMA"
  }
}

function Read-Enum([string]$Prompt, [hashtable]$Choices) {
  while ($true) {
    Write-Host ""
    Write-Host $Prompt
    foreach ($key in ($Choices.Keys | Sort-Object)) {
      Write-Host ("  " + $key + " = " + $Choices[$key])
    }
    $answer = (Read-Host "Choose one").Trim().ToUpperInvariant()
    if ($Choices.ContainsKey($answer)) { return [string]$Choices[$answer] }
    Write-Host "Invalid choice. PASS is never inferred."
  }
}

function Read-ReviewerId() {
  while ($true) {
    $value = (Read-Host "Reviewer ID (2-64 characters: letters, numbers, dot, underscore, hyphen)").Trim()
    if ($value -match '^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$') { return $value }
    Write-Host "Use a pseudonymous reviewer ID only; do not enter a patient or document name."
  }
}

function Read-YesNo([string]$Prompt) {
  while ($true) {
    $answer = (Read-Host ($Prompt + " [Y/N]")).Trim().ToUpperInvariant()
    if ($answer -eq "Y") { return $true }
    if ($answer -eq "N") { return $false }
    Write-Host "Choose Y or N."
  }
}

function Read-HumanObservation([string]$CaseId, [string]$DocumentRole) {
  Write-Host ""
  Write-Host ("Human review while Word copy is open: " + $CaseId + " / " + $DocumentRole)
  Write-Host "Inspect the visible Word window and the separately exported PDF. Do not close Word manually."
  [void](Read-Host "Press ENTER only when both are positioned for review")
  $repair = Read-Enum "Did Word show any repair, unreadable-content, corruption, or conversion-loss dialog?" @{ "N" = "NO_REPAIR_DIALOG"; "U" = "NOT_OBSERVED"; "Y" = "REPAIR_DIALOG_SHOWN" }
  $choices = @{ "B" = "BLOCKED"; "F" = "FAIL"; "P" = "PASS" }
  return [ordered]@{
    repairDialog = $repair
    visibleClinicalValues = Read-Enum "Did every expected visible synthetic value survive?" $choices
    controlBehavior = Read-Enum "Did dropdown and checkbox behavior survive without unexpected flattening?" $choices
    duplicateOrMissingFields = Read-Enum "Were all fields present exactly once with no missing or duplicate field?" $choices
    clinicallyMeaningfulStaticText = Read-Enum "Did clinically meaningful static text survive?" $choices
    tablesHeadersAndFooters = Read-Enum "Were tables, headers, and footers acceptable?" $choices
    marginsFontsAndPagination = Read-Enum "Were margins, fonts, page breaks, and pagination acceptable?" $choices
    overall = Read-Enum "Overall human verdict for this document?" $choices
  }
}

function Write-DeterministicZip([string]$SourceRoot, [string]$Destination) {
  Add-Type -AssemblyName System.IO.Compression
  Add-Type -AssemblyName System.IO.Compression.FileSystem
  if (Test-Path -LiteralPath $Destination) { Remove-Item -LiteralPath $Destination -Force }
  $stream = [IO.File]::Open($Destination, [IO.FileMode]::CreateNew)
  $archive = $null
  try {
    $archive = New-Object IO.Compression.ZipArchive($stream, [IO.Compression.ZipArchiveMode]::Create, $false)
    $fixedTime = [DateTimeOffset]::new(2000, 1, 1, 0, 0, 0, [TimeSpan]::Zero)
    foreach ($file in (Get-ChildItem -LiteralPath $SourceRoot -Recurse -File | Sort-Object FullName)) {
      $relative = Get-PortableRelativePath $file.FullName $SourceRoot
      $entry = $archive.CreateEntry($relative, [IO.Compression.CompressionLevel]::Optimal)
      $entry.LastWriteTime = $fixedTime
      $input = $null
      $output = $null
      try {
        $input = [IO.File]::OpenRead($file.FullName)
        $output = $entry.Open()
        $input.CopyTo($output)
      } finally {
        if ($null -ne $output) { $output.Dispose() }
        if ($null -ne $input) { $input.Dispose() }
      }
    }
  } finally {
    if ($null -ne $archive) { $archive.Dispose() }
    $stream.Dispose()
  }
}

if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
  throw "The signed package document manifest is missing. No document was opened."
}
if ((Get-Sha256 $ManifestPath) -ne $ExpectedManifestSha256) {
  throw "The package manifest hash changed. No document was opened."
}
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
if ($Manifest.sourceCommit -ne $ExpectedCommit -or $Manifest.syntheticOnly -ne $true -or
    $Manifest.openXmlValidator.name -ne "DocumentFormat.OpenXml.OpenXmlValidator" -or
    $Manifest.openXmlValidator.sdkVersion -ne "3.5.1.0" -or
    $Manifest.openXmlValidator.executableSha256 -ne $ExpectedOpenXmlValidatorSha256) {
  throw "The package commit or synthetic-only marker is invalid. No document was opened."
}
if (-not (Test-Path -LiteralPath $OpenXmlValidatorPath -PathType Leaf) -or
    (Get-Sha256 $OpenXmlValidatorPath) -ne $ExpectedOpenXmlValidatorSha256) {
  throw "The pinned Open XML validator is missing or changed. No document was opened."
}

$Documents = New-Object System.Collections.Generic.List[object]
foreach ($entry in $Manifest.documents) {
  $relative = [string]$entry.relativePath
  if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains("..") -or $relative.Contains("\") -or -not $relative.EndsWith(".docx")) {
    throw "The document allowlist contains an unsafe path. No document was opened."
  }
  $source = Join-Path $BundleRoot $relative.Replace("/", "\")
  if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "An allowlisted synthetic document is missing. No document was opened."
  }
  if ((Get-Sha256 $source) -ne [string]$entry.sha256 -or (Get-Item $source).Length -ne [long]$entry.sizeBytes) {
    throw "An allowlisted synthetic document failed its hash/size check. No document was opened."
  }
  $Documents.Add([pscustomobject]@{
    caseId = [string]$entry.caseId
    documentRole = [string]$entry.documentRole
    relativePath = $relative
    sourcePath = $source
    sha256 = [string]$entry.sha256
    sizeBytes = [long]$entry.sizeBytes
    minimumExpectedPages = [int]$entry.minimumExpectedPages
    expectedPageCount = [int]$entry.expectedPageCount
    verification = $entry.verification
  })
}
if ($Documents.Count -ne [int]$Manifest.documentCount) {
  throw "The document allowlist count is inconsistent. No document was opened."
}

if (Test-Path -LiteralPath $ResultsRoot) { Remove-Item -LiteralPath $ResultsRoot -Recurse -Force }
foreach ($directory in @($ResultsRoot, $WorkRoot, $ReopenedRoot, $PdfRoot, $PdfBindingRoot, $OpenXmlRoot)) { Ensure-Directory $directory }
Copy-Item -LiteralPath $ManifestPath -Destination (Join-Path $ResultsRoot "WORD-QA-DOCUMENTS.json")
Copy-Item -LiteralPath (Join-Path $BundleRoot "VISUAL-CHECKLIST.html") -Destination $ResultsRoot
Copy-Item -LiteralPath (Join-Path $BundleRoot "NO-NETWORK-ASSURANCE.txt") -Destination $ResultsRoot

$CopiedVerificationPaths = @{}
foreach ($entry in $Documents) {
  $verificationFile = $entry.verification.expectedValueManifest
  if ($null -eq $verificationFile) { continue }
  $relative = [string]$verificationFile.relativePath
  if ([IO.Path]::IsPathRooted($relative) -or $relative.Contains("..") -or $relative.Contains("\")) {
    throw "The verification manifest contains an unsafe path. No document was opened."
  }
  if ($CopiedVerificationPaths.ContainsKey($relative)) { continue }
  $source = Join-Path $BundleRoot $relative.Replace("/", "\")
  if (-not (Test-Path -LiteralPath $source -PathType Leaf) -or
      (Get-Sha256 $source) -ne [string]$verificationFile.sha256 -or
      (Get-Item $source).Length -ne [long]$verificationFile.sizeBytes) {
    throw "A byte-bound verification manifest is missing or changed. No document was opened."
  }
  $destination = Join-Path $ResultsRoot $relative.Replace("/", "\")
  Ensure-Directory ([IO.Path]::GetDirectoryName($destination))
  Copy-Item -LiteralPath $source -Destination $destination
  $CopiedVerificationPaths[$relative] = $true
}

$ReviewerId = Read-ReviewerId
$Records = New-Object System.Collections.Generic.List[object]
$Word = $null
$WordVersion = "unavailable"
$WordBuild = "unavailable"
$WordProductCode = "unavailable"
$WindowsVersion = [Environment]::OSVersion.VersionString
$WordUnavailable = $false
try {
  try {
    $Word = New-Object -ComObject Word.Application
  } catch {
    $WordUnavailable = $true
  }
  if (-not $WordUnavailable) {
    $Word.Visible = $true
    $Word.DisplayAlerts = -1
    $WordVersion = [string]$Word.Version
    try { $WordBuild = [string]$Word.Build } catch {}
    try { $WordProductCode = [string]$Word.ProductCode } catch {}
  }
  try {
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -ErrorAction Stop
    $WindowsVersion = "$($os.Caption) $($os.Version) build $($os.BuildNumber)"
  } catch {}

  foreach ($entry in $Documents) {
    $safeStem = ($entry.caseId + "--" + $entry.documentRole) -replace '[^A-Za-z0-9._-]', '_'
    $workCopy = Join-Path $WorkRoot ($safeStem + ".work-copy.docx")
    $reopenedPath = Join-Path $ReopenedRoot ($safeStem + ".word-reopened.docx")
    $pdfPath = Join-Path $PdfRoot ($safeStem + ".word.pdf")
    $pdfBindingPath = Join-Path $PdfBindingRoot ($safeStem + ".pdf-export-binding.json")
    $originalBefore = Get-Sha256 $entry.sourcePath
    $status = "BLOCKED"
    $errorCode = if ($WordUnavailable) { "WORD_NOT_INSTALLED" } else { "NONE" }
    $pageBefore = $null
    $pageAfter = $null
    $compatBefore = $null
    $compatAfter = $null
    $saveAsCompleted = $false
    $reopenReadOnlyCompleted = $false
    $pdfExportCompleted = $false
    $generated = New-Object System.Collections.Generic.List[object]
    $humanObservation = $null
    $document = $null
    $reopened = $null
    if (-not $WordUnavailable) {
      try {
        Copy-Item -LiteralPath $entry.sourcePath -Destination $workCopy
        if ((Get-Sha256 $workCopy) -ne $entry.sha256) { throw "COPY_HASH" }
        $generated.Add([pscustomobject](Get-FileEvidence $workCopy $ResultsRoot "work_copy"))
        # Word receives only the disposable copy, never the original path.
        $document = $Word.Documents.Open($workCopy, $false, $false, $false)
        try { $pageBefore = [int]$document.ComputeStatistics(2) } catch {}
        try { $compatBefore = [int]$document.CompatibilityMode } catch {}
        $document.SaveAs2($reopenedPath, 12)
        $saveAsCompleted = $true
        $document.Close(0)
        Release-ComObject $document
        $document = $null
        $reopened = $Word.Documents.Open($reopenedPath, $false, $true, $false)
        $reopenReadOnlyCompleted = $true
        try { $pageAfter = [int]$reopened.ComputeStatistics(2) } catch {}
        try { $compatAfter = [int]$reopened.CompatibilityMode } catch {}
        $reopened.ExportAsFixedFormat($pdfPath, 17)
        $pdfExportCompleted = $true
        if ($null -eq $pageAfter) { throw "PDF_EXPORT_BINDING" }
        $PdfExportBinding = [ordered]@{
          contractVersion = "__PDF_EXPORT_BINDING_VERSION__"
          sourceCommit = $ExpectedCommit
          syntheticOnly = $true
          authorizesClinicalOrProductionAction = $false
          caseId = $entry.caseId
          documentRole = $entry.documentRole
          reopenedDocxSha256 = Get-Sha256 $reopenedPath
          reopenedDocxSizeBytes = [long](Get-Item -LiteralPath $reopenedPath).Length
          exportedPdfSha256 = Get-Sha256 $pdfPath
          exportedPdfSizeBytes = [long](Get-Item -LiteralPath $pdfPath).Length
          wordPageCount = [int]$pageAfter
          recordedAtIso = (Get-Date).ToUniversalTime().ToString("o")
        }
        $PdfExportBinding | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $pdfBindingPath -Encoding UTF8
        try { Start-Process -FilePath $pdfPath | Out-Null } catch {}
        $humanObservation = Read-HumanObservation $entry.caseId $entry.documentRole
        $reopened.Close(0)
        Release-ComObject $reopened
        $reopened = $null
        $generated.Add([pscustomobject](Get-FileEvidence $reopenedPath $ResultsRoot "word_reopened_docx"))
        $generated.Add([pscustomobject](Get-FileEvidence $pdfPath $ResultsRoot "word_exported_pdf"))
        $generated.Add([pscustomobject](Get-FileEvidence $pdfBindingPath $ResultsRoot "pdf_export_binding_json"))
        $openXmlOffice2013 = Join-Path $OpenXmlRoot ($safeStem + ".Office2013.json")
        $openXmlMicrosoft365 = Join-Path $OpenXmlRoot ($safeStem + ".Microsoft365.json")
        Invoke-OpenXmlValidation $reopenedPath $openXmlOffice2013 "Office2013"
        Invoke-OpenXmlValidation $reopenedPath $openXmlMicrosoft365 "Microsoft365"
        $generated.Add([pscustomobject](Get-FileEvidence $openXmlOffice2013 $ResultsRoot "openxml_office2013_json"))
        $generated.Add([pscustomobject](Get-FileEvidence $openXmlMicrosoft365 $ResultsRoot "openxml_microsoft365_json"))
        if ($null -eq $pageAfter -or [int]$pageAfter -lt $entry.minimumExpectedPages) {
          $status = "FAILED"
          $errorCode = "PAGE_COUNT_BELOW_MINIMUM"
        } elseif ([int]$pageAfter -ne $entry.expectedPageCount) {
          $status = "FAILED"
          $errorCode = "PAGE_COUNT_MISMATCH"
        } else {
          $status = "COMPLETED"
        }
      } catch {
        $status = "FAILED"
        $errorCode = if ($_.Exception.Message -eq "COPY_HASH") { "ORIGINAL_HASH_CHANGED" } elseif ($_.Exception.Message -eq "OPENXML_SCHEMA") { "OPENXML_SCHEMA_INVALID" } else { "WORD_COM_AUTOMATION_FAILED" }
      } finally {
        if ($null -ne $reopened) { try { $reopened.Close(0) } catch {}; Release-ComObject $reopened }
        if ($null -ne $document) { try { $document.Close(0) } catch {}; Release-ComObject $document }
      }
    }
    $originalAfter = Get-Sha256 $entry.sourcePath
    $originalUnchanged = ($originalBefore -eq $entry.sha256 -and $originalAfter -eq $entry.sha256)
    if (-not $originalUnchanged) { $status = "FAILED"; $errorCode = "ORIGINAL_HASH_CHANGED" }
    if ($null -eq $humanObservation) {
      Write-Host "Word automation did not provide an open document for inspection. Record FAIL or BLOCKED honestly."
      $humanObservation = Read-HumanObservation $entry.caseId $entry.documentRole
    }
    $Records.Add([pscustomobject][ordered]@{
      caseId = $entry.caseId
      documentRole = $entry.documentRole
      allowlistedRelativePath = $entry.relativePath
      originalExpectedSha256 = $entry.sha256
      originalExpectedSizeBytes = $entry.sizeBytes
      originalBeforeSha256 = $originalBefore
      originalAfterSha256 = $originalAfter
      originalUnchanged = $originalUnchanged
      automationStatus = $status
      automationErrorCode = $errorCode
      saveAsCompleted = $saveAsCompleted
      reopenReadOnlyCompleted = $reopenReadOnlyCompleted
      pdfExportCompleted = $pdfExportCompleted
      pageCountBeforeSave = $pageBefore
      pageCountAfterReopen = $pageAfter
      expectedPageCount = $entry.expectedPageCount
      pageCountMatchesExpected = ($null -ne $pageAfter -and [int]$pageAfter -eq $entry.expectedPageCount)
      minimumExpectedPages = $entry.minimumExpectedPages
      compatibilityModeBeforeSave = $compatBefore
      compatibilityModeAfterReopen = $compatAfter
      generatedFiles = $generated
      humanObservation = $humanObservation
    })
  }
} finally {
  if ($null -ne $Word) { try { $Word.Quit(0) } catch {}; Release-ComObject $Word }
  [GC]::Collect()
  [GC]::WaitForPendingFinalizers()
}

$Attestation = [ordered]@{
  reviewedOnlySyntheticDocuments = Read-YesNo "Do you attest that you reviewed only the synthetic documents in this package?"
  observedRepairDialogsInDesktopWord = Read-YesNo "Do you attest that you personally observed Word for repair dialogs?"
  completedVisualChecklistForEveryDocument = Read-YesNo "Do you attest that you completed the visual checklist for every document?"
  understandsAutomationCannotJudgeVisualCorrectness = Read-YesNo "Do you understand that automation cannot judge visual correctness?"
}
$ManifestCopy = Join-Path $ResultsRoot "WORD-QA-DOCUMENTS.json"
$Evidence = [ordered]@{
  contractVersion = "template-twin-desktop-word-human-evidence/3.0.0"
  sourceCommit = $ExpectedCommit
  packageManifestSha256 = Get-Sha256 $ManifestCopy
  syntheticOnly = $true
  reviewedAtIso = (Get-Date).ToUniversalTime().ToString("o")
  reviewer = [ordered]@{ reviewerId = $ReviewerId; role = "desktop_word_qa_reviewer" }
  environment = [ordered]@{
    windowsVersion = $WindowsVersion
    wordVersion = $WordVersion
    wordBuild = $WordBuild
    wordProductCode = $WordProductCode
  }
  networkRequestsMadeByScript = 0
  administratorPrivilegesRequired = $false
  originalsOpenedByWord = 0
  documentsExpected = $Documents.Count
  documentsCompleted = @($Records | Where-Object { $_.automationStatus -eq "COMPLETED" }).Count
  documentsFailedOrBlocked = @($Records | Where-Object { $_.automationStatus -ne "COMPLETED" }).Count
  documents = $Records
  attestation = $Attestation
}
$EvidencePath = Join-Path $ResultsRoot "WORD-EVIDENCE.json"
$Evidence | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $EvidencePath -Encoding UTF8

$HashFiles = Get-ChildItem -LiteralPath $ResultsRoot -Recurse -File | Sort-Object FullName
$HashManifest = [ordered]@{
  contractVersion = "template-twin-return-evidence-file-hashes/1.0.0"
  files = @($HashFiles | ForEach-Object {
    [ordered]@{
      relativePath = Get-PortableRelativePath $_.FullName $ResultsRoot
      sizeBytes = [long]$_.Length
      sha256 = Get-Sha256 $_.FullName
    }
  })
}
$HashManifest | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $ResultsRoot "RESULT-FILE-HASHES.json") -Encoding UTF8

Write-DeterministicZip $ResultsRoot $ReturnZip
$ReturnHash = Get-Sha256 $ReturnZip
($ReturnHash + "  " + (Split-Path -Leaf $ReturnZip)) | Set-Content -LiteralPath $ReturnSidecar -Encoding ASCII

Write-Host ""
Write-Host ("Return ZIP: " + $ReturnZip)
Write-Host ("SHA-256: " + $ReturnHash)
Write-Host "This evidence does not authorize certification, activation, signing, import, deployment, or media approval."

$HasFailure = @($Records | Where-Object {
  $_.automationStatus -ne "COMPLETED" -or
  $_.humanObservation.repairDialog -eq "REPAIR_DIALOG_SHOWN" -or
  @($_.humanObservation.PSObject.Properties.Value) -contains "FAIL"
}).Count -gt 0
$HasBlocked = @($Records | Where-Object {
  $_.humanObservation.repairDialog -eq "NOT_OBSERVED" -or
  @($_.humanObservation.PSObject.Properties.Value) -contains "BLOCKED"
}).Count -gt 0 -or @($Attestation.Values | Where-Object { $_ -ne $true }).Count -gt 0
if ($HasFailure) { exit 2 }
if ($HasBlocked) { exit 3 }
exit 0
