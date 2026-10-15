$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)

for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
    $p = $doc.Paragraphs.Item($i)
    $txt = $p.Range.Text.Trim()
    if ($txt -match "^(SUMMER TRAINING|CANDIDATE DECLARATION|OFFER LETTER|COMPANY COMPLETION|EMPLOYER FEEDBACK|ACKNOWLEDGEMENT|TABLE OF CONTENTS|LIST OF FIGURES|LIST OF TABLES|CHAPTER)") {
        $pageNum = $p.Range.Information([Microsoft.Office.Interop.Word.WdInformation]::wdActiveEndPageNumber)
        Write-Host "Page $pageNum : $txt"
    }
}

$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
