$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docPath = (Get-Item "Summer_Training _Report_Format.docx").FullName
$doc = $word.Documents.Open($docPath)

Write-Host "HEADING PAGE NUMBERS:"
for ($i = 1; $i -le $doc.Paragraphs.Count; $i++) {
    $p = $doc.Paragraphs.Item($i)
    $style = $p.Style.NameLocal
    $t = $p.Range.Text.Trim()
    if ($t -match "^(Candidate Declaration|Offer Letter|Company Completion|Employer Feedback|Acknowledgement|Table of Contents|List of Figures|List of Tables|CHAPTER|\d\.\d|References|Appendix|APPENDIX)") {
        $absPage = $p.Range.Information([Microsoft.Office.Interop.Word.WdInformation]::wdActiveEndPageNumber)
        $printPage = $p.Range.Information([Microsoft.Office.Interop.Word.WdInformation]::wdActiveEndAdjustedPageNumber)
        Write-Host "$t -> Printed Page: $printPage (Absolute: $absPage)"
    }
}

$doc.Close([ref]$false)
$word.Quit()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($word) | Out-Null
