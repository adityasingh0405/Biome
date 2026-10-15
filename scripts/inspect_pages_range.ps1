$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)

Write-Host "Total Document Pages:" $doc.ComputeStatistics(2)

for ($i = 1; $i -le $doc.Sections.Count; $i++) {
    $sec = $doc.Sections.Item($i)
    $startP = $sec.Range.Characters.First.Information(3)
    $endP = $sec.Range.Characters.Last.Information(3)
    Write-Host "Section ${i} - First Char Page = $startP, Last Char Page = $endP"
}

$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
