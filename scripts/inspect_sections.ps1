$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)

Write-Host "Total Sections:" $doc.Sections.Count
for ($i = 1; $i -le $doc.Sections.Count; $i++) {
    $sec = $doc.Sections.Item($i)
    $startPage = $sec.Range.Information([Microsoft.Office.Interop.Word.WdInformation]::wdActiveEndPageNumber)
    $secPages = $sec.Range.ComputeStatistics(2)
    Write-Host "Section $i : StartPage = $startPage, Pages = $secPages"
}

$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
