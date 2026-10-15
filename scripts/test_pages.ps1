$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)
$infoPages = $doc.Range().Information([Microsoft.Office.Interop.Word.WdInformation]::wdNumberOfPagesInDocument)
Write-Host "Information(wdNumberOfPagesInDocument):" $infoPages

# wdStatisticWords = 0, wdStatisticLines = 1, wdStatisticPages = 2, wdStatisticCharacters = 3
$statPages = $doc.ComputeStatistics(2)
Write-Host "ComputeStatistics(2 - wdStatisticPages):" $statPages

$statWords = $doc.ComputeStatistics(0)
Write-Host "ComputeStatistics(0 - wdStatisticWords):" $statWords

$statLines = $doc.ComputeStatistics(1)
Write-Host "ComputeStatistics(1 - wdStatisticLines):" $statLines

$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
