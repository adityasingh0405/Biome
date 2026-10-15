$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)
$sec1 = $doc.Sections.Item(1)
Write-Host "Section 1 Paragraphs Count:" $sec1.Range.Paragraphs.Count
for ($i = 1; $i -le $sec1.Range.Paragraphs.Count; $i++) {
    $p = $sec1.Range.Paragraphs.Item($i)
    $page = $p.Range.Information(3)
    $t = $p.Range.Text.Trim()
    if ($t.Length -gt 40) { $t = $t.Substring(0, 40) + "..." }
    Write-Host "Para $i [Page $page]: $t"
}
$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
