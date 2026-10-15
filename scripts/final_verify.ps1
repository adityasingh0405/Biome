$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)

# Update all document fields (TOC, page references)
Write-Host "Updating document fields..."
$doc.Fields.Update()

$totalPages = $doc.ComputeStatistics(2)
Write-Host "FINAL VERIFIED TOTAL PAGES:" $totalPages

for ($i = 1; $i -le $doc.Sections.Count; $i++) {
    $sec = $doc.Sections.Item($i)
    $startP = $sec.Range.Characters.First.Information(3)
    $endP = $sec.Range.Characters.Last.Information(3)
    Write-Host "Section ${i}: Absolute Page Range = $startP to $endP"
}

$doc.Save()
$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
Write-Host "Word verification and field update finished successfully!"
